"""Leakage-aware, nested-CV model research helpers for the Pima release."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score,
                             brier_score_loss, confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.naive_bayes import GaussianNB
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC

from . import config as C
from .preprocessing import build_pipeline


MODEL_GRIDS = {
    "Logistic Regression": (
        LogisticRegression(max_iter=2000, random_state=C.RANDOM_STATE),
        {"model__C": [0.1, 1.0, 10.0], "model__class_weight": [None, "balanced"]},
    ),
    "Gaussian Naive Bayes": (
        GaussianNB(),
        {"model__var_smoothing": [1e-11, 1e-9, 1e-7, 1e-5]},
    ),
    "Random Forest": (
        RandomForestClassifier(random_state=C.RANDOM_STATE, n_jobs=1),
        {"model__n_estimators": [200, 500], "model__max_depth": [None, 5],
         "model__min_samples_leaf": [1, 3], "model__class_weight": [None, "balanced"]},
    ),
    "SVM (RBF)": (
        SVC(kernel="rbf", probability=True, random_state=C.RANDOM_STATE),
        {"model__C": [0.1, 1.0, 10.0], "model__gamma": ["scale", "auto"],
         "model__class_weight": [None, "balanced"]},
    ),
    "Gradient Boosting": (
        GradientBoostingClassifier(random_state=C.RANDOM_STATE),
        {"model__n_estimators": [75, 150], "model__learning_rate": [0.03, 0.1],
         "model__max_depth": [1, 2], "model__min_samples_leaf": [2, 5]},
    ),
}


def select_family(cv_table: pd.DataFrame, tie_tolerance: float = C.TIE_TOLERANCE) -> str:
    """Select by nested OOF ROC-AUC; on near-ties use the declared simplicity order."""
    priority = list(C.MODEL_ORDER) + ["SVM (RBF)", "Gradient Boosting"]
    best = float(cv_table["roc_auc"].max())
    tied = cv_table.loc[cv_table["roc_auc"] >= best - tie_tolerance, "model"].tolist()
    return min(tied, key=priority.index)


def search_for(name: str, seed: int = C.RANDOM_STATE, inner_folds: int = 4,
               force_class_weight: str = "search") -> GridSearchCV:
    estimator, params = MODEL_GRIDS[name]
    params = dict(params)
    if force_class_weight != "search":
        if "model__class_weight" not in params:
            raise ValueError(f"{name} does not support class weighting.")
        params["model__class_weight"] = [force_class_weight]
    estimator = clone(estimator).set_params(**{
        key: seed for key in ("random_state",) if key in estimator.get_params()
    })
    return GridSearchCV(
        build_pipeline(estimator), params, scoring="roc_auc",
        cv=StratifiedKFold(inner_folds, shuffle=True, random_state=seed),
        n_jobs=1, refit=True, error_score="raise",
    )


def nested_oof(name: str, X: pd.DataFrame, y: pd.Series, outer_folds: int = 5,
               inner_folds: int = 4, seed: int = C.RANDOM_STATE,
               force_class_weight: str = "search") -> np.ndarray:
    """Each row is scored by a pipeline whose preprocessing and tuning saw no row from its outer fold."""
    y_arr = np.asarray(y)
    result = np.full(len(y_arr), np.nan)
    outer = StratifiedKFold(outer_folds, shuffle=True, random_state=seed)
    for fold, (train_idx, valid_idx) in enumerate(outer.split(X, y_arr)):
        search = search_for(name, seed + fold, inner_folds, force_class_weight)
        search.fit(X.iloc[train_idx], y_arr[train_idx])
        result[valid_idx] = search.predict_proba(X.iloc[valid_idx])[:, 1]
    if not np.isfinite(result).all():
        raise RuntimeError("Nested CV did not produce exactly one prediction per row.")
    return result


def fit_tuned(name: str, X: pd.DataFrame, y: pd.Series, seed: int = C.RANDOM_STATE,
              inner_folds: int = 5):
    search = search_for(name, seed, inner_folds)
    search.fit(X, y)
    return search.best_estimator_, search.best_params_, float(search.best_score_)


def metrics(y_true, proba, threshold: float) -> dict:
    y = np.asarray(y_true, dtype=int)
    p = np.asarray(proba, dtype=float)
    pred = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    specificity = float(tn / (tn + fp)) if tn + fp else float("nan")
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "specificity": specificity,
        "f1": float(f1_score(y, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "false_negative_rate": float(fn / (fn + tp)) if fn + tp else float("nan"),
        "brier": float(brier_score_loss(y, p)),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }


def choose_threshold(y, oof, target_recall: float = 0.65, minimum_precision: float = 0.50):
    """Predeclared rule: highest threshold meeting recall and precision constraints."""
    candidates = np.unique(np.r_[0.0, np.asarray(oof, dtype=float), 1.0])
    table = pd.DataFrame([{"threshold": float(t), **metrics(y, oof, float(t))}
                          for t in candidates])
    feasible = table[(table.recall >= target_recall) & (table.precision >= minimum_precision)]
    chosen = None if feasible.empty else float(feasible.threshold.max())
    return chosen, table


def stratified_bootstrap_ci(y_true, proba, threshold: float, n_boot: int = 2000,
                            seed: int = C.RANDOM_STATE, alpha: float = 0.05) -> dict:
    """Percentile intervals resampling positives and negatives separately; conditional on this split."""
    y = np.asarray(y_true, dtype=int)
    p = np.asarray(proba, dtype=float)
    groups = [np.flatnonzero(y == k) for k in (0, 1)]
    rng = np.random.default_rng(seed)
    names = ("accuracy", "balanced_accuracy", "precision", "recall", "specificity",
             "f1", "roc_auc", "pr_auc", "false_negative_rate", "brier")
    draws = {name: [] for name in names}
    for _ in range(n_boot):
        idx = np.concatenate([rng.choice(g, size=len(g), replace=True) for g in groups])
        m = metrics(y[idx], p[idx], threshold)
        for name in names:
            draws[name].append(m[name])
    return {name: [float(np.quantile(vals, alpha / 2)), float(np.quantile(vals, 1 - alpha / 2))]
            for name, vals in draws.items()}


def calibration_bins(y_true, proba, bins: int = 8) -> pd.DataFrame:
    y = np.asarray(y_true, dtype=int)
    p = np.asarray(proba, dtype=float)
    cuts = np.linspace(0, 1, bins + 1)
    rows = []
    for i in range(bins):
        mask = (p >= cuts[i]) & ((p < cuts[i + 1]) if i < bins - 1 else (p <= cuts[i + 1]))
        if mask.any():
            rows.append({"bin_low": cuts[i], "bin_high": cuts[i + 1], "count": int(mask.sum()),
                         "mean_predicted": float(p[mask].mean()), "observed_fraction": float(y[mask].mean())})
    return pd.DataFrame(rows)
