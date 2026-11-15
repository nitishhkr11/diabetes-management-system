"""Train, compare and choose models - the SAME workflow for every model."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss,
                             confusion_matrix, f1_score, matthews_corrcoef,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_validate
from sklearn.naive_bayes import GaussianNB

from . import config as C
from .preprocessing import build_pipeline

CV_SCORING = {"roc_auc": "roc_auc", "f1": "f1", "accuracy": "accuracy",
              "precision": "precision", "recall": "recall"}


def get_models(random_state: int = C.RANDOM_STATE) -> dict:
    """The three contrasting models of the project (names are used everywhere)."""
    return {
        "Logistic Regression": LogisticRegression(max_iter=1000, random_state=random_state),
        "Gaussian Naive Bayes": GaussianNB(),
        "Random Forest": RandomForestClassifier(n_estimators=300, random_state=random_state, n_jobs=-1),
    }


def make_cv(folds: int = C.CV_FOLDS, random_state: int = C.RANDOM_STATE) -> StratifiedKFold:
    return StratifiedKFold(n_splits=folds, shuffle=True, random_state=random_state)


# ------------------------------------------------------------ cross-validation
def cross_validate_models(X_train, y_train, models: dict | None = None, cv=None) -> pd.DataFrame:
    """5-fold stratified CV on the TRAINING part only. The test part is never touched."""
    models = models or get_models()
    cv = cv or make_cv()
    rows = []
    for name, estimator in models.items():
        res = cross_validate(build_pipeline(clone(estimator)), X_train, y_train,
                             cv=cv, scoring=CV_SCORING, n_jobs=1)
        row = {"model": name}
        for metric in CV_SCORING:
            scores = res[f"test_{metric}"]
            row[f"{metric}_mean"] = float(scores.mean())
            row[f"{metric}_std"] = float(scores.std(ddof=1))
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------- model selection
def select_best_model(cv_table: pd.DataFrame, tol: float = C.TIE_TOLERANCE,
                      order: list | None = None):
    """Apply the project rule: ROC-AUC first, then F1, then Accuracy.

    Exact ties never happen with real numbers, so two scores closer than `tol`
    count as a tie. If everything is still tied, the simplest model wins.
    Returns (winner, list_of_explanation_lines).
    """
    order = order or C.MODEL_ORDER
    table = cv_table.set_index("model")
    candidates = list(table.index)
    log = []
    for metric in ("roc_auc", "f1", "accuracy"):
        col = f"{metric}_mean"
        best = table.loc[candidates, col].max()
        kept = [m for m in candidates if table.loc[m, col] >= best - tol]
        log.append(f"Step {metric}: best = {best:.4f}; models within {tol}: {', '.join(kept)}")
        candidates = kept
        if len(candidates) == 1:
            break
    winner = min(candidates, key=lambda m: order.index(m) if m in order else len(order))
    if len(candidates) > 1:
        log.append(f"Still tied after all three steps -> simplest model wins: {winner}")
    log.append(f"SELECTED: {winner}")
    return winner, log


# --------------------------------------------------------------- fit + metrics
def fit_models(X_train, y_train, models: dict | None = None) -> dict:
    """Fit every model (inside its own Pipeline) on the training part."""
    models = models or get_models()
    return {name: build_pipeline(clone(est)).fit(X_train, y_train) for name, est in models.items()}


def compute_metrics(y_true, proba, threshold: float = C.DECISION_THRESHOLD) -> dict:
    """All metrics from true labels + predicted probabilities of the positive class."""
    y_true = np.asarray(y_true)
    proba = np.asarray(proba, dtype=float)
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        "accuracy": accuracy_score(y_true, pred),
        "precision": precision_score(y_true, pred, zero_division=0),
        "recall": recall_score(y_true, pred, zero_division=0),
        "f1": f1_score(y_true, pred, zero_division=0),
        "roc_auc": roc_auc_score(y_true, proba),
        "specificity": tn / (tn + fp) if (tn + fp) else float("nan"),
        "mcc": matthews_corrcoef(y_true, pred),
        "brier": brier_score_loss(y_true, proba),
        "avg_precision": average_precision_score(y_true, proba),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }


def evaluate_models(fitted: dict, X_test, y_test, threshold: float = C.DECISION_THRESHOLD) -> pd.DataFrame:
    rows = []
    for name, pipe in fitted.items():
        rows.append({"model": name, **compute_metrics(y_test, pipe.predict_proba(X_test)[:, 1], threshold)})
    return pd.DataFrame(rows)


def bootstrap_ci(y_true, proba, threshold: float = C.DECISION_THRESHOLD,
                 n_boot: int = 2000, seed: int = C.RANDOM_STATE, alpha: float = 0.05) -> dict:
    """95% bootstrap interval for each metric: resample the TEST rows with replacement."""
    y_true = np.asarray(y_true)
    proba = np.asarray(proba, dtype=float)
    rng = np.random.default_rng(seed)
    draws = {k: [] for k in ("accuracy", "precision", "recall", "f1", "roc_auc")}
    for _ in range(n_boot):
        idx = rng.integers(0, len(y_true), len(y_true))
        if len(np.unique(y_true[idx])) < 2:
            continue
        m = compute_metrics(y_true[idx], proba[idx], threshold)
        for k in draws:
            draws[k].append(m[k])
    return {k: (float(np.percentile(v, 100 * alpha / 2)), float(np.percentile(v, 100 * (1 - alpha / 2))))
            for k, v in draws.items()}


# ------------------------------------------------------------ threshold study
def oof_probabilities(estimator, X_train, y_train, cv=None) -> np.ndarray:
    """Out-of-fold probabilities: each training row is scored by a model that never saw it."""
    cv = cv or make_cv()
    return cross_val_predict(build_pipeline(clone(estimator)), X_train, y_train,
                             cv=cv, method="predict_proba")[:, 1]


def threshold_table(y_true, proba, thresholds=None) -> pd.DataFrame:
    thresholds = np.round(np.arange(0.10, 0.901, 0.05), 2) if thresholds is None else thresholds
    rows = []
    for t in thresholds:
        m = compute_metrics(y_true, proba, float(t))
        rows.append({"threshold": float(t), **{k: m[k] for k in ("precision", "recall", "f1", "accuracy", "specificity")},
                     "tp": m["tp"], "fp": m["fp"], "fn": m["fn"], "tn": m["tn"]})
    return pd.DataFrame(rows)


def threshold_for_recall(table: pd.DataFrame, min_recall: float):
    """Highest threshold whose recall is still >= min_recall (None if impossible)."""
    ok = table[table["recall"] >= min_recall]
    return None if ok.empty else float(ok["threshold"].max())
