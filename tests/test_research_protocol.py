import numpy as np
import pandas as pd
import pytest

from src.research import (MODEL_GRIDS, choose_threshold, metrics, nested_oof,
                          search_for, select_family)


def test_research_metrics_include_recall_and_error_complements():
    y = np.array([1, 1, 1, 0, 0, 0])
    p = np.array([0.9, 0.4, 0.7, 0.8, 0.2, 0.1])
    result = metrics(y, p, 0.5)
    assert result["tp"] == 2 and result["fn"] == 1
    assert result["fp"] == 1 and result["tn"] == 2
    assert result["recall"] == pytest.approx(2 / 3)
    assert result["specificity"] == pytest.approx(2 / 3)
    assert result["false_negative_rate"] == pytest.approx(1 / 3)
    assert result["balanced_accuracy"] == pytest.approx(2 / 3)
    assert 0 <= result["pr_auc"] <= 1


def test_threshold_requires_predeclared_recall_and_precision_constraints():
    y = np.array([1, 1, 1, 0, 0, 0, 0, 0])
    p = np.array([0.9, 0.7, 0.3, 0.8, 0.6, 0.2, 0.1, 0.05])
    threshold, table = choose_threshold(y, p, target_recall=2 / 3, minimum_precision=0.60)
    assert threshold == pytest.approx(0.7)
    row = table[table.threshold == threshold].iloc[0]
    assert row.recall >= 2 / 3 and row.precision >= 0.60


def test_threshold_reports_infeasible_objective():
    y = np.array([1, 1, 0, 0])
    threshold, _ = choose_threshold(y, np.array([0.6, 0.5, 0.9, 0.8]),
                                    target_recall=1.0, minimum_precision=0.9)
    assert threshold is None


def test_selection_ties_prefer_simple_approved_model():
    table = pd.DataFrame([
        {"model": "Random Forest", "roc_auc": 0.811},
        {"model": "Logistic Regression", "roc_auc": 0.808},
        {"model": "SVM (RBF)", "roc_auc": 0.810},
    ])
    assert select_family(table) == "Logistic Regression"


def test_search_preprocessing_is_inside_each_tuned_pipeline():
    search = search_for("Logistic Regression", inner_folds=3)
    assert [step[0] for step in search.estimator.steps] == ["zero_to_nan", "impute", "scale", "model"]
    assert search.cv.get_n_splits() == 3
    assert set(MODEL_GRIDS) >= {"Logistic Regression", "Gaussian Naive Bayes", "Random Forest",
                               "SVM (RBF)", "Gradient Boosting"}
    balanced = search_for("Logistic Regression", inner_folds=3, force_class_weight="balanced")
    assert balanced.param_grid["model__class_weight"] == ["balanced"]
    unweighted = search_for("Logistic Regression", inner_folds=3, force_class_weight=None)
    assert unweighted.param_grid["model__class_weight"] == [None]


def test_nested_oof_is_repeatable_and_returns_one_probability_per_row():
    rng = np.random.default_rng(8)
    x = rng.normal(size=(90, 8))
    y = (x[:, 0] + x[:, 1] > 0).astype(int)
    X = pd.DataFrame(x, columns=[
        "Pregnancies", "Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI",
        "DiabetesPedigreeFunction", "Age",
    ])
    a = nested_oof("Logistic Regression", X, pd.Series(y), outer_folds=3, inner_folds=2, seed=17)
    b = nested_oof("Logistic Regression", X, pd.Series(y), outer_folds=3, inner_folds=2, seed=17)
    assert a.shape == (90,)
    assert np.isfinite(a).all() and ((a >= 0) & (a <= 1)).all()
    np.testing.assert_allclose(a, b)
