"""
CDC BRFSS Research Benchmark Training Pipeline (UCI Dataset ID 891).

Trains and compares three completely independent algorithms:
  1. Logistic Regression
  2. Random Forest
  3. Gradient Boosting

Strictly US survey data (reported diabetes/prediabetes status: Diabetes_binary).
Not a clinical diagnostic model; not validated for Indian adults.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA_PATH = ROOT / "data" / "public" / "brfss" / "cdc_diabetes_health_indicators.csv"
META_PATH = ROOT / "data" / "public" / "brfss" / "dataset_metadata.json"
MODELS_DIR = ROOT / "models" / "brfss_benchmark"
REPORTS_DIR = ROOT / "reports" / "brfss_benchmark"

LIMITATION_STATEMENT = (
    "This research benchmark uses US CDC BRFSS survey data. The target represents "
    "survey-reported diabetes/prediabetes status. It is not a clinical diagnostic model "
    "and is not validated for Indian adults."
)


def compute_metrics(y_true: np.ndarray, y_prob: np.ndarray, threshold: float = 0.5) -> dict[str, Any]:
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
    cls_rep = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "specificity": round(spec, 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "pr_auc": round(float(average_precision_score(y_true, y_prob)), 4),
        "brier": round(float(brier_score_loss(y_true, y_prob)), 4),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "per_class": {
            "0": {k: round(float(v), 4) for k, v in cls_rep["0"].items()},
            "1": {k: round(float(v), 4) for k, v in cls_rep["1"].items()},
        },
    }


def bootstrap_cis(y_true: np.ndarray, y_prob: np.ndarray, n_boot: int = 80, seed: int = 42) -> dict[str, list[float]]:
    rng = np.random.default_rng(seed)
    n = len(y_true)
    keys = ["accuracy", "balanced_accuracy", "precision", "recall", "specificity", "f1", "roc_auc", "pr_auc"]
    buckets: dict[str, list[float]] = {k: [] for k in keys}
    y_pred = (y_prob >= 0.5).astype(int)

    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        yt = y_true[idx]
        yp = y_prob[idx]
        yd = y_pred[idx]
        if len(np.unique(yt)) < 2:
            continue
        tn, fp, fn, tp = confusion_matrix(yt, yd, labels=[0, 1]).ravel()
        buckets["accuracy"].append(float(accuracy_score(yt, yd)))
        buckets["balanced_accuracy"].append(float(balanced_accuracy_score(yt, yd)))
        buckets["precision"].append(float(precision_score(yt, yd, zero_division=0)))
        buckets["recall"].append(float(recall_score(yt, yd, zero_division=0)))
        buckets["specificity"].append(float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0)
        buckets["f1"].append(float(f1_score(yt, yd, zero_division=0)))
        buckets["roc_auc"].append(float(roc_auc_score(yt, yp)))
        buckets["pr_auc"].append(float(average_precision_score(yt, yp)))

    return {
        k: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
        for k, v in buckets.items()
    }


def downsample_curve(x: np.ndarray, y: np.ndarray, max_pts: int = 100) -> list[dict[str, float]]:
    if len(x) <= max_pts:
        idx = np.arange(len(x))
    else:
        idx = np.unique(np.linspace(0, len(x) - 1, max_pts, dtype=int))
    return [{"x": round(float(x[i]), 5), "y": round(float(y[i]), 5)} for i in idx]


def main() -> int:
    if not DATA_PATH.exists():
        print(f"ERROR: Dataset not found at {DATA_PATH}. Run UCI download first.")
        return 2

    df = pd.read_csv(DATA_PATH)
    target_col = "Diabetes_binary"
    if target_col not in df.columns:
        print(f"ERROR: Expected target column '{target_col}' not found.")
        return 2

    features = [c for c in df.columns if c != target_col]
    X = df[features].copy()
    y = df[target_col].astype(int).to_numpy()

    # 80/20 stratified train/test split — test set untouched during CV and fitting
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42
    )

    # Independent pipelines; class imbalance handled on training data only
    models_cfg = {
        "Logistic Regression": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000, random_state=42)),
        ]),
        "Random Forest": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("model", RandomForestClassifier(
                n_estimators=120, max_depth=14, min_samples_leaf=20,
                class_weight="balanced_subsample", n_jobs=-1, random_state=42,
            )),
        ]),
        "Gradient Boosting": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("model", GradientBoostingClassifier(
                n_estimators=80, max_depth=3, learning_rate=0.1,
                subsample=0.5, random_state=42,
            )),
        ]),
    }

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    comparison_rows: list[dict[str, Any]] = []
    full_results: dict[str, Any] = {}
    confusion_matrices: dict[str, Any] = {}
    roc_curves: dict[str, Any] = {}
    pr_curves: dict[str, Any] = {}
    importance_rows: list[dict[str, Any]] = []
    fitted_pipes: dict[str, Pipeline] = {}

    for name, pipe in models_cfg.items():
        print(f"Training & cross-validating: {name} ...")
        cv_roc, cv_bal, cv_f1 = [], [], []
        for tr_i, va_i in skf.split(X_train, y_train):
            X_tr_f, y_tr_f = X_train.iloc[tr_i], y_train[tr_i]
            X_va_f, y_va_f = X_train.iloc[va_i], y_train[va_i]
            # Clone-like fresh fit
            from sklearn.base import clone
            fold_pipe = clone(pipe)
            if name == "Gradient Boosting":
                sw = compute_sample_weight("balanced", y_tr_f)
                fold_pipe.fit(X_tr_f, y_tr_f, model__sample_weight=sw)
            else:
                fold_pipe.fit(X_tr_f, y_tr_f)
            p_va = fold_pipe.predict_proba(X_va_f)[:, 1]
            pred_va = (p_va >= 0.5).astype(int)
            cv_roc.append(float(roc_auc_score(y_va_f, p_va)))
            cv_bal.append(float(balanced_accuracy_score(y_va_f, pred_va)))
            cv_f1.append(float(f1_score(y_va_f, pred_va, zero_division=0)))

        # Fit final model on full training split
        if name == "Gradient Boosting":
            sw_full = compute_sample_weight("balanced", y_train)
            pipe.fit(X_train, y_train, model__sample_weight=sw_full)
        else:
            pipe.fit(X_train, y_train)
        fitted_pipes[name] = pipe

        # Independent evaluation on untouched held-out test set
        p_test = pipe.predict_proba(X_test)[:, 1]
        m = compute_metrics(y_test, p_test, threshold=0.5)
        cis = bootstrap_cis(y_test, p_test, n_boot=80, seed=42)

        fpr, tpr, _ = roc_curve(y_test, p_test)
        prec_c, rec_c, _ = precision_recall_curve(y_test, p_test)
        roc_curves[name] = downsample_curve(fpr, tpr, max_pts=90)
        pr_curves[name] = downsample_curve(rec_c, prec_c, max_pts=90)
        confusion_matrices[name] = {"tn": m["tn"], "fp": m["fp"], "fn": m["fn"], "tp": m["tp"]}

        # Feature importance
        est = pipe.named_steps["model"]
        if hasattr(est, "coef_"):
            raw_imp = np.abs(est.coef_[0])
        else:
            raw_imp = est.feature_importances_
        norm_imp = raw_imp / (raw_imp.sum() if raw_imp.sum() > 0 else 1.0)
        for feat, val in zip(features, norm_imp):
            importance_rows.append({"model": name, "feature": feat, "importance": round(float(val), 5)})

        row = {
            "model": name,
            "cv_roc_auc_mean": round(float(np.mean(cv_roc)), 4),
            "cv_roc_auc_std": round(float(np.std(cv_roc)), 4),
            "cv_balanced_acc_mean": round(float(np.mean(cv_bal)), 4),
            "cv_f1_mean": round(float(np.mean(cv_f1)), 4),
            "accuracy": m["accuracy"],
            "balanced_accuracy": m["balanced_accuracy"],
            "precision": m["precision"],
            "recall": m["recall"],
            "specificity": m["specificity"],
            "f1": m["f1"],
            "roc_auc": m["roc_auc"],
            "pr_auc": m["pr_auc"],
            "brier": m["brier"],
        }
        comparison_rows.append(row)
        full_results[name] = {
            **row,
            "confusion_matrix": confusion_matrices[name],
            "per_class": m["per_class"],
            "confidence_intervals_95": cis,
        }
        print(f"  {name}: ROC-AUC={m['roc_auc']} BalAcc={m['balanced_accuracy']} F1={m['f1']} Recall={m['recall']}")

    # Select best model using balanced evaluation (CV balanced accuracy + CV ROC-AUC + CV F1)
    best_model = max(
        comparison_rows,
        key=lambda r: (r["cv_roc_auc_mean"] + r["cv_balanced_acc_mean"] + r["cv_f1_mean"]) / 3.0,
    )["model"]

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    sel_path = MODELS_DIR / "selected_model.joblib"
    joblib.dump(fitted_pipes[best_model], sel_path)
    sel_hash = hashlib.sha256(sel_path.read_bytes()).hexdigest()

    class_dist = {
        "0_no_diabetes": int((y == 0).sum()),
        "1_prediabetes_or_diabetes": int((y == 1).sum()),
    }

    card = {
        "model_version": "brfss_v1",
        "model_label": "Large US survey research benchmark (CDC BRFSS)",
        "selected_model": best_model,
        "python_version": platform.python_version(),
        "sklearn_version": sklearn.__version__,
        "package_versions": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit-learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
        "selection_reasoning": (
            f"Selected {best_model} based on balanced 5-fold cross-validation performance "
            f"(combining CV ROC-AUC, CV balanced accuracy, and CV F1) rather than accuracy alone."
        ),
        "trained_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dataset": {
            "source": "CDC Diabetes Health Indicators (UCI Dataset ID 891 / CDC BRFSS)",
            "url": "https://archive.ics.uci.edu/dataset/891/cdc+diabetes+health+indicators",
            "n_records": int(len(df)),
            "n_train": int(len(X_train)),
            "n_test": int(len(X_test)),
            "n_features": int(len(features)),
            "features": features,
            "target_column": target_col,
            "target_definition": "0 = no diabetes; 1 = prediabetes or diabetes (survey-reported)",
            "class_distribution": class_dist,
        },
        "limitation_statement": LIMITATION_STATEMENT,
        "model_sha256": sel_hash,
        "models": full_results,
    }

    (MODELS_DIR / "model_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    pd.DataFrame(comparison_rows).to_csv(REPORTS_DIR / "metrics.csv", index=False)
    pd.DataFrame(comparison_rows).to_csv(REPORTS_DIR / "model_comparison.csv", index=False)
    (REPORTS_DIR / "metrics.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    (REPORTS_DIR / "confusion_matrices.json").write_text(json.dumps(confusion_matrices, indent=2), encoding="utf-8")
    (REPORTS_DIR / "roc_curves.json").write_text(json.dumps(roc_curves), encoding="utf-8")
    (REPORTS_DIR / "pr_curves.json").write_text(json.dumps(pr_curves), encoding="utf-8")
    pd.DataFrame(importance_rows).to_csv(REPORTS_DIR / "feature_importance.csv", index=False)

    print(f"Done. Selected best model: {best_model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
