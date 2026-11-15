"""The dataset checks must accept the genuine Pima file and reject its look-alikes."""
import io

import pandas as pd
import pytest

from src import config as C
from src.data_validation import (INTEGER_COLUMNS, DatasetError, canonical_sha256, load_dataset,
                                 sha256_file, validate_dataframe)


def by_name(report):
    return {c.name: c for c in report.checks}


def test_genuine_file_is_accepted(real_df):
    rep = validate_dataframe(real_df)
    assert rep.ok, rep.to_text()
    assert rep.canonical_sha256 == C.KNOWN_CANONICAL_SHA256


def test_canonical_hash_ignores_line_endings_and_number_format(synthetic_df):
    as_floats = synthetic_df.astype({c: "float64" for c in INTEGER_COLUMNS})      # "31" becomes "31.0"
    text = as_floats.to_csv(index=False, lineterminator="\r\n")                    # Windows line endings
    reread = pd.read_csv(io.StringIO(text))
    assert canonical_sha256(reread) == canonical_sha256(synthetic_df)


def test_canonical_hash_changes_when_one_value_changes(synthetic_df):
    other = synthetic_df.copy()
    other.loc[0, "Glucose"] = other.loc[0, "Glucose"] + 1
    assert canonical_sha256(other) != canonical_sha256(synthetic_df)


def test_raw_file_hash_changes_with_one_byte(tmp_path):
    p = tmp_path / "a.bin"
    p.write_bytes(b"abc")
    first = sha256_file(p)
    p.write_bytes(b"abd")
    assert sha256_file(p) != first


def test_other_column_names_are_rejected_with_a_hint(synthetic_df):
    renamed = synthetic_df.rename(columns={"Pregnancies": "num_preg", "Glucose": "glucose_conc"})
    rep = validate_dataframe(renamed)
    assert not rep.ok
    assert any("Different schema" in h for h in rep.hints)


def test_extra_id_column_is_reported_but_the_rest_is_still_checked(real_df):
    with_id = real_df.copy()
    with_id.insert(0, "Id", range(len(with_id)))
    rep = validate_dataframe(with_id)
    assert not rep.ok
    assert any("Id column" in h for h in rep.hints)
    assert "row count" in by_name(rep)          # validation did not stop at the column check


def test_copy_with_filled_zeros_is_rejected_and_explained(real_df):
    filled = real_df.copy()
    for col in C.ZERO_AS_MISSING:
        measured = filled[col] != 0
        filled[col] = filled[col].where(measured, filled.loc[measured, col].median())
    rep = validate_dataframe(filled)
    assert not rep.ok
    assert any("ALREADY filled" in h for h in rep.hints)


def test_enlarged_copy_with_repeated_rows_is_rejected(real_df):
    bigger = pd.concat([real_df, real_df.sample(200, random_state=1)], ignore_index=True)
    rep = validate_dataframe(bigger)
    checks = by_name(rep)
    assert not rep.ok
    assert not checks["row count"].passed
    assert not checks["duplicate rows"].passed
    assert any("enlarged copy" in h for h in rep.hints)


def test_lenient_mode_accepts_a_valid_table_that_is_not_pima(synthetic_df):
    assert not validate_dataframe(synthetic_df, strict=True).ok
    assert validate_dataframe(synthetic_df, strict=False).ok


def test_labels_other_than_0_and_1_are_rejected(synthetic_df):
    bad = synthetic_df.copy()
    bad.loc[0, "Outcome"] = 2
    rep = validate_dataframe(bad, strict=False)
    assert not rep.ok
    assert not by_name(rep)["labels are 0/1"].passed


def test_missing_file_gives_a_helpful_message(tmp_path):
    with pytest.raises(DatasetError, match="download_data"):
        load_dataset(tmp_path / "nope.csv")
