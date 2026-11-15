"""Inference: load the saved model, check user input, predict, explain.

Training and inference are separate on purpose: scripts/train.py creates the
files in models/, and this module only LOADS them. The app never retrains.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import numpy
import pandas
import scipy

from . import config as C
from .explain import PatientExplainer

REQUIRED = ["Pregnancies", "DiabetesPedigreeFunction", "Age"]   # cannot be "unknown"
CARD_NAME = "model_card.json"


class ArtifactError(RuntimeError):
    """Model files are missing or do not match their recorded SHA-256."""


def slug(name: str) -> str:
    return name.lower().replace(" ", "_")


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------- saving
def save_artifacts(fitted: dict, selected: str, card: dict, models_dir=C.MODELS_DIR) -> dict:
    """Write one joblib file per model plus model_card.json (with each file's SHA-256)."""
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, pipe in fitted.items():
        path = models_dir / f"{slug(name)}.joblib"
        joblib.dump(pipe, path)
        files[name] = {"file": path.name, "sha256": _sha256(path)}
    card = dict(card)
    card.update({
        "selected_model": selected,
        "features": list(C.FEATURES),
        "model_names": list(fitted),
        "model_version": files[selected]["sha256"][:12],
        "files": files,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "python_version": platform.python_version(),
        "package_versions": {"numpy": numpy.__version__, "pandas": pandas.__version__,
                             "scipy": scipy.__version__, "scikit-learn": sklearn.__version__,
                             "joblib": joblib.__version__},
    })
    (models_dir / CARD_NAME).write_text(json.dumps(card, indent=2))
    return card


# ------------------------------------------------------------------ loading
@dataclass
class Artifacts:
    pipelines: dict
    card: dict
    notes: list = field(default_factory=list)
    _explainer: PatientExplainer | None = None
    _background: pd.DataFrame | None = None

    @property
    def selected(self) -> str:
        return self.card["selected_model"]

    @property
    def pipeline(self):
        return self.pipelines[self.selected]

    @property
    def threshold(self) -> float:
        return float(self.card.get("threshold", C.DECISION_THRESHOLD))

    def set_background(self, background: pd.DataFrame | None) -> None:
        """Choose the rows SHAP compares each patient with (normally the training part)."""
        self._background = background
        self._explainer = None                      # rebuild the explainer on next use

    @property
    def explainer(self) -> PatientExplainer:
        if self._explainer is None:
            bg = self._background
            if bg is None:                  # fall back to a synthetic median patient
                bg = pd.DataFrame([{f: self.card["profile"][f]["median"] for f in C.FEATURES}])
            self._explainer = PatientExplainer(self.pipeline, bg)
        return self._explainer


def load_artifacts(models_dir=C.MODELS_DIR, background: pd.DataFrame | None = None,
                   allow_unverified_dataset: bool = False) -> Artifacts:
    models_dir = Path(models_dir)
    card_path = models_dir / CARD_NAME
    if not card_path.exists():
        raise ArtifactError(f"{card_path} not found. Train first: python scripts/train.py")
    try:
        card = json.loads(card_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ArtifactError(f"{card_path} is unreadable or invalid JSON: {exc}") from exc
    if card.get("features") != C.FEATURES:
        raise ArtifactError("Model card feature order does not match the application schema; retrain with python scripts/train.py.")
    model_names = card.get("model_names", [])
    if (not set(C.MODEL_ORDER).issubset(model_names)
            or card.get("selected_model") not in model_names):
        raise ArtifactError("Model card is missing an approved benchmark model or has an invalid selected model.")
    installed = {"numpy": numpy.__version__, "pandas": pandas.__version__, "scipy": scipy.__version__,
                 "scikit-learn": sklearn.__version__, "joblib": joblib.__version__}
    recorded_python = ".".join(str(x) for x in sys.version_info[:2])
    artifact_python = ".".join(str(card.get("python_version", "")).split(".")[:2])
    if artifact_python != recorded_python:
        raise ArtifactError(f"Artifacts were trained with Python {artifact_python}, but runtime has {recorded_python}; use Python 3.11.")
    recorded = card.get("package_versions", {})
    for package, version in installed.items():
        if recorded.get(package) != version:
            raise ArtifactError(f"Artifacts require {package} {recorded.get(package)}, but runtime has {version}; install the pinned requirements.")
    fingerprint = card.get("dataset", {}).get("canonical_sha256")
    if not fingerprint:
        raise ArtifactError("Model card is missing the training data fingerprint.")
    if not allow_unverified_dataset and fingerprint != C.KNOWN_CANONICAL_SHA256:
        raise ArtifactError("Model artifact training data fingerprint is not the verified Pima dataset; refusing inference.")
    pipelines, notes = {}, []
    if set(card.get("files", {})) != set(model_names):
        raise ArtifactError("Model card model list does not match its artifact manifest.")
    for name in model_names:
        info = card["files"][name]
        path = models_dir / info["file"]
        if not path.exists():
            raise ArtifactError(f"Missing model file {path}")
        if _sha256(path) != info["sha256"]:      # check BEFORE unpickling
            raise ArtifactError(f"{path.name} does not match its recorded SHA-256 - refusing to load it.")
        pipelines[name] = joblib.load(path)
        if list(getattr(pipelines[name], "feature_names_in_", [])) != C.FEATURES:
            raise ArtifactError(f"{path.name} feature schema does not match the application; retrain the release artifacts.")
    return Artifacts(pipelines=pipelines, card=card, notes=notes, _background=background)


# ------------------------------------------------------------------- inputs
def check_inputs(raw: dict, profile: dict | None = None):
    """Validate user input. Returns (row_df, errors, warnings). Errors block prediction."""
    errors, warnings = [], []
    values = {}
    for feat in C.FEATURES:
        v = raw.get(feat)
        v = None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)
        if feat in C.ZERO_AS_MISSING and v == 0:      # same rule as in training
            v = None
        if v is None:
            if feat in REQUIRED:
                errors.append(f"{C.FEATURE_LABELS[feat]} is required.")
            else:
                med = f" (training median {profile[feat]['median']:.1f} will be used)" if profile else ""
                warnings.append(f"{feat} not provided{med}.")
        else:
            lo, hi = C.HARD_LIMITS[feat]
            if not lo <= v <= hi:
                errors.append(f"{feat} = {v:g} is outside the allowed range {lo}-{hi}.")
            elif profile and not profile[feat]["min"] <= v <= profile[feat]["max"]:
                warnings.append(f"{feat} = {v:g} is outside the range seen in training "
                                f"({profile[feat]['min']:g}-{profile[feat]['max']:g}); "
                                "the model is extrapolating - treat the score with extra caution.")
        values[feat] = np.nan if v is None else v
    n_unknown = sum(np.isnan(values[f]) for f in C.ZERO_AS_MISSING)
    if n_unknown >= 3:
        warnings.append(f"{n_unknown} of 5 measurements are unknown - the score is mostly based on "
                        "average values and is not reliable.")
    row = pd.DataFrame([values], columns=C.FEATURES).astype("float64")
    return row, errors, warnings


def risk_band(p: float, threshold: float) -> str:
    """Model-score bands (NOT clinical risk classes)."""
    if p >= threshold:
        return "Higher"
    return "Intermediate" if p >= threshold / 2 else "Lower"


# --------------------------------------------------------------- prediction
def predict_one(art: Artifacts, raw: dict, explain: bool = True) -> dict:
    row, errors, warnings = check_inputs(raw, art.card.get("profile"))
    if errors:
        return {"ok": False, "errors": errors, "warnings": warnings}
    p = float(art.pipeline.predict_proba(row)[0, 1])
    out = {
        "ok": True, "errors": [], "warnings": warnings,
        "probability": p, "threshold": art.threshold,
        "label": int(p >= art.threshold), "band": risk_band(p, art.threshold),
        "model": art.selected, "model_version": art.card["model_version"],
        "inputs": {f: (None if np.isnan(row.iloc[0][f]) else float(row.iloc[0][f])) for f in C.FEATURES},
        "all_models": {name: float(pipe.predict_proba(row)[0, 1]) for name, pipe in art.pipelines.items()},
    }
    if explain:
        out["explanation"] = art.explainer.explain_one(row)
    return out
