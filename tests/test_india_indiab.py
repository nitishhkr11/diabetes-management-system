"""
Tests for the India-focused ICMR-INDIAB upgrade (Model 3).

Uses clearly labelled synthetic software test fixtures ONLY in-memory;
never writes fake models to models/india_indiab/ and never modifies
existing Pima or NHANES artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def _make_software_fixture_df(n: int = 240, seed: int = 42) -> pd.DataFrame:
    """Create a purely synthetic software test fixture for pipeline unit tests."""
    rng = np.random.default_rng(seed)
    psu_ids = [f"PSU_{i // 12}" for i in range(n)]
    strata = [f"STR_{i % 4}" for i in range(n)]
    ages = rng.integers(20, 80, size=n)
    sex = rng.choice(["male", "female"], size=n)
    residence = rng.choice(["rural", "urban"], size=n)
    states = rng.choice(["StateA", "StateB"], size=n)
    bmi = rng.normal(25.0, 4.5, size=n).clip(15, 45)
    waist = rng.normal(88.0, 12.0, size=n).clip(55, 140)
    whr = (waist / 165.0).clip(0.35, 0.90)
    sys_bp = rng.normal(126.0, 16.0, size=n).clip(85, 200)
    dia_bp = rng.normal(80.0, 10.0, size=n).clip(50, 120)
    fam_hx = rng.choice(["yes", "no"], size=n, p=[0.25, 0.75])

    # Outcome constructed via WHO glucose rules (kept strictly separate from features)
    logit = -4.2 + 0.045 * ages + 0.08 * (bmi - 24.0) + 0.7 * (fam_hx == "yes")
    prob = 1.0 / (1.0 + np.exp(-logit))
    is_pos = rng.binomial(1, prob)
    fbg = np.where(is_pos == 1, rng.uniform(126, 210, size=n), rng.uniform(75, 115, size=n))
    ogtt = np.where(is_pos == 1, rng.uniform(200, 300, size=n), rng.uniform(90, 160, size=n))
    self_rep = np.where((is_pos == 1) & (rng.random(n) < 0.4), 1, 0)

    df = pd.DataFrame({
        "participant_id": [f"FIXTURE_{i}" for i in range(n)],
        "psu_id": psu_ids,
        "stratum_id": strata,
        "survey_weight": rng.uniform(0.5, 2.5, size=n),
        "age_years": ages,
        "sex": sex,
        "residence_type": residence,
        "state_region": states,
        "bmi": bmi,
        "waist_cm": waist,
        "waist_height_ratio": whr,
        "sys_bp": sys_bp,
        "dia_bp": dia_bp,
        "family_history_diabetes": fam_hx,
        "physical_activity_score": rng.uniform(0, 600, size=n),
        "tobacco_use": rng.choice(["yes", "no"], size=n),
        "alcohol_use": rng.choice(["yes", "no"], size=n),
        "education_level": rng.choice(["primary", "secondary", "graduate"], size=n),
        "ses_indicator": rng.choice(["low", "middle", "high"], size=n),
        "fasting_glucose": fbg,
        "post_load_glucose_2h": ogtt,
        "self_reported_diabetes": self_rep,
    })
    # Inject realistic missingness in predictors (never zero-filled)
    df.loc[df.index[:8], "waist_cm"] = np.nan
    df.loc[df.index[8:14], "bmi"] = np.nan
    return df


# ---------------------------------------------------------------------------
# 1. Governance, manifest, and dataset audit tests
# ---------------------------------------------------------------------------

def test_indiab_manifest_status_is_honest():
    from src.india_predict import get_india_status
    st = get_india_status()
    assert st["ready"] is False
    assert st["permission_status"] == "NOT REQUESTED"
    assert "External validation has not yet been completed." in st["external_validation"]


def test_audit_blocks_when_permission_not_granted():
    from scripts.audit_indiab_dataset import audit_dataframe
    df = _make_software_fixture_df(60)
    res = audit_dataframe(df, {"permission_status": "NOT REQUESTED"}, require_permission=True)
    assert res["audit_passed"] is False
    assert any("NOT REQUESTED" in b for b in res["blockers"])


def test_audit_checks_schema_target_missingness_and_age():
    from scripts.audit_indiab_dataset import audit_dataframe
    df = _make_software_fixture_df(80)
    df.loc[0, "age_years"] = 18  # under 20 must be flagged
    res = audit_dataframe(df, {"permission_status": "DATA RECEIVED"}, require_permission=True)
    assert res["audit_passed"] is True
    assert res["age_coverage"]["under_20_count"] == 1
    assert res["feature_availability"]["waist_cm"]["missing_pct"] > 0
    assert res["survey_design"]["psu_id"]["present"] is True
    assert res["target_summary"]["positive"] > 0
    assert res["target_summary"]["negative"] > 0


def test_who_target_excludes_leakage_from_candidate_features():
    from src import india_config as IC
    overlap = set(IC.INDIA_ALL_CANDIDATE_FEATURES) & IC.FORBIDDEN_LEAKAGE_VARIABLES
    assert not overlap, f"Leakage variables in candidate predictors: {overlap}"


# ---------------------------------------------------------------------------
# 2. ML pipeline tests (on in-memory software fixture only; save_artifacts=False)
# ---------------------------------------------------------------------------

def test_india_training_pipeline_cluster_safe_and_independent():
    from scripts.train_india_model import train_on_dataframe
    df = _make_software_fixture_df(240, seed=42)
    res = train_on_dataframe(
        df,
        {"permission_status": "DATA VERIFIED", "dataset_name": "SOFTWARE_FIXTURE"},
        allow_fixture=True,
        save_artifacts=False,
    )
    assert res["selected_model"] in {"Logistic Regression", "Random Forest", "Gradient Boosting"}
    assert len(res["comparison"]) == 3
    # Ensure each model has its own independent evaluation record
    models_seen = {row["model"] for row in res["comparison"]}
    assert models_seen == {"Logistic Regression", "Random Forest", "Gradient Boosting"}
    m = res["selected_test_metrics"]
    for k in ("accuracy", "balanced_accuracy", "sensitivity_recall", "specificity", "precision", "npv", "f1", "roc_auc", "pr_auc", "brier"):
        assert k in m
    assert res["external_validation"] == "External validation has not yet been completed."
    assert "sex" in res["subgroups"]
    assert "age_group" in res["subgroups"]
    assert "residence_type" in res["subgroups"]


def test_india_training_reproducible_with_fixed_seed():
    from scripts.train_india_model import train_on_dataframe
    df = _make_software_fixture_df(200, seed=99)
    r1 = train_on_dataframe(df, {"permission_status": "DATA VERIFIED"}, allow_fixture=True, save_artifacts=False, random_state=42)
    r2 = train_on_dataframe(df, {"permission_status": "DATA VERIFIED"}, allow_fixture=True, save_artifacts=False, random_state=42)
    assert r1["selected_test_metrics"] == r2["selected_test_metrics"]


def test_india_training_refuses_without_permission():
    from scripts.train_india_model import train_on_dataframe
    df = _make_software_fixture_df(120)
    with pytest.raises(RuntimeError, match="audit failed"):
        train_on_dataframe(df, {"permission_status": "NOT REQUESTED"}, allow_fixture=False, save_artifacts=False)


# ---------------------------------------------------------------------------
# 3. API tests (unavailable status, metadata, validation, existing endpoints intact)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from backend.main import app
    return TestClient(app, raise_server_exceptions=False)


def test_api_india_status_and_metadata(client):
    r_status = client.get("/api/v1/india-screening/status")
    assert r_status.status_code == 200
    data = r_status.json()
    assert data["ready"] is False
    assert data["permission_status"] == "NOT REQUESTED"
    assert "under development" in data["status_message"]

    r_meta = client.get("/api/v1/india-screening/metadata")
    assert r_meta.status_code == 200
    assert r_meta.json()["ready"] is False

    r_eval = client.get("/api/v1/india-screening/evaluation")
    assert r_eval.status_code == 200
    assert r_eval.json()["available"] is False


def test_api_india_prediction_returns_503_unavailable(client):
    r = client.post("/api/v1/india-screening/predictions", json={
        "age_years": 35,
        "sex": "female",
        "bmi": 24.5,
    })
    assert r.status_code == 503
    assert r.json()["detail"]["available"] is False


def test_api_india_prediction_rejects_under_20(client):
    r = client.post("/api/v1/india-screening/predictions", json={
        "age_years": 19,
        "sex": "male",
    })
    assert r.status_code == 422


def test_api_india_history_requires_auth(client):
    r = client.get("/api/v1/india-screening/history")
    assert r.status_code == 401


def test_api_nhanes_preserved_and_relabeled(client):
    r = client.get("/api/v1/public-screening/metadata")
    assert r.status_code == 200
    assert r.json()["model_label"] == "US population research benchmark"

    ev = client.get("/api/v1/public-screening/evaluation")
    assert ev.status_code == 200
    body = ev.json()
    assert len(body["roc_curve"]) > 0
    assert len(body["pr_curve"]) > 0
    assert len(body["model_comparison"]) > 0


# ---------------------------------------------------------------------------
# 4. Frontend source checks (labels, no false India validation claims)
# ---------------------------------------------------------------------------

def test_frontend_labels_and_disclaimers_present():
    screening_src = (ROOT / "frontend" / "src" / "app" / "screening" / "page.tsx").read_text(encoding="utf-8")
    research_src = (ROOT / "frontend" / "src" / "app" / "research" / "page.tsx").read_text(encoding="utf-8")
    datasets_src = (ROOT / "frontend" / "src" / "app" / "datasets" / "page.tsx").read_text(encoding="utf-8")

    assert "India-specific model is under development" in screening_src
    assert "US population research benchmark" in screening_src
    assert "External validation has not yet been completed." in screening_src

    assert "Historical Pima research benchmark" in research_src
    assert "US population research benchmark" in research_src
    assert "ResponsiveContainer" in research_src

    assert "ICMR-INDIAB" in datasets_src
    assert "LASI" in datasets_src
    assert "External validation has not yet been completed." in datasets_src
