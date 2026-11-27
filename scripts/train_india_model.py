"""
Independent ML training & cluster-aware validation pipeline for ICMR-INDIAB (Model 3).

Strictly independent from Pima (models/) and NHANES (models/public_screening/).
Refuses to run unless authorised ICMR-INDIAB data pass scripts/audit_indiab_dataset.py,
except when called programmatically in unit tests with `allow_fixture=True, save_artifacts=False`.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_indiab_dataset import audit_dataframe, derive_who_diabetes_target, load_manifest  # noqa: E402
from src import india_config as IC  # noqa: E402


def compute_calibration_slope_intercept(y_true: np.ndarray, y_prob: np.ndarray) -> tuple[float | None, float | None]:
    """Estimate logistic calibration slope & intercept on logit(p); return (None, None) if degenerate."""
    if len(np.unique(y_true)) < 2:
        return None, None
    clipped = np.clip(y_prob, 1e-6, 1.0 - 1e-6)
    logits = np.log(clipped / (1.0 - clipped)).reshape(-1, 1)
    try:
        lr = LogisticRegression(C=1e6, solver="lbfgs", max_iter=500)
        lr.fit(logits, y_true)
        return round(float(lr.coef_[0, 0]), 4), round(float(lr.intercept_[0]), 4)
    except Exception:
        return None, None


def compute_binary_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float,
    sample_weight: np.ndarray | None = None,
) -> dict[str, Any]:
    """Compute independent binary classification, calibration, and confusion metrics."""
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
    npv = float(tn / (tn + fn)) if (tn + fn) > 0 else 0.0
    slope, intercept = compute_calibration_slope_intercept(y_true, y_prob)

    has_two = len(np.unique(y_true)) >= 2
    return {
        "n_samples": int(len(y_true)),
        "n_positive": int(np.sum(y_true == 1)),
        "n_negative": int(np.sum(y_true == 0)),
        "threshold": round(float(threshold), 4),
        "accuracy": round(float(accuracy_score(y_true, y_pred, sample_weight=sample_weight)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred, sample_weight=sample_weight)), 4),
        "sensitivity_recall": round(float(recall_score(y_true, y_pred, sample_weight=sample_weight, zero_division=0)), 4),
        "specificity": round(spec, 4),
        "precision": round(float(precision_score(y_true, y_pred, sample_weight=sample_weight, zero_division=0)), 4),
        "npv": round(npv, 4),
        "f1": round(float(f1_score(y_true, y_pred, sample_weight=sample_weight, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_prob, sample_weight=sample_weight)), 4) if has_two else None,
        "pr_auc": round(float(average_precision_score(y_true, y_prob, sample_weight=sample_weight)), 4) if has_two else None,
        "brier": round(float(brier_score_loss(y_true, y_prob, sample_weight=sample_weight)), 4),
        "calibration_slope": slope,
        "calibration_intercept": intercept,
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def cluster_bootstrap_ci(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    psu_ids: np.ndarray,
    threshold: float,
    *,
    n_boot: int = 200,
    seed: int = 42,
) -> dict[str, list[float]]:
    """Cluster-aware bootstrap 95% CIs resampling PSU clusters with replacement."""
    rng = np.random.default_rng(seed)
    unique_psus = np.unique(psu_ids)
    psu_to_idx = {p: np.where(psu_ids == p)[0] for p in unique_psus}
    keys = ["roc_auc", "pr_auc", "sensitivity_recall", "specificity", "precision", "f1", "brier"]
    samples: dict[str, list[float]] = {k: [] for k in keys}

    for _ in range(n_boot):
        drawn = rng.choice(unique_psus, size=len(unique_psus), replace=True)
        idx = np.concatenate([psu_to_idx[p] for p in drawn])
        yt = y_true[idx]
        yp = y_prob[idx]
        if len(np.unique(yt)) < 2:
            continue
        m = compute_binary_metrics(yt, yp, threshold)
        for k in keys:
            if m[k] is not None:
                samples[k].append(float(m[k]))

    cis: dict[str, list[float]] = {}
    for k, vals in samples.items():
        if len(vals) >= 10:
            cis[k] = [round(float(np.percentile(vals, 2.5)), 4), round(float(np.percentile(vals, 97.5)), 4)]
    return cis


def select_validation_threshold(y_val: np.ndarray, p_val: np.ndarray) -> float:
    """Select threshold on validation predictions maximizing F1 subject to recall >= 0.60 when achievable."""
    best_thr, best_f1 = 0.5, -1.0
    for thr in np.round(np.arange(0.10, 0.85, 0.02), 2):
        pred = (p_val >= thr).astype(int)
        rec = recall_score(y_val, pred, zero_division=0)
        f1 = f1_score(y_val, pred, zero_division=0)
        if rec >= 0.60 and f1 > best_f1:
            best_f1 = f1
            best_thr = float(thr)
    if best_f1 < 0:
        for thr in np.round(np.arange(0.10, 0.85, 0.02), 2):
            f1 = f1_score(y_val, (p_val >= thr).astype(int), zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_thr = float(thr)
    return round(best_thr, 2)


def build_preprocessor(numeric_cols: list[str], categorical_cols: list[str]) -> ColumnTransformer:
    """Training-only preprocessor: median imputation (never 0) + scaling; categorical OHE."""
    transformers = []
    if numeric_cols:
        transformers.append(
            (
                "num",
                Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]),
                numeric_cols,
            )
        )
    if categorical_cols:
        transformers.append(
            (
                "cat",
                Pipeline([
                    ("impute", SimpleImputer(strategy="most_frequent")),
                    ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                ]),
                categorical_cols,
            )
        )
    return ColumnTransformer(transformers=transformers, remainder="drop")


def evaluate_subgroups(
    df_test: pd.DataFrame,
    y_test: np.ndarray,
    p_test: np.ndarray,
    threshold: float,
) -> dict[str, list[dict[str, Any]]]:
    """Subgroup evaluation across sex, age groups, residence, and state/region when n >= 30."""
    out: dict[str, list[dict[str, Any]]] = {}
    work = df_test.copy()
    work["_y"] = y_test
    work["_p"] = p_test
    if "age_years" in work.columns:
        work["age_group"] = pd.cut(
            pd.to_numeric(work["age_years"], errors="coerce"),
            bins=[19, 34, 49, 64, 120],
            labels=["20-34", "35-49", "50-64", "65+"],
        ).astype(str)

    for group_col in ["sex", "age_group", "residence_type", "state_region"]:
        if group_col not in work.columns:
            continue
        rows = []
        for val, sub in work.groupby(group_col, dropna=False):
            n = len(sub)
            yt = sub["_y"].to_numpy()
            if n < 30 or len(np.unique(yt)) < 2:
                rows.append({
                    "subgroup": str(val),
                    "n": int(n),
                    "status": "insufficient_sample_or_single_class",
                })
                continue
            m = compute_binary_metrics(yt, sub["_p"].to_numpy(), threshold)
            rows.append({
                "subgroup": str(val),
                "n": int(n),
                "status": "evaluated",
                "roc_auc": m["roc_auc"],
                "sensitivity_recall": m["sensitivity_recall"],
                "specificity": m["specificity"],
                "f1": m["f1"],
                "brier": m["brier"],
            })
        out[group_col] = rows
    return out


def train_on_dataframe(
    df: pd.DataFrame,
    manifest: dict[str, Any],
    *,
    allow_fixture: bool = False,
    save_artifacts: bool = True,
    models_dir: Path = IC.INDIA_MODELS_DIR,
    reports_dir: Path = IC.INDIA_REPORTS_DIR,
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Train and compare Logistic Regression, Random Forest, and Gradient Boosting
    with cluster-safe splitting (no PSU overlap between train and test).
    """
    audit = audit_dataframe(df, manifest, require_permission=not allow_fixture)
    if not audit["audit_passed"]:
        raise RuntimeError(f"ICMR-INDIAB audit failed; training blocked: {audit['blockers']}")

    target, _, target_summary = derive_who_diabetes_target(df)
    work = df.copy()
    work["_target"] = target
    work = work[work["_target"].notna()].copy()
    work = work[pd.to_numeric(work["age_years"], errors="coerce") >= IC.INDIA_MIN_AGE].copy()
    work = work.drop_duplicates(subset=["participant_id"]).reset_index(drop=True)

    y = work["_target"].astype(int).to_numpy()
    psus = work["psu_id"].astype(str).to_numpy()
    weights = pd.to_numeric(work["survey_weight"], errors="coerce").fillna(1.0).to_numpy()

    num_cols = [c for c in IC.INDIA_CANDIDATE_NUMERIC_FEATURES if c in work.columns]
    cat_cols = [c for c in IC.INDIA_CANDIDATE_CATEGORICAL_FEATURES if c in work.columns]
    feature_cols = num_cols + cat_cols
    assert set(feature_cols).isdisjoint(IC.FORBIDDEN_LEAKAGE_VARIABLES)

    X = work[feature_cols].copy()

    # Cluster-safe train+val vs test split (no PSU cluster appears in both)
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=random_state)
    train_val_idx, test_idx = next(splitter.split(X, y, groups=psus))

    # Assert zero PSU overlap
    assert set(psus[train_val_idx]).isdisjoint(set(psus[test_idx])), "PSU cluster leakage between train and test!"

    X_tv, y_tv, p_tv, w_tv = X.iloc[train_val_idx], y[train_val_idx], psus[train_val_idx], weights[train_val_idx]
    X_test, y_test, p_test_psu, w_test = X.iloc[test_idx], y[test_idx], psus[test_idx], weights[test_idx]

    # Cluster-safe train vs validation split
    val_split = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=random_state)
    tr_sub_idx, val_sub_idx = next(val_split.split(X_tv, y_tv, groups=p_tv))
    X_tr, y_tr, p_tr, w_tr = X_tv.iloc[tr_sub_idx], y_tv[tr_sub_idx], p_tv[tr_sub_idx], w_tv[tr_sub_idx]
    X_val, y_val, w_val = X_tv.iloc[val_sub_idx], y_tv[val_sub_idx], w_tv[val_sub_idx]

    candidates = {
        "Logistic Regression": LogisticRegression(C=0.1, max_iter=1000, random_state=random_state),
        "Random Forest": RandomForestClassifier(n_estimators=150, max_depth=8, min_samples_leaf=10, random_state=random_state),
        "Gradient Boosting": GradientBoostingClassifier(n_estimators=120, max_depth=3, learning_rate=0.05, random_state=random_state),
    }

    # Grouped CV on training split
    n_unique_tr_psus = len(np.unique(p_tr))
    n_cv_folds = min(5, max(2, n_unique_tr_psus))
    gkf = StratifiedGroupKFold(n_splits=n_cv_folds)

    comparison_rows: list[dict[str, Any]] = []
    fitted_models: dict[str, dict[str, Any]] = {}

    for name, est in candidates.items():
        # Fresh independent pipeline per model
        cv_aucs: list[float] = []
        for f_tr, f_va in gkf.split(X_tr, y_tr, groups=p_tr):
            if len(np.unique(y_tr[f_tr])) < 2 or len(np.unique(y_tr[f_va])) < 2:
                continue
            cv_pipe = Pipeline([("preprocess", build_preprocessor(num_cols, cat_cols)), ("model", est)])
            cv_pipe.fit(X_tr.iloc[f_tr], y_tr[f_tr], model__sample_weight=w_tr[f_tr])
            p_va = cv_pipe.predict_proba(X_tr.iloc[f_va])[:, 1]
            cv_aucs.append(float(roc_auc_score(y_tr[f_va], p_va)))

        pipe = Pipeline([("preprocess", build_preprocessor(num_cols, cat_cols)), ("model", est)])
        pipe.fit(X_tr, y_tr, model__sample_weight=w_tr)

        val_probs = pipe.predict_proba(X_val)[:, 1]
        thr = select_validation_threshold(y_val, val_probs)
        val_metrics = compute_binary_metrics(y_val, val_probs, thr, sample_weight=w_val)

        test_probs = pipe.predict_proba(X_test)[:, 1]
        test_metrics = compute_binary_metrics(y_test, test_probs, thr, sample_weight=w_test)
        test_cis = cluster_bootstrap_ci(y_test, test_probs, p_test_psu, thr, n_boot=100, seed=random_state)

        comparison_rows.append({
            "model": name,
            "cv_roc_auc_mean": round(float(np.mean(cv_aucs)), 4) if cv_aucs else None,
            "cv_roc_auc_std": round(float(np.std(cv_aucs)), 4) if cv_aucs else None,
            "val_roc_auc": val_metrics["roc_auc"],
            "val_f1": val_metrics["f1"],
            "test_roc_auc": test_metrics["roc_auc"],
            "test_pr_auc": test_metrics["pr_auc"],
            "test_recall": test_metrics["sensitivity_recall"],
            "test_specificity": test_metrics["specificity"],
            "test_f1": test_metrics["f1"],
            "test_brier": test_metrics["brier"],
            "threshold": thr,
        })
        fitted_models[name] = {
            "pipeline": pipe,
            "threshold": thr,
            "val_metrics": val_metrics,
            "test_metrics": test_metrics,
            "test_cis": test_cis,
            "test_probs": test_probs,
            "cv_aucs": [round(x, 4) for x in cv_aucs],
        }

    # Select best model strictly by validation ROC-AUC (never test set)
    selected_name = max(
        fitted_models.keys(),
        key=lambda m: fitted_models[m]["val_metrics"]["roc_auc"] or 0.0,
    )
    sel = fitted_models[selected_name]

    subgroups = evaluate_subgroups(work.iloc[test_idx], y_test, sel["test_probs"], sel["threshold"])
    fpr, tpr, _ = roc_curve(y_test, sel["test_probs"])
    prec_c, rec_c, _ = precision_recall_curve(y_test, sel["test_probs"])

    result = {
        "selected_model": selected_name,
        "features": feature_cols,
        "numeric_features": num_cols,
        "categorical_features": cat_cols,
        "target_summary": target_summary,
        "n_eligible": int(len(work)),
        "n_train": int(len(X_tr)),
        "n_val": int(len(X_val)),
        "n_test": int(len(X_test)),
        "comparison": comparison_rows,
        "selected_val_metrics": sel["val_metrics"],
        "selected_test_metrics": sel["test_metrics"],
        "selected_test_cis": sel["test_cis"],
        "selected_cv_aucs": sel["cv_aucs"],
        "subgroups": subgroups,
        "external_validation": "External validation has not yet been completed.",
    }

    if save_artifacts and not allow_fixture:
        models_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)
        model_path = models_dir / "selected_model.joblib"
        joblib.dump(sel["pipeline"], model_path)
        sha = hashlib.sha256(model_path.read_bytes()).hexdigest()

        card = {
            "model_version": IC.INDIA_MODEL_VERSION,
            "model_family": "india_indiab",
            "model_label": IC.INDIA_MODEL_LABEL,
            "status": "MODEL TRAINED",
            "selected_model": selected_name,
            "trained_at": datetime.datetime.utcnow().isoformat() + "Z",
            "dataset": {
                "name": manifest.get("dataset_name", "ICMR-INDIAB National Diabetes Study"),
                "permission_status": "MODEL TRAINED",
                "n_eligible": int(len(work)),
                "n_train": int(len(X_tr)),
                "n_val": int(len(X_val)),
                "n_test": int(len(X_test)),
            },
            "features": feature_cols,
            "feature_labels": {f: IC.INDIA_FEATURE_LABELS.get(f, f) for f in feature_cols},
            "input_limits": {f: list(IC.INDIA_INPUT_LIMITS[f]) for f in feature_cols if f in IC.INDIA_INPUT_LIMITS},
            "threshold": sel["threshold"],
            "model_sha256": sha,
            "validation_metrics": sel["val_metrics"],
            "test_metrics": sel["test_metrics"],
            "test_confidence_intervals": sel["test_cis"],
            "subgroups": subgroups,
            "comparison": comparison_rows,
            "external_validation": "External validation has not yet been completed.",
            "population": "Indian adults aged 20 years and above (men and women, rural and urban).",
        }
        (models_dir / "model_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
        pd.DataFrame(comparison_rows).to_csv(reports_dir / "model_comparison.csv", index=False)
        pd.DataFrame({"fpr": fpr, "tpr": tpr}).to_csv(reports_dir / "roc_curve.csv", index=False)
        pd.DataFrame({"precision": prec_c, "recall": rec_c}).to_csv(reports_dir / "pr_curve.csv", index=False)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Train ICMR-INDIAB India screening model.")
    parser.add_argument("--data", type=Path, required=True, help="Path to authorised ICMR-INDIAB CSV/Parquet.")
    args = parser.parse_args()
    manifest = load_manifest()
    if not args.data.exists():
        print(f"ERROR: Data file not found: {args.data}")
        return 2
    df = pd.read_parquet(args.data) if args.data.suffix.lower() == ".parquet" else pd.read_csv(args.data)
    res = train_on_dataframe(df, manifest, allow_fixture=False, save_artifacts=True)
    print(json.dumps({"selected_model": res["selected_model"], "test_metrics": res["selected_test_metrics"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
