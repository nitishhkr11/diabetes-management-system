"""Cleaning + preprocessing, built as ONE scikit-learn Pipeline.

Key idea (data leakage): anything that LEARNS from data (the median used to fill
gaps, the mean/std used for scaling) must be learned from the TRAINING rows only.
A Pipeline guarantees that: when we call pipeline.fit(X_train, y_train) every
step learns from X_train only, and later applies what it learned to new rows.

Putting the "0 means missing" rule inside the pipeline also guarantees that the
online inference API treats a supplied 0 exactly the way training did.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, OneToOneFeatureMixin, TransformerMixin
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from . import config as C


class ZeroToNaN(OneToOneFeatureMixin, TransformerMixin, BaseEstimator):
    """Turn 0 into NaN ("missing") in the chosen columns. Nothing is learned here."""

    def __init__(self, columns=None):
        self.columns = columns

    def _cols(self):
        return list(C.ZERO_AS_MISSING if self.columns is None else self.columns)

    def fit(self, X, y=None):
        missing = [c for c in self._cols() if c not in X.columns]
        if missing:
            raise ValueError(f"Columns not found: {missing}")
        self.feature_names_in_ = np.array(X.columns, dtype=object)
        self.n_features_in_ = X.shape[1]
        return self

    def transform(self, X):
        X = X.copy()                      # never modify the caller's data
        for col in self._cols():
            X[col] = X[col].astype("float64").where(X[col] != 0, np.nan)
        return X


def build_pipeline(model) -> Pipeline:
    """zero->NaN, median imputation, standardisation, then the classifier."""
    pipe = Pipeline([
        ("zero_to_nan", ZeroToNaN(C.ZERO_AS_MISSING)),
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("model", model),
    ])
    pipe.set_output(transform="pandas")   # keep column names (needed for SHAP)
    return pipe


def split_data(df: pd.DataFrame, test_size: float = C.TEST_SIZE, random_state: int = C.RANDOM_STATE):
    """Stratified split: both parts keep the same share of diabetic patients."""
    X, y = df[C.FEATURES], df[C.TARGET]
    return train_test_split(X, y, test_size=test_size, random_state=random_state, stratify=y)


def training_profile(X_train: pd.DataFrame) -> dict:
    """Median/min/max per feature AFTER treating zeros as missing.

    Saved with the model so the app can warn when an input is outside the range
    the model has ever seen (see predict.py).
    """
    clean = ZeroToNaN(C.ZERO_AS_MISSING).fit(X_train).transform(X_train)
    return {
        c: {
            "median": float(clean[c].median()), "min": float(clean[c].min()),
            "max": float(clean[c].max()), "q05": float(clean[c].quantile(0.05)),
            "q95": float(clean[c].quantile(0.95)),
        }
        for c in C.FEATURES
    }
