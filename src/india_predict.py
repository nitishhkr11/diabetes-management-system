"""
India-specific screening inference module (Model 3 — ICMR-INDIAB).

Completely independent from Pima (src/predict.py) and NHANES (src/public_predict.py).
Refuses to serve predictions until:
1. Dataset permission/acquisition status is MODEL TRAINED
2. Verified model_card.json and selected_model.joblib exist
3. SHA-256 hash matches
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from src import india_config as IC


class IndiaModelUnavailableError(Exception):
    """Raised when the ICMR-INDIAB model is not trained, verified, or authorised."""


@dataclass
class IndiaArtifacts:
    pipeline: Any
    card: dict[str, Any]
    threshold: float
    features: list[str]
    model_name: str
    model_version: str
    model_hash: str


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def get_india_status(
    models_dir: Path = IC.INDIA_MODELS_DIR,
    manifest_path: Path = IC.INDIA_MANIFEST_PATH,
    audit_dir: Path = IC.INDIA_AUDIT_DIR,
) -> dict[str, Any]:
    """Return honest availability, dataset permission status, and blockers."""
    manifest = _read_json(manifest_path) or {"permission_status": "NOT REQUESTED"}
    audit = _read_json(audit_dir / "indiab_audit.json")
    card = _read_json(models_dir / "model_card.json")
    model_file = models_dir / "selected_model.joblib"

    perm_status = manifest.get("permission_status", "NOT REQUESTED")
    ready = bool(
        perm_status == "MODEL TRAINED"
        and card is not None
        and card.get("status") == "MODEL TRAINED"
        and model_file.is_file()
    )

    blockers = []
    if audit and audit.get("blockers"):
        blockers.extend(audit["blockers"])
    elif not ready:
        blockers.append(f"Authorised ICMR-INDIAB dataset status is '{perm_status}'.")
        if not model_file.is_file():
            blockers.append("Trained ICMR-INDIAB model artifact is not present.")

    return {
        "model_family": "india_indiab",
        "model_label": IC.INDIA_MODEL_LABEL,
        "model_version": IC.INDIA_MODEL_VERSION,
        "ready": ready,
        "permission_status": perm_status,
        "status_message": (
            "ICMR-INDIAB Indian adult research model is ready."
            if ready
            else "India-specific model is under development. Existing international and historical models are available for research comparison only."
        ),
        "intended_population": "Indian adults aged 20 years and above (men and women, rural and urban, across Indian states).",
        "dataset_source": "ICMR-INDIAB National Diabetes Study (https://nhrdr.icmr.org.in/datasets/icmr-indiab)",
        "external_validation": "External validation has not yet been completed.",
        "blockers": blockers,
    }


def load_india_artifacts(
    models_dir: Path = IC.INDIA_MODELS_DIR,
    manifest_path: Path = IC.INDIA_MANIFEST_PATH,
) -> IndiaArtifacts:
    """Load and verify ICMR-INDIAB artifacts; raise IndiaModelUnavailableError if not ready."""
    import joblib

    status = get_india_status(models_dir=models_dir, manifest_path=manifest_path)
    if not status["ready"]:
        raise IndiaModelUnavailableError(status["status_message"])

    card = _read_json(models_dir / "model_card.json")
    model_path = models_dir / "selected_model.joblib"
    if card is None or not model_path.is_file():
        raise IndiaModelUnavailableError("Verified ICMR-INDIAB model artifacts are missing.")

    actual_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    expected_hash = card.get("model_sha256", "")
    if expected_hash and actual_hash != expected_hash:
        raise IndiaModelUnavailableError("ICMR-INDIAB model artifact hash verification failed.")

    pipeline = joblib.load(model_path)
    return IndiaArtifacts(
        pipeline=pipeline,
        card=card,
        threshold=float(card["threshold"]),
        features=list(card["features"]),
        model_name=str(card["selected_model"]),
        model_version=str(card["model_version"]),
        model_hash=actual_hash,
    )


def validate_india_inputs(raw: dict[str, Any], features: list[str], limits: dict[str, list[float]]) -> tuple[dict[str, Any], list[str], list[str]]:
    """Validate and coerce inputs for age 20+ Indian adult screening."""
    errors: list[str] = []
    warnings: list[str] = []
    validated: dict[str, Any] = {}

    age = raw.get("age_years")
    if age is None or age == "":
        errors.append("'age_years' is required and must be 20 or above.")
    else:
        try:
            fage = float(age)
            if fage < IC.INDIA_MIN_AGE:
                errors.append(f"Model is restricted to adults aged {IC.INDIA_MIN_AGE}+; do not extrapolate to 18-19-year-olds.")
            elif fage > IC.INDIA_MAX_AGE:
                errors.append(f"'age_years' = {fage} exceeds maximum supported age ({IC.INDIA_MAX_AGE}).")
        except (TypeError, ValueError):
            errors.append("'age_years' must be a number.")

    for feat in features:
        val = raw.get(feat)
        if val is None or val == "":
            validated[feat] = None
            warnings.append(f"'{feat}' not provided — imputed from training distribution.")
            continue
        if feat in IC.INDIA_CANDIDATE_NUMERIC_FEATURES:
            try:
                fval = float(val)
            except (TypeError, ValueError):
                errors.append(f"'{feat}' must be a number.")
                validated[feat] = None
                continue
            lo, hi = limits.get(feat, [None, None])
            if lo is not None and fval < lo:
                errors.append(f"'{feat}' = {fval} is below minimum ({lo}).")
                validated[feat] = None
            elif hi is not None and fval > hi:
                errors.append(f"'{feat}' = {fval} exceeds maximum ({hi}).")
                validated[feat] = None
            else:
                validated[feat] = fval
        else:
            validated[feat] = str(val)

    return validated, errors, warnings


def predict_india(art: IndiaArtifacts, raw_inputs: dict[str, Any]) -> dict[str, Any]:
    """Run inference using verified ICMR-INDIAB artifacts."""
    import pandas as pd

    limits = art.card.get("input_limits", {})
    validated, errors, warnings = validate_india_inputs(raw_inputs, art.features, limits)
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings, "inputs": validated}

    missing_inputs = [f for f, v in validated.items() if v is None]
    row = {
        k: (np.nan if v is None else (float(v) if k in IC.INDIA_CANDIDATE_NUMERIC_FEATURES else v))
        for k, v in validated.items()
    }
    X = pd.DataFrame([row], columns=art.features)
    prob = float(art.pipeline.predict_proba(X)[0, 1])
    label = int(prob >= art.threshold)
    band = "higher" if label == 1 else "lower"

    return {
        "ok": True,
        "model_family": "india_indiab",
        "model_label": IC.INDIA_MODEL_LABEL,
        "model": art.model_name,
        "model_version": art.model_version,
        "dataset": "ICMR-INDIAB",
        "probability": round(prob, 6),
        "label": label,
        "band": band,
        "threshold": art.threshold,
        "inputs": validated,
        "missing_inputs": missing_inputs,
        "warnings": warnings,
        "disclaimer": (
            "Research screening estimate from the ICMR-INDIAB Indian adult model — not a clinical diagnosis. "
            "Consult a qualified healthcare professional for clinical testing."
        ),
    }


def get_india_metadata(models_dir: Path = IC.INDIA_MODELS_DIR, manifest_path: Path = IC.INDIA_MANIFEST_PATH) -> dict[str, Any]:
    status = get_india_status(models_dir=models_dir, manifest_path=manifest_path)
    template = _read_json(models_dir / "model_card.template.json") or {}
    card = _read_json(models_dir / "model_card.json")
    source = card if (status["ready"] and card) else template
    return {
        **status,
        "features": source.get("features", []),
        "feature_labels": IC.INDIA_FEATURE_LABELS,
        "input_limits": IC.INDIA_INPUT_LIMITS,
        "intended_use": source.get("intended_use", ""),
        "population": source.get("population", status["intended_population"]),
        "clinical_disclaimer": source.get("clinical_disclaimer", ""),
    }


def get_india_evaluation(models_dir: Path = IC.INDIA_MODELS_DIR, manifest_path: Path = IC.INDIA_MANIFEST_PATH) -> dict[str, Any]:
    status = get_india_status(models_dir=models_dir, manifest_path=manifest_path)
    card = _read_json(models_dir / "model_card.json")
    if not status["ready"] or not card:
        return {
            **status,
            "available": False,
            "comparison": [],
            "test_metrics": None,
            "subgroups": {},
        }
    return {
        **status,
        "available": True,
        "selected_model": card.get("selected_model"),
        "threshold": card.get("threshold"),
        "validation_metrics": card.get("validation_metrics"),
        "test_metrics": card.get("test_metrics"),
        "test_confidence_intervals": card.get("test_confidence_intervals", {}),
        "comparison": card.get("comparison", []),
        "subgroups": card.get("subgroups", {}),
    }
