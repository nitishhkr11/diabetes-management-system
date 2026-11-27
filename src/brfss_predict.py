"""
CDC BRFSS Research Benchmark reader module (UCI Dataset ID 891).

Completely independent from Pima, NHANES, and ICMR-INDIAB.
Serves real stored evaluation metrics, curves, confusion matrices, and feature importances.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BRFSS_MODELS_DIR = ROOT / "models" / "brfss_benchmark"
BRFSS_REPORTS_DIR = ROOT / "reports" / "brfss_benchmark"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        out = []
        for row in csv.DictReader(f):
            parsed: dict[str, Any] = {}
            for k, v in row.items():
                try:
                    parsed[k] = round(float(v), 5)
                except (TypeError, ValueError):
                    parsed[k] = v
            out.append(parsed)
        return out


def get_brfss_metadata(
    models_dir: Path = BRFSS_MODELS_DIR,
) -> dict[str, Any]:
    card = _read_json(models_dir / "model_card.json")
    if not card:
        return {
            "available": False,
            "model_version": "brfss_v1",
            "model_label": "Large US survey research benchmark (CDC BRFSS)",
            "message": "BRFSS benchmark artifacts not yet generated.",
        }
    return {
        "available": True,
        "model_version": card.get("model_version", "brfss_v1"),
        "model_label": card.get("model_label", "Large US survey research benchmark (CDC BRFSS)"),
        "selected_model": card.get("selected_model"),
        "selection_reasoning": card.get("selection_reasoning"),
        "trained_at": card.get("trained_at"),
        "dataset": card.get("dataset", {}),
        "limitation_statement": card.get("limitation_statement", ""),
    }


def get_brfss_evaluation(
    models_dir: Path = BRFSS_MODELS_DIR,
    reports_dir: Path = BRFSS_REPORTS_DIR,
) -> dict[str, Any]:
    card = _read_json(models_dir / "model_card.json")
    if not card:
        return {
            "available": False,
            "model_version": "brfss_v1",
            "model_label": "Large US survey research benchmark (CDC BRFSS)",
        }
    return {
        "available": True,
        "model_version": card.get("model_version", "brfss_v1"),
        "model_label": card.get("model_label"),
        "selected_model": card.get("selected_model"),
        "selection_reasoning": card.get("selection_reasoning"),
        "trained_at": card.get("trained_at"),
        "dataset": card.get("dataset", {}),
        "limitation_statement": card.get("limitation_statement", ""),
        "models": card.get("models", {}),
        "model_comparison": _read_csv(reports_dir / "model_comparison.csv"),
        "confusion_matrices": _read_json(reports_dir / "confusion_matrices.json") or {},
        "roc_curves": _read_json(reports_dir / "roc_curves.json") or {},
        "pr_curves": _read_json(reports_dir / "pr_curves.json") or {},
        "feature_importance": _read_csv(reports_dir / "feature_importance.csv"),
    }
