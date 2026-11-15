"""The 'mistake recipes' must really do what their documentation says - otherwise the
leakage experiments would measure the wrong thing."""
import numpy as np
import pytest

from src import config as C
from src.leaky_recipes import class_conditional_fill, class_medians, enlarged_copy, global_prepare, oversample_before_split


def test_class_conditional_fill_writes_one_constant_per_class(real_df):
    filled = class_conditional_fill(real_df)
    consts = class_medians(real_df)
    for col in C.ZERO_AS_MISSING:
        assert (filled[col] > 0).all()                                      # no zeros are left
        for cls, label in ((0, "class 0 (no diabetes)"), (1, "class 1 (diabetes)")):
            was_zero = (real_df[col] == 0) & (real_df[C.TARGET] == cls)
            assert (filled.loc[was_zero, col] == consts.loc[col, label]).all()
    untouched = ~(real_df[C.ZERO_AS_MISSING] == 0).any(axis=1)
    np.testing.assert_array_equal(filled.loc[untouched, C.FEATURES].to_numpy(),
                                  real_df.loc[untouched, C.FEATURES].to_numpy())   # measured rows unchanged


def test_the_constants_match_the_ones_found_in_public_repositories(real_df):
    c = class_medians(real_df)
    assert c.loc["Glucose"].tolist() == [107.0, 140.0]
    assert c.loc["BloodPressure"].tolist() == [70.0, 74.5]
    assert c.loc["SkinThickness"].tolist() == [27.0, 32.0]
    assert c.loc["Insulin"].tolist() == [102.5, 169.5]
    assert c.loc["BMI"].tolist() == [30.1, 34.3]


def test_the_filled_value_reveals_the_label(synthetic_df):
    filled = class_conditional_fill(synthetic_df)
    rows = synthetic_df["Insulin"] == 0
    # for the rows that were unknown, the filled number alone separates the classes perfectly
    values = filled.loc[rows].groupby(C.TARGET)["Insulin"].nunique()
    assert (values == 1).all()
    assert filled.loc[rows & (synthetic_df[C.TARGET] == 0), "Insulin"].iloc[0] != \
        filled.loc[rows & (synthetic_df[C.TARGET] == 1), "Insulin"].iloc[0]


def test_global_prepare_standardises_with_all_rows(synthetic_df):
    out = global_prepare(synthetic_df)
    np.testing.assert_allclose(out[C.FEATURES].mean().to_numpy(), 0, atol=1e-9)
    np.testing.assert_allclose(out[C.FEATURES].std(ddof=0).to_numpy(), 1, atol=1e-9)
    assert not out.isna().any().any()


def test_oversampling_balances_the_classes_by_duplicating_rows(synthetic_df):
    out = oversample_before_split(synthetic_df, seed=0)
    counts = out[C.TARGET].value_counts()
    assert counts[0] == counts[1]
    assert out.duplicated().sum() >= counts[1] - (synthetic_df[C.TARGET] == 1).sum() - 1


def test_enlarged_copy_has_the_expected_size_and_repeats(real_df):
    out = enlarged_copy(real_df, seed=0)
    assert len(out) == len(real_df) + 2000
    assert out.duplicated().sum() >= 1900                  # almost all extra rows repeat genuine rows
    assert out.iloc[: len(real_df)].reset_index(drop=True).equals(real_df.reset_index(drop=True))


@pytest.mark.parametrize("fn", [class_conditional_fill, global_prepare])
def test_recipes_do_not_modify_their_input(fn, synthetic_df):
    before = synthetic_df.copy()
    fn(synthetic_df)
    assert synthetic_df.equals(before)
