"""Recipes that LEAK information - written down so we can measure the damage. NEVER use them to train.

Each function reproduces a mistake that is common in public notebooks and repositories.
scripts/experiments.py (experiment B) and scripts/leakage_demo.py use them to show, with
numbers, how much each mistake inflates the test score compared with the correct
Pipeline in src/preprocessing.py.
"""
from __future__ import annotations

import pandas as pd

from . import config as C


def class_conditional_fill(df: pd.DataFrame) -> pd.DataFrame:
    """Replace each 0 by the median of the SAME CLASS (diabetic / not diabetic).

    Why it leaks: the filled value now depends on the label. For a row whose Insulin was
    unknown, 102.5 means "not diabetic" and 169.5 means "diabetic" - the answer is written
    into the feature. At prediction time the label is unknown, so this cannot be reproduced.
    """
    out = df.copy().astype({c: "float64" for c in C.ZERO_AS_MISSING})
    for col in C.ZERO_AS_MISSING:
        for cls in (0, 1):
            in_class = out[C.TARGET] == cls
            out.loc[in_class & (out[col] == 0), col] = out.loc[in_class & (out[col] != 0), col].median()
    return out


def class_medians(df: pd.DataFrame) -> pd.DataFrame:
    """The constants that class_conditional_fill writes into the file (class 0, class 1)."""
    rows = {c: [float(df.loc[(df[C.TARGET] == k) & (df[c] != 0), c].median()) for k in (0, 1)]
            for c in C.ZERO_AS_MISSING}
    return pd.DataFrame(rows, index=["class 0 (no diabetes)", "class 1 (diabetes)"]).T


def global_prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Zero -> missing, median fill and standardise using ALL rows, test rows included.

    A mild leak: the test rows influence the medians, means and standard deviations.
    """
    X = df[C.FEATURES].astype("float64")
    for col in C.ZERO_AS_MISSING:
        X[col] = X[col].where(X[col] != 0)
    X = X.fillna(X.median())
    X = (X - X.mean()) / X.std(ddof=0)
    return X.assign(**{C.TARGET: df[C.TARGET].to_numpy()})


def oversample_before_split(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Randomly duplicate diabetic rows until the classes are 500:500 - BEFORE splitting.

    Why it leaks: duplicates of the same patient end up on both sides of the split, so the
    test set contains rows the model has already memorised.
    """
    minority = df[df[C.TARGET] == 1]
    extra = minority.sample(n=int((df[C.TARGET] == 0).sum() - len(minority)), replace=True, random_state=seed)
    return pd.concat([df, extra], ignore_index=True)


def enlarged_copy(df: pd.DataFrame, seed: int, extra_rows: int = 2000) -> pd.DataFrame:
    """768 real rows + `extra_rows` rows sampled WITH replacement from them (2,768 rows in total).

    This imitates a look-alike file seen in public repositories, in which 1,981 of the 2,000
    extra rows were exact copies of genuine rows. A random split then puts copies of training
    patients into the test set.
    """
    return pd.concat([df, df.sample(n=extra_rows, replace=True, random_state=seed)], ignore_index=True)
