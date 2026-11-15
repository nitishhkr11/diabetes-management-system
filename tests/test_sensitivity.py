import pytest

from src import config as C
from src.sensitivity import sensitivity_bounds, vary_feature


def test_sensitivity_uses_training_quantile_bounds(synthetic_split):
    x_train, *_ = synthetic_split
    profile = {"Glucose": {"min": 44, "max": 199, "q05": 67.5, "q95": 171}}
    assert sensitivity_bounds(profile, "Glucose") == (67.5, 171.0)


def test_vary_feature_does_not_mutate_base_case():
    base = {feature: 1.0 for feature in C.FEATURES}
    result = vary_feature(base, "Glucose", 145)
    assert result["Glucose"] == 145
    assert base["Glucose"] == 1.0
    assert result is not base


def test_sensitivity_rejects_unknown_feature():
    with pytest.raises(ValueError, match="Unknown feature"):
        sensitivity_bounds({}, "Name")
