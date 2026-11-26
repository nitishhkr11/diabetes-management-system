"""
Tests for the public screening model (Model 2 — NHANES).

These tests cover:
- Artifact loading and hash verification
- Prediction endpoint with valid inputs
- Prediction endpoint with minimal inputs (age + sex only)
- Validation reject on out-of-range age
- Leakage guard: forbidden lab features not in model features
- Metadata endpoint
- Evaluation endpoint
- FastAPI routes (skipped when shap/fitz are unavailable — same pre-existing gap)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Standalone inference module tests (no FastAPI, no shap dependency)
# ---------------------------------------------------------------------------

def test_public_artifacts_load():
    """Model artifact loads without error and has the required keys."""
    from src.public_predict import load_public_artifacts
    art = load_public_artifacts()
    assert art.pipeline is not None
    assert art.threshold > 0
    assert len(art.features) == 11
    assert art.model_name != ""
    assert art.model_version != ""


def test_public_artifacts_hash_matches_card():
    """SHA-256 of the joblib file matches the hash stored in model_card.json."""
    import hashlib
    model_path = ROOT / "models" / "public_screening" / "selected_model.joblib"
    card_path  = ROOT / "models" / "public_screening" / "model_card.json"
    card = json.loads(card_path.read_text())
    actual = hashlib.sha256(model_path.read_bytes()).hexdigest()
    assert actual == card["model_sha256"], (
        f"Artifact hash mismatch: card={card['model_sha256'][:16]}… actual={actual[:16]}…"
    )


def test_no_forbidden_lab_features():
    """
    Leakage guard: laboratory or target-derived features must NOT appear
    in the public screening model's feature list.
    """
    from src.public_predict import load_public_artifacts
    art = load_public_artifacts()
    forbidden = {
        "LBXGH", "lbxgh", "hba1c", "HbA1c",
        "DIQ010", "diq010", "diabetes_diagnosis",
        "glucose", "Glucose", "LBXGLU",
        "insulin", "Insulin", "LBXIN",
    }
    overlap = set(art.features) & forbidden
    assert not overlap, f"Forbidden lab features found in model: {overlap}"


def test_predict_full_inputs():
    """Prediction with all 11 inputs returns a valid result dict."""
    from src.public_predict import load_public_artifacts, predict_public
    art = load_public_artifacts()
    result = predict_public(art, {
        "age_years":         45.0,
        "sex_male":          1.0,
        "bmi":               28.5,
        "waist_cm":          95.0,
        "sys_bp":            130.0,
        "dia_bp":            82.0,
        "mod_days_per_week": 3.0,
        "vig_days_per_week": 1.0,
        "sedentary_min_day": 480.0,
        "smoked_100":        0.0,
        "current_smoker":    0.0,
    })
    assert result["ok"] is True
    assert 0.0 <= result["probability"] <= 1.0
    assert result["label"] in (0, 1)
    assert result["band"] in ("higher", "lower")
    assert result["model_type"] == "public_screening"
    assert isinstance(result["missing_inputs"], list)
    assert result["missing_inputs"] == []   # all supplied


def test_predict_minimal_inputs():
    """Prediction with only age and sex returns ok=True; others are imputed."""
    from src.public_predict import load_public_artifacts, predict_public
    art = load_public_artifacts()
    result = predict_public(art, {
        "age_years": 55.0,
        "sex_male":  0.0,
    })
    assert result["ok"] is True
    assert 0.0 <= result["probability"] <= 1.0
    # 9 optional features were not supplied → all in missing_inputs
    assert len(result["missing_inputs"]) == 9


def test_predict_invalid_age_low():
    """Age below minimum (21) should be rejected with an error."""
    from src.public_predict import load_public_artifacts, predict_public
    art = load_public_artifacts()
    result = predict_public(art, {
        "age_years": 15.0,  # below minimum 21
        "sex_male":  1.0,
    })
    assert result["ok"] is False
    assert any("age_years" in e for e in result.get("errors", []))


def test_predict_invalid_age_high():
    """Age above maximum (80) should be rejected with an error."""
    from src.public_predict import load_public_artifacts, predict_public
    art = load_public_artifacts()
    result = predict_public(art, {
        "age_years": 95.0,  # above maximum 80
        "sex_male":  0.0,
    })
    assert result["ok"] is False
    assert any("age_years" in e for e in result.get("errors", []))


def test_predict_disclaimer_present():
    """Every result includes a non-empty disclaimer string."""
    from src.public_predict import load_public_artifacts, predict_public
    art = load_public_artifacts()
    result = predict_public(art, {"age_years": 40.0, "sex_male": 1.0})
    assert "disclaimer" in result
    assert len(result["disclaimer"]) > 50


def test_get_public_metadata_shape():
    """get_public_metadata returns the expected keys."""
    from src.public_predict import load_public_artifacts, get_public_metadata
    art = load_public_artifacts()
    meta = get_public_metadata(art)
    for key in ("model_version", "model_name", "features", "threshold",
                "intended_use", "population", "test_metrics", "disclaimer"):
        assert key in meta, f"Missing key in metadata: {key}"


def test_get_public_evaluation_shape():
    """get_public_evaluation returns the expected keys."""
    from src.public_predict import load_public_artifacts, get_public_evaluation
    art = load_public_artifacts()
    ev = get_public_evaluation(art)
    for key in ("model_version", "model_name", "test_metrics", "features",
                "threshold", "figures_available"):
        assert key in ev, f"Missing key in evaluation: {key}"


def test_model_config_no_cross_contamination():
    """Public config and Pima config must reference separate artifacts."""
    from src import config as pima_c
    from src.public_config import PUBLIC_FEATURES, PUBLIC_MODELS_DIR, PUBLIC_REPORTS_DIR
    # Paths must be different directories
    assert str(PUBLIC_MODELS_DIR) != str(ROOT / "models"), \
        "Public model dir must NOT be the Pima models dir"
    # Feature schemas must be disjoint from Pima features
    pima_features = set(pima_c.FEATURES)
    public_features = set(PUBLIC_FEATURES)
    assert pima_features.isdisjoint(public_features), (
        f"Cross-contamination: shared features between Pima and public schemas: "
        f"{pima_features & public_features}"
    )


# ---------------------------------------------------------------------------
# FastAPI route tests (require httpx; skip if shap/fitz unavailable)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_client():
    """Return a TestClient for backend.main, or skip if deps unavailable."""
    try:
        from fastapi.testclient import TestClient
        from backend.main import app  # This import triggers shap; will skip if missing
        return TestClient(app, raise_server_exceptions=True)
    except ModuleNotFoundError as exc:
        pytest.skip(f"Backend test deps unavailable ({exc})")


def test_api_public_screening_metadata(api_client):
    r = api_client.get("/api/v1/public-screening/metadata")
    assert r.status_code == 200
    data = r.json()
    assert "model_version" in data
    assert "features" in data


def test_api_public_screening_prediction_valid(api_client):
    r = api_client.post("/api/v1/public-screening/predictions", json={
        "age_years": 50.0,
        "sex_male":  1.0,
        "bmi":       30.0,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "probability" in data
    assert data["band"] in ("higher", "lower")


def test_api_public_screening_prediction_age_too_low(api_client):
    r = api_client.post("/api/v1/public-screening/predictions", json={
        "age_years": 10.0,
        "sex_male":  1.0,
    })
    assert r.status_code == 422


def test_api_public_screening_prediction_forbidden_field(api_client):
    """Extra fields must be rejected (extra='forbid' in Pydantic model)."""
    r = api_client.post("/api/v1/public-screening/predictions", json={
        "age_years": 45.0,
        "sex_male":  1.0,
        "LBXGH": 6.5,       # HbA1c — forbidden
    })
    assert r.status_code == 422


def test_api_public_screening_evaluation(api_client):
    r = api_client.get("/api/v1/public-screening/evaluation")
    assert r.status_code == 200
    data = r.json()
    assert "test_metrics" in data
    assert "threshold" in data
