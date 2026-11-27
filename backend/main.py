"""Versioned API that serves the existing verified ML release artifacts."""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import sys
import time
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config as C  # noqa: E402
from src.audit_report import build_audit_html  # noqa: E402
from src.predict import ArtifactError, load_artifacts, predict_one  # noqa: E402
from src.sensitivity import sensitivity_bounds, vary_feature  # noqa: E402
from src.medical_report import MAX_BYTES as REPORT_MAX_BYTES, ReportError, extract_text, parse_observations  # noqa: E402
from src.public_predict import (  # noqa: E402
    PublicModelError, load_public_artifacts, predict_public,
    get_public_metadata, get_public_evaluation,
)
from src.india_predict import (  # noqa: E402
    IndiaModelUnavailableError, get_india_status, get_india_metadata,
    get_india_evaluation, load_india_artifacts, predict_india,
)
from src.brfss_predict import (  # noqa: E402
    get_brfss_metadata, get_brfss_evaluation,
)
from src.mdrf_idrs import compute_mdrf_idrs  # noqa: E402
from src.lab_interpretation import interpret_lab_results  # noqa: E402

REPORT_REQUEST_LIMIT = REPORT_MAX_BYTES + 256 * 1024


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
        path = scope.get("path", "")
        limit = REPORT_REQUEST_LIMIT if path == "/api/v1/reports/extract" else self.max_bytes
        length = next((value.decode("latin-1") for key, value in scope["headers"] if key == b"content-length"), "")
        if length.isdigit() and int(length) > limit:
            await JSONResponse(status_code=413, content={"detail": "Request body too large."})(scope, receive, send)
            return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > limit:
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
    title="Diabetes Management System API",
    summary="Educational research inference API; not for diagnosis or treatment.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)
app.add_middleware(RequestBodyLimitMiddleware)
logger = logging.getLogger("dms.api")
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
    request_limit = REPORT_REQUEST_LIMIT if request.url.path == "/api/v1/reports/extract" else 16_384
    if length and length.isdigit() and int(length) > request_limit:
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
    # Pydantic's default 422 includes the submitted value. Return only field,
    # message and type so health measurements are not echoed into proxy logs.
    details = [{
        "field": ".".join(str(part) for part in item.get("loc", ()) if part != "body"),
        "message": item.get("msg", "Invalid input."),
        "code": item.get("type", "invalid"),
    } for item in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": details})


class AssessmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    Pregnancies: float | None = Field(default=None, ge=0, le=20)
    Glucose: float | None = Field(default=None, ge=0, le=500)
    BloodPressure: float | None = Field(default=None, ge=0, le=150)
    SkinThickness: float | None = Field(default=None, ge=0, le=100)
    Insulin: float | None = Field(default=None, ge=0, le=1000)
    BMI: float | None = Field(default=None, ge=0, le=80)
    DiabetesPedigreeFunction: float | None = Field(default=None, ge=0, le=3)
    Age: float | None = Field(default=None, ge=0, le=100)
    input_sources: dict[str, Literal["manual", "report"]] = Field(default_factory=dict, max_length=8)

    @model_validator(mode="after")
    def validate_source_keys(self):
        if set(self.input_sources) - set(C.FEATURES):
            raise ValueError("Input source keys must match supported model features.")
        return self


class SaveAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent: bool
    inputs: AssessmentInput


class AuditReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inputs: AssessmentInput
    case_reference: str | None = Field(default=None, max_length=80)


class SensitivityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inputs: AssessmentInput
    feature: str = Field(min_length=1, max_length=40)
    points: int = Field(default=31, ge=5, le=61)


class DeleteResponse(BaseModel):
    deleted: bool


@lru_cache(maxsize=1)
def artifacts():
    models_dir = Path(os.getenv("DIABETES_MODELS_DIR", ROOT / "models"))
    return load_artifacts(models_dir)


def ready_artifacts():
    try:
        return artifacts()
    except (ArtifactError, OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=503, detail="Verified model artifacts are unavailable. Check deployment setup.") from exc


def supabase_settings():
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
    """Small per-process prediction throttle; use an edge/API gateway for scaled deployments."""
    def __init__(self):
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        stamp = time.monotonic() if now is None else now
        hits = self.hits[key]
        while hits and hits[0] <= stamp - 60:
            hits.popleft()
        if len(hits) >= 30:
            return False
        hits.append(stamp)
        return True


rate_window = RateWindow()
User = Annotated[dict, Depends(current_user)]


@app.get("/health/live", tags=["health"])
def live():
    return {"status": "ok"}


@app.post("/api/v1/reports/extract", tags=["reports"])
async def extract_medical_report(_: User, file: UploadFile = File(...)):
    """Extract reviewable laboratory observations in memory; never persist the upload."""
    try:
        if file.content_type not in {"application/pdf", "image/png", "image/jpeg"}:
            raise HTTPException(status_code=415, detail="Upload a PDF, PNG, JPG, or JPEG file.")
        payload = await file.read(REPORT_MAX_BYTES + 1)
        if len(payload) > REPORT_MAX_BYTES:
            raise HTTPException(status_code=413, detail="The report is larger than the 10 MB limit.")
        try:
            extracted = await run_in_threadpool(extract_text, payload, file.content_type)
        except ReportError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        observations = await run_in_threadpool(parse_observations, extracted.text, extracted.confidence)
        if not extracted.text.strip():
            raise HTTPException(status_code=422, detail="No readable text was found. Try a clearer report or enter values manually.")
        return {
            "observations": observations,
            "method": extracted.method,
            "pages": extracted.pages,
            "confidence": extracted.confidence,
            "source_name": (file.filename or "report").rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:120],
            "retained": False,
            "notice": "Review every extracted value. Laboratory findings are separate from model inputs and are not a diagnosis.",
        }
    finally:
        await file.close()


@app.get("/health/ready", tags=["health"])
def ready():
    art = ready_artifacts()
    return {"status": "ready", "model_version": art.card["model_version"]}


@app.get("/api/v1/metadata", tags=["public"])
def metadata(art=Depends(ready_artifacts)):
    return {
        "project": "Diabetes Management System",
        "model_label": "Historical Pima research benchmark",
        "intended_use": "Educational research prototype; not a medical device or clinical risk calculator.",
        "model_version": art.card["model_version"],
        "trained_at": art.card.get("trained_at"),
        "selected_model": art.selected,
        "models": art.card.get("model_names", C.MODEL_ORDER),
        "threshold": art.threshold,
        "profile": art.card.get("profile", {}),
        "dataset": art.card.get("dataset"),
        "population_scope": art.card.get("population"),
        "cv_results": art.card.get("cv_table", []),
        "held_out_results": art.card.get("test_table", []),
        "features": C.FEATURES,
    }


@app.get("/api/v1/evaluation", tags=["public"])
def evaluation(art=Depends(ready_artifacts)):
    return {
        "selection_rule": art.card.get("selection_rule",
            "Stratified 5-fold CV on the training split: ROC-AUC, then F1, then accuracy within tolerance, then model simplicity."),
        "current_run_test_used_for_selection": art.card.get("current_run_test_used_for_selection", False),
        "historical_test_exposure": art.card.get("historical_test_exposure", True),
        "independent_test_claim": art.card.get("independent_test_claim", False),
        "test_exposure_note": art.card.get("test_exposure_note", "The nominal holdout has prior repository exploration and is descriptive, not confirmatory."),
        "cv": art.card.get("cv_table", []),
        "test": art.card.get("test_table", []),
        "threshold": art.threshold,
        "threshold_objective": art.card.get("threshold_objective"),
        "confidence_intervals": art.card.get("test_confidence_intervals", {}),
        "calibration_bins": art.card.get("calibration_bins", []),
        "figures": {p.stem: f"/api/v1/evaluation/figures/{p.name}" for p in (ROOT / "reports" / "figures").glob("*_test.png")},
    }


@app.get("/api/v1/evaluation/chart-data", tags=["public"])
def evaluation_chart_data(art=Depends(ready_artifacts)):
    """Serve interactive plot points only when they match the loaded model release."""
    path = ROOT / "reports" / "interactive_charts.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"available": False, "reason": "Interactive chart data are not available for this release."}
    if data.get("model_version") != art.card.get("model_version") or data.get("model") != art.selected:
        return {"available": False, "reason": "Interactive chart data do not match the loaded model release."}
    return {"available": True, **data}


@app.get("/api/v1/evaluation/figures/{filename}", tags=["public"])
def evaluation_figure(filename: str):
    allowed = {"roc_test.png", "confusion_test.png", "calibration_test.png", "shap_global_bar.png", "shap_beeswarm.png"}
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="Evaluation figure not found.")
    file = ROOT / "reports" / "figures" / filename
    if not file.is_file():
        raise HTTPException(status_code=404, detail="Evaluation figure not found.")
    return Response(file.read_bytes(), media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@app.post("/api/v1/predictions", tags=["predictions"])
def create_prediction(payload: AssessmentInput, request: Request, art=Depends(ready_artifacts)):
    client_host = request.headers.get("x-dms-rate-key") or (request.client.host if request.client else "unknown")
    if not rate_window.allow(client_host):
        raise HTTPException(status_code=429, detail="Too many assessments. Wait a minute and try again.", headers={"Retry-After": "60"})
    output = predict_one(art, payload.model_dump(), explain=True)
    if not output["ok"]:
        raise HTTPException(status_code=422, detail={"errors": output["errors"], "warnings": output["warnings"]})
    output["input_sources"] = payload.input_sources
    return output


@app.post("/api/v1/reports/assessment", tags=["predictions"])
def assessment_report(payload: AuditReportRequest, art=Depends(ready_artifacts)):
    output = predict_one(art, payload.inputs.model_dump(), explain=True)
    if not output["ok"]:
        raise HTTPException(status_code=422, detail={"errors": output["errors"], "warnings": output["warnings"]})
    output["input_sources"] = payload.inputs.input_sources
    report = build_audit_html(output, art.card, payload.case_reference)
    return Response(report, media_type="text/html; charset=utf-8", headers={"Content-Disposition": "attachment; filename=assessment-audit.html", "Cache-Control": "no-store"})


@app.post("/api/v1/sensitivity", tags=["predictions"])
def sensitivity(payload: SensitivityRequest, request: Request, art=Depends(ready_artifacts)):
    host = request.headers.get("x-dms-rate-key") or (request.client.host if request.client else "unknown")
    if not rate_window.allow(host):
        raise HTTPException(status_code=429, detail="Too many model requests. Wait a minute and try again.", headers={"Retry-After": "60"})
    if payload.feature not in C.FEATURES:
        raise HTTPException(status_code=422, detail="Choose a supported dataset feature.")
    try:
        low, high = sensitivity_bounds(art.card["profile"], payload.feature)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Training-range sensitivity profile is unavailable.") from exc
    import numpy as np
    base = payload.inputs.model_dump()
    curve = []
    for value in np.linspace(low, high, payload.points):
        case = vary_feature(base, payload.feature, float(value))
        outcome = predict_one(art, case, explain=False)
        if not outcome["ok"]:
            raise HTTPException(status_code=422, detail={"errors": outcome["errors"], "warnings": outcome["warnings"]})
        curve.append({"value": float(value), "models": outcome["all_models"]})
    return {"feature": payload.feature, "range": [low, high], "points": curve, "disclaimer": "One-feature-at-a-time model sensitivity only; not causal, physiological or medical evidence."}


async def postgrest(method: str, table_path: str, token: str, *, json_body=None, prefer="return=representation", exact_count=False):
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
        # Do not forward provider details, SQL, or database internals.
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


@app.get("/api/v1/history", tags=["history"])
async def history_list(user: User, authorization: Annotated[str, Header()],
                       limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    path = f"assessments?select=id,created_at,model_version,model_name,score,label,threshold,inputs,explanation&order=created_at.desc&limit={limit}&offset={offset}"
    records, total = await postgrest("GET", path, authorization, exact_count=True)
    return {"items": records or [], "total": total, "limit": limit, "offset": offset}


@app.post("/api/v1/history", tags=["history"])
async def history_create(payload: SaveAssessment, user: User, authorization: Annotated[str, Header()]):
    if payload.consent is not True:
        raise HTTPException(status_code=400, detail="Explicit consent is required before saving an assessment.")
    art = ready_artifacts()
    row = predict_one(art, payload.inputs.model_dump(), explain=True)
    if not row["ok"]:
        raise HTTPException(status_code=422, detail={"errors": row["errors"], "warnings": row["warnings"]})
    record = {
        "model_version": str(row["model_version"]), "model_name": str(row["model"]),
        "score": float(row["probability"]), "label": int(row["label"]),
        "threshold": float(row["threshold"]),
        "inputs": {**row["inputs"], "input_sources": payload.inputs.input_sources},
        "explanation": row["explanation"],
    }
    saved = await postgrest("POST", "assessments", authorization, json_body=record)
    return {"item": (saved or [None])[0]}


@app.get("/api/v1/history/export", tags=["history"])
async def history_export(user: User, authorization: Annotated[str, Header()]):
    rows = await postgrest("GET", "assessments?select=id,created_at,model_version,model_name,score,label,threshold,inputs,explanation&order=created_at.desc&limit=1000", authorization)
    output = io.StringIO(newline="")
    fields = ["id", "created_at", "model_version", "model_name", "score", "label", "threshold", "inputs", "explanation"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for record in rows or []:
        writer.writerow({**record, "inputs": json.dumps(record.get("inputs", {}), separators=(",", ":")), "explanation": json.dumps(record.get("explanation", {}), separators=(",", ":"))})
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=assessment-history.csv"})


@app.delete("/api/v1/history/{assessment_id}", response_model=DeleteResponse, tags=["history"])
async def history_delete(assessment_id: UUID, user: User, authorization: Annotated[str, Header()]):
    rows = await postgrest("DELETE", f"assessments?id=eq.{assessment_id}", authorization, prefer="return=representation")
    return {"deleted": bool(rows)}


@app.delete("/api/v1/history", tags=["history"])
async def history_delete_all(user: User, authorization: Annotated[str, Header()]):
    await postgrest("DELETE", "assessments?id=not.is.null", authorization, prefer="return=minimal")
    return {"deleted": True}


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC SCREENING — Model 2 (NHANES) — no authentication required
# ═══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def public_artifacts():
    models_dir = Path(os.getenv("PUBLIC_MODELS_DIR", ROOT / "models" / "public_screening"))
    return load_public_artifacts(str(models_dir))


def ready_public_artifacts():
    try:
        return public_artifacts()
    except PublicModelError as exc:
        raise HTTPException(status_code=503, detail=f"Public screening model unavailable: {exc}") from exc


class PublicScreeningInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    age_years:          float | None = Field(default=None, ge=21,  le=80)
    sex_male:           float | None = Field(default=None, ge=0,   le=1)
    bmi:                float | None = Field(default=None, ge=10,  le=70)
    waist_cm:           float | None = Field(default=None, ge=40,  le=200)
    sys_bp:             float | None = Field(default=None, ge=60,  le=220)
    dia_bp:             float | None = Field(default=None, ge=20,  le=130)
    mod_days_per_week:  float | None = Field(default=None, ge=0,   le=7)
    vig_days_per_week:  float | None = Field(default=None, ge=0,   le=7)
    sedentary_min_day:  float | None = Field(default=None, ge=0,   le=1440)
    smoked_100:         float | None = Field(default=None, ge=0,   le=1)
    current_smoker:     float | None = Field(default=None, ge=0,   le=1)


class SaveScreeningAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent: bool
    inputs: PublicScreeningInput


@app.get("/api/v1/public-screening/metadata", tags=["public-screening"])
def public_screening_metadata(art=Depends(ready_public_artifacts)):
    """Model card and feature schema for the public screening model (no auth)."""
    return get_public_metadata(art)


@app.get("/api/v1/public-screening/evaluation", tags=["public-screening"])
def public_screening_evaluation(art=Depends(ready_public_artifacts)):
    """Full evaluation data for the research/interviewer dashboard (no auth)."""
    return get_public_evaluation(art)


@app.get("/api/v1/public-screening/figures/{filename}", tags=["public-screening"])
def public_screening_figure(filename: str):
    """Serve evaluation figures for the public screening model."""
    allowed = {"roc_test.png", "confusion_test.png", "calibration_test.png", "feature_importance.png"}
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="Figure not found.")
    path = ROOT / "reports" / "public_screening" / "figures" / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Figure not yet generated.")
    return Response(path.read_bytes(), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.post("/api/v1/public-screening/predictions", tags=["public-screening"])
def create_public_screening_prediction(
    payload: PublicScreeningInput,
    request: Request,
    art=Depends(ready_public_artifacts),
):
    """
    Guest-accessible public diabetes screening prediction.
    No authentication required. Inputs are non-laboratory biometric measurements.
    Rate-limited per client IP.
    """
    client_host = request.headers.get("x-dms-rate-key") or (
        request.client.host if request.client else "unknown"
    )
    if not rate_window.allow(client_host):
        raise HTTPException(
            status_code=429,
            detail="Too many screening requests. Wait a minute and try again.",
            headers={"Retry-After": "60"},
        )
    raw = payload.model_dump()
    result = predict_public(art, raw)
    if not result["ok"]:
        raise HTTPException(status_code=422, detail={
            "errors": result.get("errors", []),
            "warnings": result.get("warnings", []),
        })
    return result


@app.post("/api/v1/public-screening/history", tags=["public-screening-history"])
async def screening_history_create(
    payload: SaveScreeningAssessment,
    user: User,
    authorization: Annotated[str, Header()],
    art=Depends(ready_public_artifacts),
):
    """Save a public screening assessment to personal history (requires auth + consent)."""
    if payload.consent is not True:
        raise HTTPException(status_code=400, detail="Explicit consent is required before saving an assessment.")
    raw = payload.inputs.model_dump()
    result = predict_public(art, raw)
    if not result["ok"]:
        raise HTTPException(status_code=422, detail={
            "errors": result.get("errors", []),
            "warnings": result.get("warnings", []),
        })
    record = {
        "model_version": result["model_version"],
        "model_name":    result["model"],
        "model_type":    "public_screening",
        "score":         result["probability"],
        "label":         result["label"],
        "band":          result["band"],
        "threshold":     result["threshold"],
        "inputs":        result["inputs"],
        "missing_inputs": result["missing_inputs"],
        "dataset":       "NHANES 2017-2018",
    }
    saved = await postgrest("POST", "screening_assessments", authorization, json_body=record)
    return {"item": (saved or [None])[0]}


@app.get("/api/v1/public-screening/history", tags=["public-screening-history"])
async def screening_history_list(
    user: User,
    authorization: Annotated[str, Header()],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    path = (
        f"screening_assessments?select=id,created_at,model_version,model_name,"
        f"score,label,band,threshold,inputs,missing_inputs,dataset"
        f"&order=created_at.desc&limit={limit}&offset={offset}"
    )
    records, total = await postgrest("GET", path, authorization, exact_count=True)
    return {"items": records or [], "total": total, "limit": limit, "offset": offset}


@app.get("/api/v1/public-screening/history/export", tags=["public-screening-history"])
async def screening_history_export(user: User, authorization: Annotated[str, Header()]):
    rows = await postgrest(
        "GET",
        "screening_assessments?select=id,created_at,model_version,model_name,"
        "score,label,band,threshold,inputs,missing_inputs,dataset"
        "&order=created_at.desc&limit=1000",
        authorization,
    )
    output = io.StringIO(newline="")
    fields = ["id", "created_at", "model_version", "model_name", "score", "label",
              "band", "threshold", "inputs", "missing_inputs", "dataset"]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for record in rows or []:
        writer.writerow({
            **record,
            "inputs": json.dumps(record.get("inputs", {}), separators=(",", ":")),
            "missing_inputs": json.dumps(record.get("missing_inputs", []), separators=(",", ":")),
        })
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=screening-history.csv"},
    )


@app.delete("/api/v1/public-screening/history/{assessment_id}",
            response_model=DeleteResponse, tags=["public-screening-history"])
async def screening_history_delete(
    assessment_id: UUID, user: User, authorization: Annotated[str, Header()]
):
    rows = await postgrest(
        "DELETE", f"screening_assessments?id=eq.{assessment_id}",
        authorization, prefer="return=representation"
    )
    return {"deleted": bool(rows)}


@app.delete("/api/v1/public-screening/history", tags=["public-screening-history"])
async def screening_history_delete_all(user: User, authorization: Annotated[str, Header()]):
    await postgrest("DELETE", "screening_assessments?id=not.is.null",
                    authorization, prefer="return=minimal")
    return {"deleted": True}


# ═══════════════════════════════════════════════════════════════════════════════
# INDIA SCREENING — Model 3 (ICMR-INDIAB) — independent & gated
# ═══════════════════════════════════════════════════════════════════════════════

class IndiaScreeningInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    age_years: float = Field(ge=20, le=100)
    sex: str = Field(min_length=1, max_length=20)
    bmi: float | None = Field(default=None, ge=10, le=70)
    waist_cm: float | None = Field(default=None, ge=40, le=200)
    waist_height_ratio: float | None = Field(default=None, ge=0.25, le=1.2)
    sys_bp: float | None = Field(default=None, ge=60, le=240)
    dia_bp: float | None = Field(default=None, ge=30, le=140)
    family_history_diabetes: str | None = Field(default=None, max_length=20)
    physical_activity_score: float | None = Field(default=None, ge=0, le=10000)
    tobacco_use: str | None = Field(default=None, max_length=30)
    alcohol_use: str | None = Field(default=None, max_length=30)
    education_level: str | None = Field(default=None, max_length=40)
    ses_indicator: str | None = Field(default=None, max_length=40)
    residence_type: str | None = Field(default=None, max_length=20)
    state_region: str | None = Field(default=None, max_length=60)


class SaveIndiaAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent: bool
    inputs: IndiaScreeningInput


def ready_india_artifacts():
    try:
        return load_india_artifacts()
    except IndiaModelUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "available": False,
                "status": get_india_status(),
                "message": str(exc),
            },
        ) from exc


@app.get("/api/v1/india-screening/status", tags=["india-screening"])
def india_screening_status():
    """Return ICMR-INDIAB dataset access status and model availability."""
    return get_india_status()


@app.get("/api/v1/india-screening/metadata", tags=["india-screening"])
def india_screening_metadata():
    """Return ICMR-INDIAB model metadata (honestly reports unavailable until trained)."""
    return get_india_metadata()


@app.get("/api/v1/india-screening/evaluation", tags=["india-screening"])
def india_screening_evaluation():
    """Return ICMR-INDIAB evaluation metadata (or unavailable status)."""
    return get_india_evaluation()


@app.post("/api/v1/india-screening/predictions", tags=["india-screening"])
def create_india_screening_prediction(payload: IndiaScreeningInput, request: Request):
    """Run India-specific screening prediction ONLY when ICMR-INDIAB model is trained & verified."""
    art = ready_india_artifacts()
    client_host = request.headers.get("x-dms-rate-key") or (request.client.host if request.client else "unknown")
    if not rate_window.allow(client_host):
        raise HTTPException(status_code=429, detail="Too many screening requests. Wait a minute and try again.", headers={"Retry-After": "60"})
    result = predict_india(art, payload.model_dump())
    if not result["ok"]:
        raise HTTPException(status_code=422, detail={"errors": result.get("errors", []), "warnings": result.get("warnings", [])})
    return result


@app.post("/api/v1/india-screening/history", tags=["india-screening-history"])
async def india_history_create(
    payload: SaveIndiaAssessment,
    user: User,
    authorization: Annotated[str, Header()],
):
    if payload.consent is not True:
        raise HTTPException(status_code=400, detail="Explicit consent is required before saving an assessment.")
    art = ready_india_artifacts()
    result = predict_india(art, payload.inputs.model_dump())
    if not result["ok"]:
        raise HTTPException(status_code=422, detail={"errors": result.get("errors", []), "warnings": result.get("warnings", [])})
    record = {
        "model_family": "india_indiab",
        "model_version": result["model_version"],
        "model_name": result["model"],
        "model_card_ref": "models/india_indiab/model_card.json",
        "score": result["probability"],
        "threshold": result["threshold"],
        "label": result["label"],
        "band": result["band"],
        "inputs": result["inputs"],
        "missing_inputs": result["missing_inputs"],
        "consent": True,
    }
    saved = await postgrest("POST", "india_assessments", authorization, json_body=record)
    return {"item": (saved or [None])[0]}


@app.get("/api/v1/india-screening/history", tags=["india-screening-history"])
async def india_history_list(
    user: User,
    authorization: Annotated[str, Header()],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    path = (
        "india_assessments?select=id,created_at,model_family,model_version,model_name,"
        "model_card_ref,score,threshold,label,band,inputs,missing_inputs,consent"
        f"&order=created_at.desc&limit={limit}&offset={offset}"
    )
    records, total = await postgrest("GET", path, authorization, exact_count=True)
    return {"items": records or [], "total": total, "limit": limit, "offset": offset}


@app.delete("/api/v1/india-screening/history/{assessment_id}", response_model=DeleteResponse, tags=["india-screening-history"])
async def india_history_delete(assessment_id: UUID, user: User, authorization: Annotated[str, Header()]):
    rows = await postgrest("DELETE", f"india_assessments?id=eq.{assessment_id}", authorization, prefer="return=representation")
    return {"deleted": bool(rows)}


# ═══════════════════════════════════════════════════════════════════════════════
# CDC BRFSS RESEARCH BENCHMARK — UCI ID 891 (US survey data, independent)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/v1/brfss-benchmark/metadata", tags=["brfss-benchmark"])
def brfss_benchmark_metadata():
    """Return metadata for the large US CDC BRFSS research benchmark (no auth)."""
    return get_brfss_metadata()


@app.get("/api/v1/brfss-benchmark/evaluation", tags=["brfss-benchmark"])
def brfss_benchmark_evaluation():
    """Return full evaluation metrics, curves, and confusion matrices for CDC BRFSS."""
    return get_brfss_evaluation()


# ═══════════════════════════════════════════════════════════════════════════════
# INDIA REAL-WORLD SCREENING — MDRF-IDRS & LAB RESULT INTERPRETATION
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
def run_mdrf_idrs(payload: IdrsInput):
    """Compute MDRF Indian Diabetes Risk Score (adults 20+, no blood test required)."""
    try:
        return compute_mdrf_idrs(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/india-risk/lab-interpret", tags=["india-risk"])
def run_lab_interpret(payload: LabInterpretInput):
    """Interpret blood test results using ADA / ICMR-WHO criteria."""
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


@app.delete("/api/v1/india-risk/history/{assessment_id}", response_model=DeleteResponse, tags=["india-risk-history"])
async def india_risk_history_delete(assessment_id: UUID, user: User, authorization: Annotated[str, Header()]):
    rows = await postgrest("DELETE", f"india_risk_assessments?id=eq.{assessment_id}", authorization, prefer="return=representation")
    return {"deleted": bool(rows)}

