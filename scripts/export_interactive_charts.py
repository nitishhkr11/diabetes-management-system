"""Export verified, interactive chart points for the frozen model release.

This script reconstructs the documented nominal holdout predictions only to
serialize their ROC points. It does not fit, select, or tune any model.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve

from src.config import DATA_PATH, ROOT
from src.predict import load_artifacts
from src.preprocessing import split_data


def write_interactive_chart_data(*, model_version: str, model: str, threshold: float,
                                 roc_auc: float, roc_points: list[dict],
                                 confusion_matrix: dict, calibration_bins: list[dict],
                                 shap_units: str, shap_importance: list[dict],
                                 destination: Path | None = None) -> Path:
    payload = {
        "model_version": model_version,
        "model": model,
        "threshold": float(threshold),
        "roc_auc": float(roc_auc),
        "roc_points": roc_points,
        "confusion_matrix": confusion_matrix,
        "calibration_bins": calibration_bins,
        "shap_units": shap_units,
        "shap_importance": shap_importance,
        "provenance": "From the release's documented nominal holdout predictions; descriptive visualization only. The nominal holdout has historical repository exposure and is not confirmatory.",
    }
    destination = destination or ROOT / "reports" / "interactive_charts.json"
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return destination


def export_chart_data() -> Path:
    art = load_artifacts()
    frame = pd.read_csv(DATA_PATH)
    X_train, X_test, _, y_test = split_data(frame)
    probability = art.pipeline.predict_proba(X_test)[:, 1]
    auc = float(roc_auc_score(y_test, probability))
    saved_test = next((row for row in art.card.get("test_table", [])
                       if row.get("model") == art.selected), None)
    if saved_test is None or not np.isclose(auc, saved_test["roc_auc"], atol=1e-12):
        raise RuntimeError("Reconstructed ROC-AUC does not match this release's saved test metric.")

    fpr, tpr, thresholds = roc_curve(y_test, probability, drop_intermediate=False)
    art.set_background(X_train)
    shap = art.explainer.global_importance(X_test)
    stored_shap = pd.read_csv(ROOT / "reports" / "shap_global_importance.csv")
    checked_shap = shap.merge(stored_shap, on="feature", suffixes=("_new", "_saved"))
    if len(checked_shap) != len(shap) or not np.allclose(
        checked_shap["mean_abs_shap_new"], checked_shap["mean_abs_shap_saved"], rtol=1e-8, atol=1e-10
    ):
        raise RuntimeError("Reconstructed SHAP values do not match the saved release summary.")

    roc_points = [
            {"false_positive_rate": float(x), "true_positive_rate": float(y),
             "threshold": None if not np.isfinite(threshold) else float(threshold)}
            for x, y, threshold in zip(fpr, tpr, thresholds, strict=True)
        ]
    confusion = {
            "actual_negative": {"predicted_negative": int(saved_test["tn"]), "predicted_positive": int(saved_test["fp"])},
            "actual_positive": {"predicted_negative": int(saved_test["fn"]), "predicted_positive": int(saved_test["tp"])},
            "sample_count": int(len(y_test)),
        }
    shap_rows = [
            {"feature": row.feature, "mean_abs_shap": float(row.mean_abs_shap)}
            for row in shap.itertuples(index=False)
        ]
    return write_interactive_chart_data(
        model_version=art.card["model_version"], model=art.selected, threshold=art.threshold,
        roc_auc=auc, roc_points=roc_points, confusion_matrix=confusion,
        calibration_bins=art.card.get("calibration_bins", []), shap_units=art.explainer.units,
        shap_importance=shap_rows,
    )


if __name__ == "__main__":
    print(export_chart_data())
