"""Check that a CSV really is the Pima Indians Diabetes dataset BEFORE training.

Why this matters: many different files are called "diabetes.csv". Some have the
same column names but different rows (duplicates added, zeros already filled in,
...). Training on the wrong file silently gives wrong results.

Run it on its own:   python -m src.data_validation data/diabetes.csv
"""
from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import config as C

INTEGER_COLUMNS = ["Pregnancies", "Glucose", "BloodPressure", "SkinThickness",
                   "Insulin", "Age", C.TARGET]


class DatasetError(ValueError):
    """Raised when the dataset is missing or fails a blocking check."""


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    blocking: bool = True


@dataclass
class ValidationReport:
    checks: list = field(default_factory=list)
    hints: list = field(default_factory=list)
    raw_sha256: str | None = None
    canonical_sha256: str | None = None

    @property
    def ok(self) -> bool:
        return all(c.passed or not c.blocking for c in self.checks)

    def to_text(self) -> str:
        lines = []
        for c in self.checks:
            mark = "PASS" if c.passed else ("FAIL" if c.blocking else "WARN")
            lines.append(f"  [{mark}] {c.name}: {c.detail}")
        if self.raw_sha256:
            lines.append(f"  raw file SHA-256      : {self.raw_sha256}")
        if self.canonical_sha256:
            lines.append(f"  canonical SHA-256     : {self.canonical_sha256}")
        for h in self.hints:
            lines.append(f"  HINT: {h}")
        lines.append("  RESULT: " + ("dataset accepted" if self.ok else "dataset REJECTED"))
        return "\n".join(lines)


# ------------------------------------------------------------------ hashing
def sha256_file(path) -> str:
    """SHA-256 of the exact bytes of a file (changes if even one byte changes)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_sha256(df: pd.DataFrame) -> str:
    """SHA-256 of the *values* in a fixed text format.

    Two copies of the same dataset can differ in line endings (CRLF vs LF), in
    number formatting ("31" vs "31.0") or in having a header or not. The raw-file
    hash then differs although the data is identical. This hash re-writes the
    values in one canonical format first, so identical data gives an identical hash.
    """
    d = df[C.FEATURES + [C.TARGET]].copy()
    for col in INTEGER_COLUMNS:
        # keep integer columns as integers only if they really are whole numbers;
        # otherwise (e.g. 74.5 from an imputed copy) the hash must change.
        if (d[col] % 1 == 0).all():
            d[col] = d[col].astype("int64")
    text = d.to_csv(index=False, lineterminator="\n", float_format="%.3f")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------- validation
def validate_dataframe(df: pd.DataFrame, strict: bool = True) -> ValidationReport:
    """Run all checks. strict=True also requires it to match the genuine file."""
    rep = ValidationReport()
    expected_cols = C.FEATURES + [C.TARGET]

    # 1. column names and order
    cols_ok = list(df.columns) == expected_cols
    if cols_ok:
        rep.checks.append(Check("columns", True, "9 expected columns, correct order"))
    else:
        missing = [c for c in expected_cols if c not in df.columns]
        extra = [c for c in df.columns if c not in expected_cols]
        rep.checks.append(Check("columns", False, f"missing={missing} unexpected={extra}"))
        cols = set(df.columns)
        if "Id" in cols or "id" in cols:
            rep.hints.append("File has an extra Id column - drop it, then re-check the row count.")
        if {"num_preg", "glucose_conc"} & cols:
            rep.hints.append("Different schema (older course copy). Same people, other column names.")
        if {"gender", "HbA1c_level", "blood_glucose_level", "Diabetes_binary"} & cols:
            rep.hints.append("Looks like a DIFFERENT diabetes dataset, not the Pima file.")
        if missing:
            return rep  # nothing else can be checked without the right columns
        df = df[expected_cols]  # only extra columns: keep checking the rest, to explain more

    # 2. numeric types, no missing cells, labels 0/1, no negatives
    numeric = all(pd.api.types.is_numeric_dtype(df[c]) for c in expected_cols)
    rep.checks.append(Check("numeric", numeric, "all columns numeric" if numeric else "non-numeric column found"))
    if not numeric:
        return rep
    n_nan = int(df.isna().sum().sum())
    rep.checks.append(Check("no missing cells", n_nan == 0, f"{n_nan} empty cells"))
    labels = sorted(df[C.TARGET].dropna().unique().tolist())
    rep.checks.append(Check("labels are 0/1", set(labels) <= {0, 1}, f"labels found: {labels}"))
    n_neg = int((df[expected_cols] < 0).sum().sum())
    rep.checks.append(Check("no negative values", n_neg == 0, f"{n_neg} negative cells"))
    if n_nan or n_neg or not set(labels) <= {0, 1}:
        return rep

    # 3. does it look like the GENUINE file? (blocking only in strict mode)
    blocking = strict
    rows_ok = len(df) == C.EXPECTED_ROWS
    rep.checks.append(Check("row count", rows_ok, f"{len(df)} rows (expected {C.EXPECTED_ROWS})", blocking))
    if len(df) > C.EXPECTED_ROWS:
        rep.hints.append("More rows than the original 768: probably an enlarged copy whose extra rows "
                         "repeat original rows. A random split would then put copies of training "
                         "rows in the test set and inflate accuracy.")

    counts = {int(k): int(v) for k, v in df[C.TARGET].value_counts().items()}
    rep.checks.append(Check("class counts", counts == C.EXPECTED_CLASS_COUNTS,
                            f"{counts} (expected {C.EXPECTED_CLASS_COUNTS})", blocking))

    zeros = {c: int((df[c] == 0).sum()) for c in C.EXPECTED_ZERO_COUNTS}
    rep.checks.append(Check("zero counts", zeros == C.EXPECTED_ZERO_COUNTS,
                            f"{zeros} (expected {C.EXPECTED_ZERO_COUNTS})", blocking))
    if all(zeros[c] == 0 for c in C.ZERO_AS_MISSING):
        rep.hints.append("No zeros left in Glucose/BloodPressure/SkinThickness/Insulin/BMI: the missing "
                         "values were ALREADY filled in this copy. If they were filled with a value per "
                         "class (e.g. the median of diabetic patients), the label has leaked into the "
                         "features and results will look unrealistically good.")

    n_dup = int(df.duplicated().sum())
    rep.checks.append(Check("duplicate rows", n_dup == 0, f"{n_dup} duplicated rows", blocking))

    rep.canonical_sha256 = canonical_sha256(df)
    same = rep.canonical_sha256 == C.KNOWN_CANONICAL_SHA256
    rep.checks.append(Check("matches verified Pima fingerprint", same,
                            "values identical to the verified copies" if same else
                            "values differ from the verified copies", blocking))
    return rep


def load_dataset(path=C.DATA_PATH, strict: bool = True) -> pd.DataFrame:
    """Read the CSV, validate it, and return it (or raise DatasetError)."""
    path = Path(path)
    if not path.exists():
        raise DatasetError(
            f"{path} not found. Download the Pima Indians Diabetes CSV and save it there "
            f"(see data/README_DATA.md or run: python scripts/download_data.py)."
        )
    df = pd.read_csv(path)
    rep = validate_dataframe(df, strict=strict)
    rep.raw_sha256 = sha256_file(path)
    if not rep.ok:
        raise DatasetError("Dataset validation failed:\n" + rep.to_text())
    return df


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    strict = "--lenient" not in args
    args = [a for a in args if not a.startswith("--")]
    path = Path(args[0]) if args else C.DATA_PATH
    if not path.exists():
        print(f"File not found: {path}")
        return 1
    df = pd.read_csv(path)
    rep = validate_dataframe(df, strict=strict)
    rep.raw_sha256 = sha256_file(path)
    print(f"Checking {path}  (strict={strict})")
    print(rep.to_text())
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
