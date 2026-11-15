"""Model comparison, selection rule and metric arithmetic."""
import numpy as np
import pandas as pd
import pytest

from src import config as C
from src.modeling import (bootstrap_ci, compute_metrics, cross_validate_models, make_cv,
                          select_best_model, threshold_for_recall, threshold_table)


def cv_table(rows):
    return pd.DataFrame([{"model": m, "roc_auc_mean": a, "f1_mean": f, "accuracy_mean": c} for m, a, f, c in rows])


def test_clear_auc_winner_is_selected():
    t = cv_table([("Logistic Regression", .80, .60, .75), ("Gaussian Naive Bayes", .83, .55, .70),
                  ("Random Forest", .85, .50, .70)])
    assert select_best_model(t)[0] == "Random Forest"


def test_auc_tie_is_broken_by_f1():
    # LR and RF are only 0.002 apart in AUC -> tie -> the higher F1 wins; NB is far behind.
    t = cv_table([("Logistic Regression", .840, .60, .75), ("Gaussian Naive Bayes", .700, .70, .75),
                  ("Random Forest", .838, .66, .75)])
    assert select_best_model(t)[0] == "Random Forest"


def test_f1_tie_is_broken_by_accuracy():
    t = cv_table([("Logistic Regression", .84, .650, .74), ("Gaussian Naive Bayes", .70, .65, .90),
                  ("Random Forest", .84, .652, .76)])
    assert select_best_model(t)[0] == "Random Forest"


def test_full_tie_prefers_the_simplest_model():
    t = cv_table([(m, .84, .65, .75) for m in C.MODEL_ORDER])
    winner, log = select_best_model(t)
    assert winner == "Logistic Regression"
    assert any("simplest" in line for line in log)


def test_a_gap_just_above_the_tolerance_is_not_a_tie():
    t = cv_table([("Logistic Regression", .840, .50, .70), ("Gaussian Naive Bayes", .60, .50, .70),
                  ("Random Forest", .846, .40, .60)])
    assert select_best_model(t)[0] == "Random Forest"          # 0.006 > 0.005


def test_metrics_match_a_hand_calculation():
    # 10 patients, 4 diabetic. At threshold 0.5 the model finds 3 of them and wrongly flags 2 healthy people.
    y = np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0])
    p = np.array([.9, .8, .7, .2, .6, .55, .1, .1, .1, .1])
    m = compute_metrics(y, p, 0.5)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (3, 2, 1, 4)
    assert m["accuracy"] == pytest.approx(7 / 10)
    assert m["precision"] == pytest.approx(3 / 5)
    assert m["recall"] == pytest.approx(3 / 4)
    assert m["specificity"] == pytest.approx(4 / 6)
    assert m["f1"] == pytest.approx(2 * (3 / 5) * (3 / 4) / ((3 / 5) + (3 / 4)))
    assert m["roc_auc"] == pytest.approx(22 / 24)               # 22 of the 24 (diabetic, healthy) pairs are ordered right


def test_threshold_for_recall_picks_the_highest_qualifying_threshold():
    t = pd.DataFrame({"threshold": [.2, .3, .4, .5], "recall": [.95, .80, .66, .50]})
    assert threshold_for_recall(t, .65) == .4
    assert threshold_for_recall(t, .99) is None


def test_lower_threshold_never_lowers_recall(synthetic_split, fitted_synthetic):
    _, X_test, _, y_test = synthetic_split
    proba = fitted_synthetic["Logistic Regression"].predict_proba(X_test)[:, 1]
    table = threshold_table(y_test, proba)
    assert table["recall"].is_monotonic_decreasing                # raising the threshold can only lose recall


def test_bootstrap_interval_is_reproducible_and_brackets_the_estimate(synthetic_split, fitted_synthetic):
    _, X_test, _, y_test = synthetic_split
    proba = fitted_synthetic["Logistic Regression"].predict_proba(X_test)[:, 1]
    first, second = bootstrap_ci(y_test, proba, n_boot=300), bootstrap_ci(y_test, proba, n_boot=300)
    assert first == second
    point = compute_metrics(y_test, proba)
    for metric, (lo, hi) in first.items():
        assert lo <= hi
        assert lo - 0.05 <= point[metric] <= hi + 0.05


def test_cross_validation_table_has_the_expected_shape(synthetic_split):
    X_train, _, y_train, _ = synthetic_split
    t = cross_validate_models(X_train, y_train, cv=make_cv(3))
    assert list(t.model) == C.MODEL_ORDER
    for metric in ("roc_auc", "f1", "accuracy", "precision", "recall"):
        assert t[f"{metric}_mean"].between(0, 1).all()
        assert (t[f"{metric}_std"] >= 0).all()
    assert (t["roc_auc_mean"] > 0.6).all()                       # the fake labels depend on glucose and BMI


def test_the_same_seed_gives_the_same_model(synthetic_split):
    from src.modeling import fit_models
    X_train, X_test, y_train, _ = synthetic_split
    a, b = fit_models(X_train, y_train), fit_models(X_train, y_train)
    for name in a:
        np.testing.assert_allclose(a[name].predict_proba(X_test), b[name].predict_proba(X_test))
