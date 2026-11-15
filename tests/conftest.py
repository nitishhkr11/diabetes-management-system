"""Shared test fixtures.

The tests never touch your real data/predictions.db or models/ folder: they use a
small FAKE table (not real patients) and temporary folders. Tests that need the
genuine Pima file are skipped automatically if it has not been downloaded.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config as C  # noqa: E402
from src import modeling as M  # noqa: E402
from src.data_validation import load_dataset  # noqa: E402
from src.preprocessing import split_data  # noqa: E402


def make_synthetic(n: int = 400, seed: int = 0) -> pd.DataFrame:
    """A fake 'Pima-like' table: same columns, similar ranges, zeros as missing codes."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "Pregnancies": rng.poisson(3.5, n).clip(0, 17),
        "Glucose": rng.normal(120, 30, n).clip(60, 199).round(),
        "BloodPressure": rng.normal(72, 12, n).clip(40, 122).round(),
        "SkinThickness": rng.normal(29, 10, n).clip(7, 99).round(),
        "Insulin": rng.gamma(2.0, 70, n).clip(14, 846).round(),
        "BMI": rng.normal(32, 6.5, n).clip(18, 67).round(1),
        "DiabetesPedigreeFunction": rng.gamma(2.0, 0.24, n).clip(0.08, 2.42).round(3),
        "Age": (21 + rng.gamma(2.0, 7.0, n)).clip(21, 81).round(),
    })
    logit = (-9.0 + 0.035 * df["Glucose"] + 0.07 * df["BMI"] + 0.03 * df["Age"]
             + 0.7 * df["DiabetesPedigreeFunction"])
    df["Outcome"] = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    for col, share in (("BloodPressure", 0.05), ("SkinThickness", 0.30), ("Insulin", 0.45),
                       ("BMI", 0.02), ("Glucose", 0.01)):
        df.loc[rng.random(n) < share, col] = 0
    return df


@pytest.fixture(scope="session")
def synthetic_df() -> pd.DataFrame:
    return make_synthetic()


@pytest.fixture(scope="session")
def real_df() -> pd.DataFrame:
    if not C.DATA_PATH.exists():                  # not downloaded yet -> skip (and say why)
        pytest.skip("data/diabetes.csv not found - run: python scripts/download_data.py")
    return load_dataset()                         # a file that EXISTS but fails validation is a failure, not a skip


@pytest.fixture(scope="session")
def synthetic_split(synthetic_df):
    return split_data(synthetic_df)


@pytest.fixture(scope="session")
def fitted_synthetic(synthetic_split):
    X_train, _, y_train, _ = synthetic_split
    return M.fit_models(X_train, y_train)
