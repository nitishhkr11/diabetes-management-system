"""GlucoGuide API: MDRF-IDRS screening, clinical lab interpretation, and consent-gated history."""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import sys
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.lab_interpretation import interpret_lab_results  # noqa: E402
from src.mdrf_idrs import compute_mdrf_idrs  # noqa: E402


def env_origins() -> list[str]:
    values = [item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if item.strip()]
    if "*" in values:
        raise RuntimeError("CORS_ORIGINS must list exact origins; wildcard origins are not allowed.")
    return values


class RequestBodyLimitMiddleware:
    """Buffer and cap request bodies, including requests without Content-Length."""

    def __init__(self, app, max_bytes: int = 16_384):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        length = next((value.decode("latin-1") for key, value in scope["headers"] if key == b"content-length"), "")
        if length.isdigit() and int(length) > self.max_bytes:
            await JSONResponse(status_code=413, content={"detail": "Request body too large."})(scope, receive, send)
            return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_bytes:
                await JSONResponse(status_code=413, content={"detail": "Request body too large."})(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay_receive():
            nonlocal replayed
            if replayed:
                return {"type": "http.disconnect"}
            replayed = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay_receive, send)


app = FastAPI(
    title="GlucoGuide API",
    summary="Indian diabetes risk screening (MDRF-IDRS) and clinical laboratory interpretation API.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)
app.add_middleware(RequestBodyLimitMiddleware)
logger = logging.getLogger("glucoguide.api")
app.add_middleware(
    CORSMiddleware,
    allow_origins=env_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def request_limits(request: Request, call_next):
    request_id = UUID(bytes=os.urandom(16), version=4).hex[:16]
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > 16_384:
        response = JSONResponse(status_code=413, content={"detail": "Request body too large."})
        response.headers["X-Request-ID"] = request_id
        return response
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("api_unhandled_error request_id=%s method=%s route=%s", request_id, request.method, request.url.path)
        response = JSONResponse(status_code=500, content={"detail": f"Unexpected API error. Reference {request_id}."})
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    # Return only field, message and type so sensitive health inputs are not echoed into logs.
    details = [{
        "field": ".".join(str(part) for part in item.get("loc", ()) if part != "body"),
        "message": item.get("msg", "Invalid input."),
        "code": item.get("type", "invalid"),
    } for item in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": details})


class DeleteResponse(BaseModel):
    deleted: bool


class DeleteAllResponse(BaseModel):
    deleted: bool
    count: int


def supabase_settings() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    anon = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not anon or "YOUR_PROJECT" in url or "YOUR_SUPABASE" in anon:
        raise HTTPException(status_code=503, detail="Account history is not configured. Add Supabase URL and anon key.")
    return url, anon


async def current_user(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in to access account history.", headers={"WWW-Authenticate": "Bearer"})
    url, anon = supabase_settings()
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"{url}/auth/v1/user",
                headers={"apikey": anon, "Authorization": authorization},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Authentication provider is temporarily unavailable.") from exc
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Session is invalid or expired.", headers={"WWW-Authenticate": "Bearer"})
    try:
        user = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Session is invalid.") from exc
    if not user.get("id"):
        raise HTTPException(status_code=401, detail="Session is invalid.")
    return user


class RateWindow:
    """Small per-process request throttle for public screening endpoints."""

    def __init__(self):
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        stamp = time.monotonic() if now is None else now
        hits = self.hits[key]
        while hits and hits[0] <= stamp - 60:
            hits.popleft()
        if len(hits) >= 60:
            return False
        hits.append(stamp)
        return True


rate_window = RateWindow()
User = Annotated[dict, Depends(current_user)]


async def postgrest(
    method: str,
    table_path: str,
    token: str,
    *,
    json_body=None,
    prefer: str = "return=representation",
    exact_count: bool = False,
):
    url, anon = supabase_settings()
    headers = {"apikey": anon, "Authorization": token, "Accept-Profile": "public", "Content-Profile": "public"}
    if method in {"POST", "DELETE"}:
        headers["Prefer"] = prefer
    if exact_count:
        headers["Prefer"] = "count=exact"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.request(method, f"{url}/rest/v1/{table_path}", headers=headers, json=json_body)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="History storage is temporarily unavailable.") from exc
    if response.status_code >= 400:
        code = 404 if response.status_code == 404 else (409 if response.status_code == 409 else 503)
        raise HTTPException(status_code=code, detail="History operation could not be completed.")
    result = response.json() if response.content else None
    if exact_count:
        content_range = response.headers.get("content-range", "*/0")
        try:
            total = int(content_range.rsplit("/", 1)[1])
        except (ValueError, IndexError):
            total = len(result or [])
        return result, total
    return result


@app.get("/health/live", tags=["health"])
def live():
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def ready():
    return {"status": "ready", "service": "glucoguide-india-screening"}


# ═══════════════════════════════════════════════════════════════════════════════
# INDIA SCREENING — MDRF-IDRS & CLINICAL LAB RESULT INTERPRETATION
# ═══════════════════════════════════════════════════════════════════════════════


class IdrsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    age_years: float = Field(ge=20, le=120)
    sex: Literal["female", "male"]
    waist_value: float = Field(gt=0)
    waist_unit: Literal["cm", "in"] = "cm"
    physical_activity: Literal["vigorous", "moderate", "mild", "sedentary"]
    family_history: Literal["none", "one_parent", "both_parents"]


class LabInterpretInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_pregnant: bool = False
    hba1c_pct: float | None = Field(default=None, ge=3.0, le=20.0)
    fasting_glucose: float | None = Field(default=None, gt=0)
    fasting_unit: Literal["mg/dL", "mmol/L"] = "mg/dL"
    ogtt_2h_glucose: float | None = Field(default=None, gt=0)
    ogtt_unit: Literal["mg/dL", "mmol/L"] = "mg/dL"
    random_glucose: float | None = Field(default=None, gt=0)
    random_unit: Literal["mg/dL", "mmol/L"] = "mg/dL"
    has_classic_symptoms: bool = False


class SaveIndiaRiskAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent: bool
    assessment_type: Literal["mdrf_idrs", "lab_interpretation"]
    idrs_inputs: IdrsInput | None = None
    lab_inputs: LabInterpretInput | None = None


@app.post("/api/v1/india-risk/idrs", tags=["india-risk"])
def run_mdrf_idrs(payload: IdrsInput, request: Request):
    """Compute MDRF Indian Diabetes Risk Score (adults 20+, no blood test required)."""
    host = request.headers.get("x-dms-rate-key") or (request.client.host if request.client else "unknown")
    if not rate_window.allow(host):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute and try again.", headers={"Retry-After": "60"})
    try:
        return compute_mdrf_idrs(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/india-risk/lab-interpret", tags=["india-risk"])
def run_lab_interpret(payload: LabInterpretInput, request: Request):
    """Interpret blood test results using ADA / ICMR-WHO criteria."""
    host = request.headers.get("x-dms-rate-key") or (request.client.host if request.client else "unknown")
    if not rate_window.allow(host):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute and try again.", headers={"Retry-After": "60"})
    try:
        return interpret_lab_results(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/india-risk/history", tags=["india-risk-history"])
async def india_risk_history_create(
    payload: SaveIndiaRiskAssessment,
    user: User,
    authorization: Annotated[str, Header()],
):
    if payload.consent is not True:
        raise HTTPException(status_code=400, detail="Explicit consent is required before saving an assessment.")
    if payload.assessment_type == "mdrf_idrs":
        if not payload.idrs_inputs:
            raise HTTPException(status_code=422, detail="idrs_inputs required for mdrf_idrs.")
        try:
            res = compute_mdrf_idrs(**payload.idrs_inputs.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        record = {
            "assessment_type": "mdrf_idrs",
            "guideline_version": res["guideline_version"],
            "result_category": res["risk_label"],
            "score": float(res["score"]),
            "inputs": res["normalized_inputs"],
            "result_payload": res,
            "consent": True,
        }
    else:
        if not payload.lab_inputs:
            raise HTTPException(status_code=422, detail="lab_inputs required for lab_interpretation.")
        try:
            res = interpret_lab_results(**payload.lab_inputs.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        record = {
            "assessment_type": "lab_interpretation",
            "guideline_version": res["guideline_version"],
            "result_category": res["overall_label"],
            "score": None,
            "inputs": payload.lab_inputs.model_dump(),
            "result_payload": res,
            "consent": True,
        }
    saved = await postgrest("POST", "india_risk_assessments", authorization, json_body=record)
    return {"item": (saved or [None])[0]}


@app.get("/api/v1/india-risk/history", tags=["india-risk-history"])
async def india_risk_history_list(
    user: User,
    authorization: Annotated[str, Header()],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    path = (
        "india_risk_assessments?select=id,created_at,assessment_type,guideline_version,"
        "result_category,score,inputs,result_payload,consent"
        f"&order=created_at.desc&limit={limit}&offset={offset}"
    )
    records, total = await postgrest("GET", path, authorization, exact_count=True)
    return {"items": records or [], "total": total, "limit": limit, "offset": offset}


@app.get("/api/v1/india-risk/history/export", tags=["india-risk-history"])
async def india_risk_history_export(user: User, authorization: Annotated[str, Header()]):
    path = (
        "india_risk_assessments?select=id,created_at,assessment_type,guideline_version,"
        "result_category,score,inputs,consent&order=created_at.desc&limit=500"
    )
    records = await postgrest("GET", path, authorization)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "created_at", "assessment_type", "guideline_version", "result_category", "score", "inputs_json", "consent"])
    for row in records or []:
        writer.writerow([
            row.get("id", ""),
            row.get("created_at", ""),
            row.get("assessment_type", ""),
            row.get("guideline_version", ""),
            row.get("result_category", ""),
            row.get("score", ""),
            json.dumps(row.get("inputs", {})),
            row.get("consent", True),
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="glucoguide-india-history.csv"'},
    )


@app.delete("/api/v1/india-risk/history/{assessment_id}", response_model=DeleteResponse, tags=["india-risk-history"])
async def india_risk_history_delete(assessment_id: UUID, user: User, authorization: Annotated[str, Header()]):
    rows = await postgrest("DELETE", f"india_risk_assessments?id=eq.{assessment_id}", authorization, prefer="return=representation")
    return {"deleted": bool(rows)}


@app.delete("/api/v1/india-risk/history", response_model=DeleteAllResponse, tags=["india-risk-history"])
async def india_risk_history_delete_all(user: User, authorization: Annotated[str, Header()]):
    rows = await postgrest("DELETE", "india_risk_assessments?consent=eq.true", authorization, prefer="return=representation")
    return {"deleted": True, "count": len(rows or [])}
