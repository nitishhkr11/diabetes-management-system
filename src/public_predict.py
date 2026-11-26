"""
Public Screening Model — inference module.

Completely independent from the existing Pima pipeline.
Loads models/public_screening/selected_model.joblib

Feature schema is fixed at import time from the model card.
Never trains during inference.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_MODELS_DIR = ROOT / "models" / "public_screening"
PUBLIC_REPORTS_DIR = ROOT / "reports" / "public_screening"

# Human-readable labels for the screening result bands
BAND_LABELS = {
    "higher": "Higher likelihood",
    "lower":  "Lower likelihood",
}

SCREENING_DISCLAIMER = (
    "This estimate is based on a research model trained on a US population survey dataset. "
    "It reflects patterns in the data, not a clinical diagnosis. A higher estimate means "
    "some measured values are more common in the survey-defined diabetes group — it does "
    "not mean you have or will develop diabetes. Consult a qualified healthcare provider "
    "for clinical assessment."
)


class PublicModelError(Exception):
    """Raised when the public screening artifacts cannot be loaded or verified."""


@dataclass
class PublicArtifacts:
    pipeline: Any          # sklearn Pipeline
    card: dict             # model_card.json
    threshold: float
    features: list[str]
    model_name: str
    model_version: str
    model_hash: str


@lru_cache(maxsize=1)
def load_public_artifacts(models_dir: str = str(PUBLIC_MODELS_DIR)) -> PublicArtifacts:
    """
    Load and verify the public screening artifacts.
    Cached after first load — raises PublicModelError if anything is wrong.
    """
    import joblib

    models_path = Path(models_dir)
    card_path = models_path / "model_card.json"
    model_path = models_path / "selected_model.joblib"

    if not card_path.exists():
        raise PublicModelError(f"Public model card not found: {card_path}")
    if not model_path.exists():
        raise PublicModelError(f"Public model artifact not found: {model_path}")

    card = json.loads(card_path.read_text())

    # Verify artifact hash
    actual_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    expected_hash = card.get("model_sha256", "")
    if expected_hash and actual_hash != expected_hash:
        raise PublicModelError(
            f"Public model artifact hash mismatch. "
            f"Expected {expected_hash[:16]}... got {actual_hash[:16]}..."
        )

    pipeline = joblib.load(model_path)

    return PublicArtifacts(
        pipeline=pipeline,
        card=card,
        threshold=float(card["threshold"]),
        features=card["features"],
        model_name=card["selected_model"],
        model_version=card["model_version"],
        model_hash=actual_hash,
    )


def validate_public_inputs(raw: dict, features: list[str],
                            limits: dict) -> tuple[dict, list[str], list[str]]:
    """
    Validate and coerce public screening inputs.

    Returns:
        (validated_dict, errors, warnings)

    validated_dict values are float or None (for optional/missing fields).
    """
    errors: list[str] = []
    warnings: list[str] = []
    validated: dict = {}

    for feat in features:
        val = raw.get(feat)
        lo, hi = limits.get(feat, (None, None))

        if val is None or val == "":
            # Missing — allowed, model handles via imputation
            validated[feat] = None
            warnings.append(f"'{feat}' not provided — will be imputed from training data median.")
            continue

        try:
            fval = float(val)
        except (TypeError, ValueError):
            errors.append(f"'{feat}' must be a number.")
            validated[feat] = None
            continue

        if lo is not None and fval < lo:
            errors.append(f"'{feat}' = {fval} is below the minimum allowed value ({lo}).")
            validated[feat] = None
        elif hi is not None and fval > hi:
            errors.append(f"'{feat}' = {fval} exceeds the maximum allowed value ({hi}).")
            validated[feat] = None
        else:
            validated[feat] = fval

    return validated, errors, warnings


def predict_public(
    art: PublicArtifacts,
    raw_inputs: dict,
    *,
    suppress_imputation_warnings: bool = False,
) -> dict:
    """
    Run public screening prediction.

    Returns a prediction dict with:
      - ok: bool
      - probability: float (calibrated score, NOT a clinical probability)
      - label: 0 or 1
      - band: str ("higher" / "lower")
      - threshold: float
      - model: str
      - model_version: str
      - inputs: dict (the validated input values)
      - missing_inputs: list[str]
      - errors: list[str]
      - warnings: list[str]
      - disclaimer: str
    """
    limits = art.card.get("input_limits", {})
    validated, errors, warnings = validate_public_inputs(
        raw_inputs, art.features, limits
    )

    if errors:
        return {
            "ok": False,
            "errors": errors,
            "warnings": warnings,
            "inputs": validated,
        }

    missing_inputs = [f for f, v in validated.items() if v is None]

    # Build feature array for sklearn pipeline
    # Pipeline handles NaN via its own imputer
    import numpy as np
    import pandas as pd
    # Replace None → np.nan and coerce to float64 so the imputer can process them
    row = {k: np.nan if v is None else float(v) for k, v in validated.items()}
    X = pd.DataFrame([row], columns=art.features, dtype=float)

    try:
        prob = float(art.pipeline.predict_proba(X)[0, 1])
    except Exception as exc:
        return {
            "ok": False,
            "errors": [f"Prediction failed: {exc}"],
            "warnings": warnings,
            "inputs": validated,
        }

    label = int(prob >= art.threshold)
    band  = "higher" if label == 1 else "lower"

    # Sanitize inputs for response (never log raw values in production)
    safe_inputs = {k: (round(v, 4) if v is not None else None) for k, v in validated.items()}

    return {
        "ok": True,
        "probability": round(prob, 6),
        "label": label,
        "band": band,
        "band_label": BAND_LABELS[band],
        "threshold": art.threshold,
        "model": art.model_name,
        "model_version": art.model_version,
        "model_type": "public_screening",
        "dataset": "NHANES 2017-2018",
        "inputs": safe_inputs,
        "missing_inputs": missing_inputs,
        "warnings": warnings,
        "disclaimer": SCREENING_DISCLAIMER,
        "population_note": art.card.get("population", ""),
    }


def get_public_metadata(art: PublicArtifacts) -> dict:
    """Return public-facing metadata for the screening model."""
    card = art.card
    return {
        "model_version": art.model_version,
        "model_name": art.model_name,
        "model_type": "public_screening",
        "dataset": card.get("dataset", {}),
        "features": art.features,
        "feature_labels": card.get("feature_labels", {}),
        "input_limits": card.get("input_limits", {}),
        "threshold": art.threshold,
        "threshold_selection": card.get("threshold_selection", ""),
        "intended_use": card.get("intended_use", ""),
        "population": card.get("population", ""),
        "population_limitations": card.get("population_limitations", []),
        "trained_at": card.get("trained_at", ""),
        "sklearn_version": card.get("sklearn_version", ""),
        "test_metrics": card.get("test_metrics", {}),
        "test_confidence_intervals": card.get("test_confidence_intervals", {}),
        "calibration_bins": card.get("calibration_bins", []),
        "disclaimer": SCREENING_DISCLAIMER,
    }


def get_public_evaluation(art: PublicArtifacts) -> dict:
    """Return evaluation data for the research/interviewer dashboard."""
    card = art.card
    return {
        "model_version": art.model_version,
        "model_name": art.model_name,
        "dataset": card.get("dataset", {}),
        "target_definition": card.get("target_definition", {}),
        "test_metrics": card.get("test_metrics", {}),
        "test_confidence_intervals": card.get("test_confidence_intervals", {}),
        "calibration_bins": card.get("calibration_bins", []),
        "features": art.features,
        "feature_labels": card.get("feature_labels", {}),
        "population": card.get("population", ""),
        "population_limitations": card.get("population_limitations", []),
        "protocol": card.get("cv_selection", ""),
        "selection_rule": card.get("selection_rule", ""),
        "threshold": art.threshold,
        "figures_available": [
            f.name for f in PUBLIC_REPORTS_DIR.glob("figures/*.png")
        ] if PUBLIC_REPORTS_DIR.exists() else [],
    }
