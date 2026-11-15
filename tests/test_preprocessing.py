"""Cleaning rules and the anti-leakage design of the pipeline."""
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from src import config as C
from src.preprocessing import ZeroToNaN, build_pipeline, split_data, training_profile


def test_zero_to_nan_converts_only_the_five_columns():
    X = pd.DataFrame([{**{f: 1.0 for f in C.FEATURES}, "Pregnancies": 0, "Glucose": 0, "Insulin": 0}])
    out = ZeroToNaN().fit(X).transform(X)
    assert out.loc[0, "Pregnancies"] == 0                   # a valid answer: never pregnant
    assert np.isnan(out.loc[0, "Glucose"]) and np.isnan(out.loc[0, "Insulin"])
    assert X.loc[0, "Glucose"] == 0                          # the caller's data is untouched


def test_pipeline_statistics_come_from_the_training_rows_only(synthetic_split):
    X_train, X_test, y_train, _ = synthetic_split
    pipe = build_pipeline(LogisticRegression(max_iter=1000)).fit(X_train, y_train)
    clean = ZeroToNaN().fit(X_train).transform(X_train)
    np.testing.assert_allclose(pipe.named_steps["impute"].statistics_, clean[C.FEATURES].median().to_numpy())
    np.testing.assert_allclose(pipe.named_steps["scale"].mean_, clean.fillna(clean.median()).mean().to_numpy())


def test_scoring_new_rows_does_not_change_what_was_learned(synthetic_split):
    X_train, X_test, y_train, _ = synthetic_split
    pipe = build_pipeline(LogisticRegression(max_iter=1000)).fit(X_train, y_train)
    before = (pipe.named_steps["scale"].mean_.copy(), pipe.named_steps["impute"].statistics_.copy())
    pipe.predict_proba(X_test * 100)                          # absurd rows must not leak into the pipeline
    np.testing.assert_array_equal(pipe.named_steps["scale"].mean_, before[0])
    np.testing.assert_array_equal(pipe.named_steps["impute"].statistics_, before[1])


def test_a_typed_zero_and_a_missing_value_give_identical_predictions(fitted_synthetic, synthetic_split):
    _, X_test, _, _ = synthetic_split
    row = X_test.iloc[[0]].copy()
    as_zero, as_nan = row.copy(), row.copy()
    as_zero["Insulin"], as_nan["Insulin"] = 0.0, np.nan
    for name, pipe in fitted_synthetic.items():
        assert pipe.predict_proba(as_zero)[0, 1] == pytest.approx(pipe.predict_proba(as_nan)[0, 1]), name


def test_split_is_stratified_reproducible_and_disjoint(synthetic_df):
    X_train, X_test, y_train, y_test = split_data(synthetic_df)
    again = split_data(synthetic_df)
    other = split_data(synthetic_df, random_state=7)
    assert abs(y_train.mean() - y_test.mean()) < 0.02
    assert set(X_train.index).isdisjoint(X_test.index)
    assert len(X_train) + len(X_test) == len(synthetic_df)
    assert list(X_train.index) == list(again[0].index)
    assert list(X_train.index) != list(other[0].index)


def test_training_profile_ignores_the_placeholder_zeros(synthetic_split):
    X_train, _, _, _ = synthetic_split
    prof = training_profile(X_train)
    assert prof["Glucose"]["min"] > 0 and prof["Insulin"]["min"] > 0
    assert prof["Pregnancies"]["min"] == X_train["Pregnancies"].min()      # zero is a real answer there
