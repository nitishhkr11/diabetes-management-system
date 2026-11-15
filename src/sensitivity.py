"""Helpers for the one-feature model-sensitivity explorer."""
from __future__ import annotations

from . import config as C


def sensitivity_bounds(profile: dict, feature: str) -> tuple[float, float]:
    """Use the feature's training 5th–95th percentiles as exploration bounds."""
    if feature not in C.FEATURES:
        raise ValueError(f"Unknown feature: {feature}")
    values = profile[feature]
    low, high = float(values.get("q05", values["min"])), float(values.get("q95", values["max"]))
    if low > high:
        raise ValueError(f"Invalid training quantiles for {feature}: {low} > {high}")
    return low, high


def vary_feature(base_case: dict, feature: str, value: float) -> dict:
    """Return a modified case without mutating the submitted base case."""
    if feature not in C.FEATURES:
        raise ValueError(f"Unknown feature: {feature}")
    varied = dict(base_case)
    varied[feature] = float(value)
    return varied
