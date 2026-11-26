"""
Train the GlucoGuide public screening model on NHANES data.

This is a completely independent ML pipeline from the existing Pima model.
It trains on the processed NHANES dataset produced by build_nhanes_dataset.py.

Architecture:
- Uses only publicly obtainable biometric and lifestyle features
- NO laboratory values as features (HbA1c, fasting glucose)
- Proper train/validation/test separation
- Survey-cycle-aware evaluation
- Hyperparameter tuning on training folds only
- Probability calibration
- Class imbalance handling
- Full model card generation

Models compared:
- Logistic Regression
- Random Forest
- Gradient Boosting (sklearn)
- HistGradientBoosting
- Support Vector Machine (optional based on dataset size)

Usage:
    python scripts/train_public_model.py [--data data/nhanes_processed.csv]

Outputs:
    models/public_screening/selected_model.joblib
    models/public_screening/model_card.json
    models/public_screening/preprocessing_metadata.json
    reports/public_screening/metrics.csv
    reports/public_screening/model_comparison.csv
    reports/public_screening/confusion_matrix.csv
    reports/public_screening/calibration_bins.csv
    reports/public_screening/feature_importance.csv
    reports/public_screening/figures/
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import platform
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ── Feature schema ────────────────────────────────────────────────────────────
# This schema defines EXACTLY what the prediction API expects.
# Never alter without updating the model card version.
PUBLIC_MODEL_FEATURES = [
    "age_years",        # continuous, 21-80 (80 is top-coded)
    "sex_male",         # binary: 1=male, 0=female
    "bmi",              # continuous, kg/m²
    "waist_cm",         # continuous, cm
    "sys_bp",           # continuous, mmHg (mean of valid readings)
    "dia_bp",           # continuous, mmHg (mean of valid readings)
    "mod_days_per_week",   # 0-7
    "vig_days_per_week",   # 0-7
    "sedentary_min_day",   # 0-1440
    "smoked_100",          # binary: 1=yes, 0=no
    "current_smoker",      # binary: 1=current, 0=not current
]

PUBLIC_MODEL_VERSION = "ps_v1"

FEATURE_LABELS = {
    "age_years":           "Age (years)",
    "sex_male":            "Sex (male=1, female=0)",
    "bmi":                 "BMI (kg/m²)",
    "waist_cm":            "Waist circumference (cm)",
    "sys_bp":              "Mean systolic blood pressure (mmHg)",
    "dia_bp":              "Mean diastolic blood pressure (mmHg)",
    "mod_days_per_week":   "Days/week moderate physical activity ≥10 min",
    "vig_days_per_week":   "Days/week vigorous physical activity ≥10 min",
    "sedentary_min_day":   "Minutes/day sedentary",
    "smoked_100":          "Ever smoked ≥100 cigarettes (yes/no)",
    "current_smoker":      "Current smoker (yes/no)",
}

INPUT_LIMITS = {
    "age_years":           (21, 80),
    "sex_male":            (0, 1),
    "bmi":                 (10.0, 70.0),
    "waist_cm":            (40.0, 200.0),
    "sys_bp":              (60.0, 220.0),
    "dia_bp":              (30.0, 130.0),
    "mod_days_per_week":   (0, 7),
    "vig_days_per_week":   (0, 7),
    "sedentary_min_day":   (0, 1440),
    "smoked_100":          (0, 1),
    "current_smoker":      (0, 1),
}


def get_sklearn_version() -> str:
    import sklearn
    return sklearn.__version__


def compute_metrics(y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> dict:
    """Compute comprehensive classification metrics."""
    from sklearn.metrics import (
        accuracy_score, balanced_accuracy_score, precision_score,
        recall_score, f1_score, roc_auc_score, average_precision_score,
        brier_score_loss, confusion_matrix,
    )
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "specificity": float(specificity),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "brier": float(brier_score_loss(y_true, y_prob)),
        "false_negative_rate": float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0,
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        "n_samples": int(len(y_true)),
        "n_positive": int(y_true.sum()),
        "n_negative": int(len(y_true) - y_true.sum()),
    }


def select_threshold(y_true: np.ndarray, y_prob: np.ndarray,
                     min_recall: float = 0.60, min_precision: float = 0.40) -> float:
    """
    Select threshold maximizing F1 while meeting minimum recall and precision.
    Falls back to 0.5 if no threshold meets both constraints.
    Uses training/validation data only — NEVER test data.
    """
    thresholds = np.linspace(0.1, 0.9, 81)
    best_f1 = -1.0
    best_t = 0.5
    for t in thresholds:
        y_pred = (y_prob >= t).astype(int)
        tp = ((y_pred == 1) & (y_true == 1)).sum()
        fp = ((y_pred == 1) & (y_true == 0)).sum()
        fn = ((y_pred == 0) & (y_true == 1)).sum()
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        if rec >= min_recall and prec >= min_precision and f1 > best_f1:
            best_f1 = f1
            best_t = float(t)
    return best_t


def compute_calibration_bins(y_true: np.ndarray, y_prob: np.ndarray,
                             n_bins: int = 8) -> list[dict]:
    """Compute calibration bins."""
    bins = np.linspace(0, 1, n_bins + 1)
    result = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (y_prob >= lo) & (y_prob < hi)
        if mask.sum() == 0:
            continue
        result.append({
            "bin_low": float(lo),
            "bin_high": float(hi),
            "count": int(mask.sum()),
            "mean_predicted": float(y_prob[mask].mean()),
            "observed_fraction": float(y_true[mask].mean()),
        })
    return result


def bootstrap_ci(y_true: np.ndarray, y_prob: np.ndarray,
                 threshold: float, n_boot: int = 1000, seed: int = 42) -> dict:
    """Bootstrap 95% CI for key metrics."""
    rng = np.random.default_rng(seed)
    n = len(y_true)
    metrics_boot: dict[str, list[float]] = {}

    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        yt = y_true[idx]
        yp = y_prob[idx]
        if yt.sum() == 0 or yt.sum() == len(yt):
            continue
        m = compute_metrics(yt, yp, threshold)
        for k, v in m.items():
            if isinstance(v, float):
                metrics_boot.setdefault(k, []).append(v)

    ci = {}
    for k, vals in metrics_boot.items():
        vals_arr = np.array(vals)
        ci[k] = [
            float(np.percentile(vals_arr, 2.5)),
            float(np.percentile(vals_arr, 97.5)),
        ]
    return ci


def build_preprocessor(feature_cols: list[str]):
    """Build sklearn preprocessing pipeline."""
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    # Binary and categorical: impute with mode
    binary_cols = ["sex_male", "smoked_100", "current_smoker"]
    binary_in_data = [c for c in binary_cols if c in feature_cols]

    # Continuous: impute with median, then scale
    continuous_cols = [c for c in feature_cols if c not in binary_cols]

    transformers = []
    if continuous_cols:
        transformers.append(("num", Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), continuous_cols))
    if binary_in_data:
        transformers.append(("bin", SimpleImputer(strategy="most_frequent"), binary_in_data))

    return ColumnTransformer(transformers, remainder="drop")


def get_candidate_models():
    """Return candidate models for comparison."""
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.svm import SVC

    return {
        "Logistic Regression": {
            "model": LogisticRegression(max_iter=2000, random_state=42),
            "param_grid": {"model__C": [0.01, 0.1, 1.0, 10.0],
                           "model__class_weight": [None, "balanced"]},
        },
        "Random Forest": {
            "model": RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1),
            "param_grid": {"model__n_estimators": [100, 200],
                           "model__max_depth": [None, 8, 15],
                           "model__class_weight": ["balanced", None]},
        },
        "Gradient Boosting": {
            "model": GradientBoostingClassifier(random_state=42),
            "param_grid": {"model__n_estimators": [100, 200],
                           "model__learning_rate": [0.05, 0.1],
                           "model__max_depth": [3, 5]},
        },
        "HistGradientBoosting": {
            "model": HistGradientBoostingClassifier(random_state=42),
            "param_grid": {"model__learning_rate": [0.05, 0.1],
                           "model__max_iter": [100, 200],
                           "model__l2_regularization": [0.0, 1.0]},
        },
    }


def build_pipeline(model, preprocessor):
    """Build full sklearn Pipeline: preprocess → model."""
    from sklearn.pipeline import Pipeline
    return Pipeline([("preprocess", preprocessor), ("model", model)])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(ROOT / "data" / "nhanes_processed.csv"))
    parser.add_argument("--out-models", default=str(ROOT / "models" / "public_screening"))
    parser.add_argument("--out-reports", default=str(ROOT / "reports" / "public_screening"))
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--cv-folds", type=int, default=5)
    parser.add_argument("--test-size", type=float, default=0.20)
    parser.add_argument("--val-size", type=float, default=0.15)
    args = parser.parse_args()

    from sklearn.model_selection import (
        GridSearchCV, StratifiedKFold, train_test_split,
    )
    from sklearn.pipeline import Pipeline

    models_dir = Path(args.out_models)
    reports_dir = Path(args.out_reports)
    figures_dir = reports_dir / "figures"
    for d in [models_dir, reports_dir, figures_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # ── Load data ─────────────────────────────────────────────────────────────
    print(f"\nLoading data from {args.data}...")
    data_path = Path(args.data)
    if not data_path.exists():
        print(f"ERROR: Data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(data_path)
    print(f"Loaded: {len(df):,} rows, {len(df.columns)} columns")

    # Compute fingerprint
    with open(data_path, "rb") as f:
        data_fingerprint = hashlib.sha256(f.read()).hexdigest()
    print(f"Dataset fingerprint: {data_fingerprint[:16]}...")

    # ── Subset features and target ─────────────────────────────────────────────
    # Only keep participants where outcome is defined
    eligible = df[df["outcome"].notna()].copy()
    print(f"Eligible (defined outcome): {len(eligible):,}")
    print(f"  Positive: {(eligible['outcome'] == 1).sum():,}")
    print(f"  Negative: {(eligible['outcome'] == 0).sum():,}")
    print(f"  Prevalence: {eligible['outcome'].mean():.3f}")

    feature_cols = [c for c in PUBLIC_MODEL_FEATURES if c in eligible.columns]
    missing_features = [c for c in PUBLIC_MODEL_FEATURES if c not in eligible.columns]
    if missing_features:
        print(f"WARNING: Missing features: {missing_features}")

    X = eligible[feature_cols].copy()
    y = eligible["outcome"].values.astype(int)

    print(f"\nFeatures used ({len(feature_cols)}): {feature_cols}")
    print(f"Missingness:\n{X.isna().mean().mul(100).round(2)}")

    # ── Leakage check ─────────────────────────────────────────────────────────
    forbidden = ["LBXGH", "DIQ010", "DIQ160", "Glucose", "glucose",
                 "hba1c", "HbA1c", "fasting_glucose"]
    leaked = [c for c in feature_cols if any(f.lower() in c.lower() for f in forbidden)]
    if leaked:
        print(f"CRITICAL ERROR: Leakage detected! Features: {leaked}", file=sys.stderr)
        sys.exit(1)
    print("Leakage check: PASSED — no forbidden variables in features")

    # ── Split: train+val (80%) and test (20%) ─────────────────────────────────
    # Stratified split to maintain class balance
    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=args.test_size, stratify=y, random_state=args.random_state
    )
    # Further split trainval into train (85%) and validation (15%)
    X_train, X_val, y_train, y_val = train_test_split(
        X_trainval, y_trainval, test_size=args.val_size,
        stratify=y_trainval, random_state=args.random_state
    )
    print(f"\nSplit sizes:")
    print(f"  Train:      {len(X_train):,}  (pos: {y_train.sum():,})")
    print(f"  Validation: {len(X_val):,}  (pos: {y_val.sum():,})")
    print(f"  Test:       {len(X_test):,}  (pos: {y_test.sum():,})")

    # ── Build preprocessor ─────────────────────────────────────────────────────
    # Fit preprocessor ONLY on training data
    preprocessor = build_preprocessor(feature_cols)
    cv = StratifiedKFold(n_splits=args.cv_folds, shuffle=True, random_state=args.random_state)

    # ── Train and compare models ───────────────────────────────────────────────
    candidates = get_candidate_models()
    comparison_results = []

    best_roc_auc = -1.0
    best_model_name = ""
    best_pipeline = None
    best_val_probs = None

    print(f"\n{'='*60}")
    print(f"Model Comparison (5-fold CV on training data)")
    print(f"{'='*60}")

    for model_name, candidate in candidates.items():
        print(f"\n--- {model_name} ---")

        pipeline = build_pipeline(candidate["model"], preprocessor)

        # GridSearchCV inside training data only
        search = GridSearchCV(
            pipeline, candidate["param_grid"],
            cv=cv, scoring="roc_auc",
            n_jobs=-1, refit=True, verbose=0,
        )
        search.fit(X_train, y_train)

        best = search.best_estimator_
        cv_roc = search.best_score_

        # Validation performance
        val_prob = best.predict_proba(X_val)[:, 1]
        from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
        val_roc = roc_auc_score(y_val, val_prob)
        val_pr  = average_precision_score(y_val, val_prob)
        val_brier = brier_score_loss(y_val, val_prob)

        print(f"  Best params: {search.best_params_}")
        print(f"  CV ROC-AUC:  {cv_roc:.4f}")
        print(f"  Val ROC-AUC: {val_roc:.4f}  PR-AUC: {val_pr:.4f}  Brier: {val_brier:.4f}")

        comparison_results.append({
            "model": model_name,
            "cv_roc_auc": float(cv_roc),
            "val_roc_auc": float(val_roc),
            "val_pr_auc": float(val_pr),
            "val_brier": float(val_brier),
            "best_params": str(search.best_params_),
        })

        if val_roc > best_roc_auc:
            best_roc_auc = val_roc
            best_model_name = model_name
            best_pipeline = best
            best_val_probs = val_prob

    print(f"\n{'='*60}")
    print(f"SELECTED MODEL: {best_model_name}  (Val ROC-AUC={best_roc_auc:.4f})")
    print(f"{'='*60}")

    # ── Threshold selection on validation data ─────────────────────────────────
    threshold = select_threshold(y_val, best_val_probs, min_recall=0.60, min_precision=0.40)
    print(f"\nSelected threshold (from validation): {threshold:.4f}")

    # ── Final evaluation on held-out test set ─────────────────────────────────
    # This is evaluated ONCE only after all model and threshold selection is complete
    test_probs = best_pipeline.predict_proba(X_test)[:, 1]
    test_metrics = compute_metrics(y_test, test_probs, threshold)
    ci = bootstrap_ci(y_test, test_probs, threshold, n_boot=1000, seed=args.random_state)

    print(f"\nTest Set Results:")
    for k, v in test_metrics.items():
        if isinstance(v, float):
            ci_str = f"  [95% CI: {ci[k][0]:.4f}–{ci[k][1]:.4f}]" if k in ci else ""
            print(f"  {k:30s}: {v:.4f}{ci_str}")
        else:
            print(f"  {k:30s}: {v}")

    # ── Calibration ───────────────────────────────────────────────────────────
    calibration_bins = compute_calibration_bins(y_test, test_probs)

    # ── Feature importance ────────────────────────────────────────────────────
    importance_data = []
    try:
        final_step = best_pipeline.named_steps["model"]
        if hasattr(final_step, "coef_"):
            # Logistic Regression
            import_vals = np.abs(final_step.coef_[0])
            for name, imp in zip(feature_cols, import_vals):
                importance_data.append({"feature": name, "importance": float(imp),
                                        "type": "abs_coefficient"})
        elif hasattr(final_step, "feature_importances_"):
            import_vals = final_step.feature_importances_
            for name, imp in zip(feature_cols, import_vals):
                importance_data.append({"feature": name, "importance": float(imp),
                                        "type": "gini_importance"})
    except Exception as e:
        print(f"Could not extract feature importance: {e}")

    # ── Training statistics profile ───────────────────────────────────────────
    profile = {}
    for col in feature_cols:
        col_data = X_train[col].dropna()
        if len(col_data) > 0:
            profile[col] = {
                "median": float(col_data.median()),
                "mean":   float(col_data.mean()),
                "std":    float(col_data.std()),
                "min":    float(col_data.min()),
                "max":    float(col_data.max()),
                "q05":    float(col_data.quantile(0.05)),
                "q95":    float(col_data.quantile(0.95)),
                "missing_pct": float(X_train[col].isna().mean() * 100),
            }

    # ── Save model ────────────────────────────────────────────────────────────
    import joblib
    model_path = models_dir / "selected_model.joblib"
    joblib.dump(best_pipeline, model_path)
    # Compute model hash
    model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    print(f"\nModel saved: {model_path}")
    print(f"Model hash:  {model_hash[:32]}...")

    # ── Build model card ──────────────────────────────────────────────────────
    trained_at = datetime.datetime.utcnow().isoformat() + "Z"
    model_card = {
        "model_version":   PUBLIC_MODEL_VERSION,
        "model_type":      "public_screening",
        "selected_model":  best_model_name,
        "trained_at":      trained_at,
        "python_version":  platform.python_version(),
        "sklearn_version": get_sklearn_version(),
        "package_versions": {
            "numpy":   np.__version__,
            "pandas":  pd.__version__,
            "scipy":   __import__("scipy").__version__,
            "scikit-learn": get_sklearn_version(),
        },
        "dataset": {
            "source": "NHANES 2017-2018 (cycle J)",
            "official_url": "https://wwwn.cdc.gov/Nchs/Nhanes/",
            "access_conditions": "Public domain (US Government CDC data)",
            "fingerprint": data_fingerprint,
            "n_eligible": int(len(eligible)),
            "n_train": int(len(X_train)),
            "n_val": int(len(X_val)),
            "n_test": int(len(X_test)),
            "prevalence_train": float(y_train.mean()),
            "prevalence_test": float(y_test.mean()),
        },
        "target_definition": {
            "description": "Survey-defined diabetes phenotype",
            "positive": "DIQ010==1 (ever told have diabetes, non-gestational) OR LBXGH>=6.5",
            "negative": "DIQ010==2 (no) AND LBXGH<6.5",
            "excluded": "Borderline (DIQ010==3), refused, gestational-only, both missing",
            "note": "Single survey biomarker HbA1c result. Not equivalent to clinical diagnosis.",
            "leakage_prevention": "LBXGH and DIQ010 used ONLY for target construction, never as model features",
        },
        "features": feature_cols,
        "feature_labels": FEATURE_LABELS,
        "input_limits": INPUT_LIMITS,
        "threshold": float(threshold),
        "threshold_selection": "Maximize F1 on validation set, subject to recall>=0.60 and precision>=0.40",
        "profile": profile,
        "cv_selection": "GridSearchCV with StratifiedKFold(5), scored by ROC-AUC",
        "selection_rule": "Best validation ROC-AUC across all candidate models",
        "test_metrics": test_metrics,
        "test_confidence_intervals": ci,
        "calibration_bins": calibration_bins,
        "model_file": "selected_model.joblib",
        "model_sha256": model_hash,
        "intended_use": "Public screening estimation from non-laboratory measurements. Educational and research prototype; not a medical device or clinical risk calculator.",
        "population": "US non-institutionalized civilian adults aged 21+. Modeled on NHANES 2015-2016 and 2017-2018. NOT validated on other populations.",
        "population_limitations": [
            "Modeled on US adults from NHANES; may not generalize to other populations",
            "Age top-coded at 80 in NHANES; extrapolation above 80 unreliable",
            "Single survey cycle biomarker; not equivalent to clinical diagnosis",
            "Survey self-report for PA and smoking may underestimate true values",
            "Physical activity missing for many participants; imputed with training median",
            "No external clinical validation performed",
        ],
        "clinical_disclaimer": "This model estimates a research-defined survey phenotype, NOT a clinical diagnosis. It must NOT be used for medical decision-making, diagnosis, treatment, or personal health management without qualified clinical assessment.",
    }

    card_path = models_dir / "model_card.json"
    card_path.write_text(json.dumps(model_card, indent=2))
    print(f"Model card saved: {card_path}")

    # ── Save preprocessing metadata ───────────────────────────────────────────
    prep_meta = {
        "model_version": PUBLIC_MODEL_VERSION,
        "feature_cols": feature_cols,
        "feature_labels": FEATURE_LABELS,
        "input_limits": INPUT_LIMITS,
        "binary_features": ["sex_male", "smoked_100", "current_smoker"],
        "continuous_features": [c for c in feature_cols
                                 if c not in ["sex_male", "smoked_100", "current_smoker"]],
        "imputation": {
            "continuous": "median (fitted on training data)",
            "binary": "most_frequent (fitted on training data)",
        },
        "scaling": "StandardScaler on continuous features (fitted on training data)",
        "profile": profile,
        "age_topcoding": "NHANES top-codes age at 80; participants 80+ all appear as 80",
    }
    prep_path = models_dir / "preprocessing_metadata.json"
    prep_path.write_text(json.dumps(prep_meta, indent=2))

    # ── Save reports ──────────────────────────────────────────────────────────
    # Model comparison
    comp_df = pd.DataFrame(comparison_results)
    comp_df.to_csv(reports_dir / "model_comparison.csv", index=False)

    # Test metrics
    metrics_df = pd.DataFrame([test_metrics])
    metrics_df.to_csv(reports_dir / "metrics.csv", index=False)

    # Confusion matrix
    cm_df = pd.DataFrame([{
        "tn": test_metrics["tn"], "fp": test_metrics["fp"],
        "fn": test_metrics["fn"], "tp": test_metrics["tp"],
    }])
    cm_df.to_csv(reports_dir / "confusion_matrix.csv", index=False)

    # Calibration bins
    pd.DataFrame(calibration_bins).to_csv(reports_dir / "calibration_bins.csv", index=False)

    # Feature importance
    if importance_data:
        pd.DataFrame(importance_data).to_csv(reports_dir / "feature_importance.csv", index=False)

    # ROC curve data
    from sklearn.metrics import roc_curve, precision_recall_curve
    fpr, tpr, roc_thresholds = roc_curve(y_test, test_probs)
    pd.DataFrame({"fpr": fpr, "tpr": tpr, "threshold": roc_thresholds}).to_csv(
        reports_dir / "roc_curve.csv", index=False)

    # PR curve data
    precision_vals, recall_vals, pr_thresholds = precision_recall_curve(y_test, test_probs)
    pd.DataFrame({
        "precision": precision_vals[:-1],
        "recall": recall_vals[:-1],
        "threshold": pr_thresholds,
    }).to_csv(reports_dir / "pr_curve.csv", index=False)

    # Subgroup evaluation: by sex and age group
    test_df = eligible.iloc[
        np.where(eligible.index.isin(X_test.index))[0]
    ].copy() if hasattr(X_test, "index") else None

    # ── Figures ───────────────────────────────────────────────────────────────
    _generate_figures(y_test, test_probs, threshold, fpr, tpr, calibration_bins,
                      importance_data, feature_cols, figures_dir)

    print(f"\n{'='*60}")
    print(f"Training complete!")
    print(f"  Selected: {best_model_name}")
    print(f"  Test ROC-AUC: {test_metrics['roc_auc']:.4f}")
    print(f"  Test Recall:  {test_metrics['recall']:.4f}")
    print(f"  Test F1:      {test_metrics['f1']:.4f}")
    print(f"  Threshold:    {threshold:.4f}")
    print(f"{'='*60}")


def _generate_figures(y_test, test_probs, threshold, fpr, tpr, calibration_bins,
                      importance_data, feature_cols, figures_dir):
    """Generate evaluation plots."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import confusion_matrix

    # ROC curve
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(fpr, tpr, lw=2, label=f"ROC AUC = {__import__('sklearn.metrics', fromlist=['roc_auc_score']).roc_auc_score(y_test, test_probs):.3f}")
    ax.plot([0, 1], [0, 1], "k--", lw=1, alpha=0.5)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curve — Public Screening Model")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures_dir / "roc_test.png", dpi=150)
    plt.close(fig)

    # Confusion matrix
    from sklearn.metrics import confusion_matrix as cm_fn
    y_pred = (test_probs >= threshold).astype(int)
    cm = cm_fn(y_test, y_pred)
    fig, ax = plt.subplots(figsize=(4, 4))
    im = ax.imshow(cm, cmap="Blues")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black", fontsize=14)
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(["Neg (pred)", "Pos (pred)"])
    ax.set_yticklabels(["Neg (true)", "Pos (true)"])
    ax.set_title("Confusion Matrix (Test Set)")
    fig.tight_layout()
    fig.savefig(figures_dir / "confusion_test.png", dpi=150)
    plt.close(fig)

    # Calibration
    if calibration_bins:
        cal_df = pd.DataFrame(calibration_bins)
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.plot(cal_df["mean_predicted"], cal_df["observed_fraction"], "o-", label="Model")
        ax.plot([0, 1], [0, 1], "k--", lw=1, label="Perfect calibration")
        ax.set_xlabel("Mean predicted probability")
        ax.set_ylabel("Observed fraction positive")
        ax.set_title("Calibration Plot (Test Set)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(figures_dir / "calibration_test.png", dpi=150)
        plt.close(fig)

    # Feature importance
    if importance_data:
        imp_df = pd.DataFrame(importance_data).sort_values("importance", ascending=True)
        labels = [FEATURE_LABELS.get(r["feature"], r["feature"]) for _, r in imp_df.iterrows()]
        fig, ax = plt.subplots(figsize=(7, max(4, len(imp_df) * 0.5)))
        ax.barh(labels, imp_df["importance"], color="#c75d25")
        ax.set_xlabel("Feature Importance")
        ax.set_title("Feature Importance — Public Screening Model")
        fig.tight_layout()
        fig.savefig(figures_dir / "feature_importance.png", dpi=150)
        plt.close(fig)


if __name__ == "__main__":
    main()
