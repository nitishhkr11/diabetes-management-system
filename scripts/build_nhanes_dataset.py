"""
Build public screening dataset from NHANES 2017-2018 (cycle J).

Note on 2015-2016 (cycle H): CDC has restructured their data hosting and
the 2015-2016 files are no longer available at the new URL structure used
for 2017-2018. This script uses only 2017-2018 (n=9,254 participants) which
provides a substantial sample for modeling.

Blood pressure variables (cycle J): BPXSY1/BPXDI1 through BPXSY4/BPXDI4
Physical activity variables (cycle J):
  - PAQ650 (1=yes/2=no vigorous PA), PAQ655 (days/week if yes)
  - PAQ605 (1=yes/2=no moderate PA), PAQ610 (days/week if yes) 
  - PAD680 (sedentary minutes/day)

Usage: python scripts/build_nhanes_dataset.py
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def read_xpt(path: Path, cols: list[str]) -> pd.DataFrame:
    """Read XPT file, selecting available columns."""
    df = pd.read_sas(path, format="xport", encoding="utf-8")
    available = [c for c in cols if c in df.columns]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        print(f"  NOTE: Columns not in {path.name}: {missing}")
    return df[available].copy()


def load_cycle_j(nhanes_dir: Path) -> pd.DataFrame:
    """Load all NHANES 2017-2018 (J) components and merge on SEQN."""
    print("\nLoading NHANES 2017-2018 (cycle J)...")

    demo = read_xpt(nhanes_dir / "DEMO_J.XPT",
                    ["SEQN", "RIDAGEYR", "RIAGENDR", "SDMVPSU", "SDMVSTRA",
                     "WTMEC2YR", "WTINT2YR"])
    bmx  = read_xpt(nhanes_dir / "BMX_J.XPT",
                    ["SEQN", "BMXHT", "BMXWT", "BMXBMI", "BMXWAIST"])
    bpx  = read_xpt(nhanes_dir / "BPX_J.XPT",
                    ["SEQN", "BPXSY1", "BPXSY2", "BPXSY3",
                     "BPXDI1", "BPXDI2", "BPXDI3"])
    diq  = read_xpt(nhanes_dir / "DIQ_J.XPT",
                    ["SEQN", "DIQ010", "DIQ160"])
    ghb  = read_xpt(nhanes_dir / "GHB_J.XPT",
                    ["SEQN", "LBXGH"])
    paq  = read_xpt(nhanes_dir / "PAQ_J.XPT",
                    ["SEQN", "PAQ650", "PAQ655", "PAQ605", "PAQ610", "PAD680"])
    smq  = read_xpt(nhanes_dir / "SMQ_J.XPT",
                    ["SEQN", "SMQ020", "SMQ040"])

    print(f"  DEMO: {len(demo):,}  BMX: {len(bmx):,}  BPX: {len(bpx):,}")
    print(f"  DIQ:  {len(diq):,}  GHB: {len(ghb):,}  PAQ: {len(paq):,}  SMQ: {len(smq):,}")

    merged = demo
    for df in [bmx, bpx, diq, ghb, paq, smq]:
        merged = merged.merge(df, on="SEQN", how="left")

    merged["_cycle"] = "2017-2018"
    print(f"  Merged: {len(merged):,} rows, {merged.shape[1]} columns")
    return merged


def compute_bp(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mean systolic and diastolic BP from up to 3 readings.
    0 values → NaN (measurement failure).
    Require at least 2 valid readings; otherwise NaN.
    """
    for col in ["BPXSY1", "BPXSY2", "BPXSY3", "BPXDI1", "BPXDI2", "BPXDI3"]:
        if col in df.columns:
            df[col] = df[col].replace(0, np.nan)
            # Plausibility bounds
            if "SY" in col:
                df[col] = df[col].where((df[col] >= 60) & (df[col] <= 250))
            else:
                df[col] = df[col].where((df[col] >= 20) & (df[col] <= 150))

    sys_cols = [c for c in ["BPXSY1", "BPXSY2", "BPXSY3"] if c in df.columns]
    dia_cols = [c for c in ["BPXDI1", "BPXDI2", "BPXDI3"] if c in df.columns]

    if sys_cols:
        sys_df = df[sys_cols]
        n_valid = sys_df.notna().sum(axis=1)
        df["sys_bp"] = sys_df.mean(axis=1, skipna=True).where(n_valid >= 2)
    else:
        df["sys_bp"] = np.nan

    if dia_cols:
        dia_df = df[dia_cols]
        n_valid = dia_df.notna().sum(axis=1)
        df["dia_bp"] = dia_df.mean(axis=1, skipna=True).where(n_valid >= 2)
    else:
        df["dia_bp"] = np.nan

    return df


def recode_physical_activity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Vigorous PA (days/week):
      PAQ650==1 (yes) → use PAQ655 (days/week, 1-7, 99=don't know→NaN)
      PAQ650==2 (no)  → 0 days
      PAQ650 missing  → NaN

    Moderate PA (days/week):
      PAQ605==1 (yes) → use PAQ610 (days/week, 1-7, 99=don't know→NaN)
      PAQ605==2 (no)  → 0 days
      PAQ605 missing  → NaN

    Sedentary (PAD680): minutes/day; 7777/9999→NaN, clip 0-1440
    """
    # Vigorous
    vig_days = pd.Series(np.nan, index=df.index)
    if "PAQ650" in df.columns:
        # No vigorous PA → 0 days
        vig_days[df["PAQ650"] == 2] = 0.0
        # Yes → days/week from PAQ655
        if "PAQ655" in df.columns:
            days = df["PAQ655"].replace({99: np.nan, 77: np.nan})
            days = days.clip(1, 7)
            mask_yes = df["PAQ650"] == 1
            vig_days[mask_yes] = days[mask_yes]
    df["vig_days_per_week"] = vig_days

    # Moderate
    mod_days = pd.Series(np.nan, index=df.index)
    if "PAQ605" in df.columns:
        mod_days[df["PAQ605"] == 2] = 0.0
        if "PAQ610" in df.columns:
            days = df["PAQ610"].replace({99: np.nan, 77: np.nan})
            days = days.clip(1, 7)
            mask_yes = df["PAQ605"] == 1
            mod_days[mask_yes] = days[mask_yes]
    df["mod_days_per_week"] = mod_days

    # Sedentary
    if "PAD680" in df.columns:
        sed = df["PAD680"].replace({7777: np.nan, 9999: np.nan, 9999.0: np.nan})
        # Very small float values (near-zero from XPT encoding) → 0
        sed = sed.where(sed >= 0)
        df["sedentary_min_day"] = sed.clip(0, 1440)
    else:
        df["sedentary_min_day"] = np.nan

    return df


def recode_smoking(df: pd.DataFrame) -> pd.DataFrame:
    """
    smoked_100: SMQ020  1=Yes→1, 2=No→0, 7/9=refused/dk→NaN
    current_smoker: SMQ040  1=every day, 2=some days → 1 (current)
                            3=not at all → 0
                            only valid when smoked_100==1
    """
    if "SMQ020" in df.columns:
        df["smoked_100"] = df["SMQ020"].map({1: 1.0, 2: 0.0, 7: np.nan, 9: np.nan})
    else:
        df["smoked_100"] = np.nan

    if "SMQ040" in df.columns:
        # Current only meaningful if ever smoked
        cur = df["SMQ040"].map({1: 1.0, 2: 1.0, 3: 0.0, 7: np.nan, 9: np.nan})
        # For those who never smoked (smoked_100==0), current_smoker = 0
        df["current_smoker"] = cur
        if "smoked_100" in df.columns:
            df.loc[df["smoked_100"] == 0, "current_smoker"] = 0.0
    else:
        df["current_smoker"] = np.nan

    return df


def build_target(df: pd.DataFrame) -> pd.DataFrame:
    """
    Survey-defined diabetes phenotype.

    POSITIVE: DIQ010==1 (diagnosed, non-gestational-only) OR LBXGH>=6.5
    NEGATIVE: DIQ010==2 (no) AND LBXGH<6.5
    EXCLUDED: borderline (3), refused (7), don't know (9), missing, gestational-only

    LBXGH and DIQ010 are NEVER exposed as model features.
    """
    diq = df.get("DIQ010", pd.Series(np.nan, index=df.index)).replace({7: np.nan, 9: np.nan})
    ghb = df.get("LBXGH", pd.Series(np.nan, index=df.index))

    # Gestational exclusion: DIQ010==1 AND DIQ160==1
    gestational = pd.Series(False, index=df.index)
    if "DIQ160" in df.columns:
        gestational = (diq == 1) & (df["DIQ160"] == 1)

    diagnosed     = (diq == 1) & ~gestational
    hba1c_pos     = ghb >= 6.5
    not_diagnosed = (diq == 2)
    hba1c_neg     = ghb < 6.5

    positive = diagnosed | hba1c_pos
    negative = not_diagnosed & hba1c_neg

    df["outcome"] = np.nan
    df.loc[positive, "outcome"] = 1.0
    df.loc[negative & ~positive, "outcome"] = 0.0

    df["_target_note"] = "included"
    df.loc[gestational, "_target_note"] = "gestational_excluded"
    df.loc[diq == 3, "_target_note"] = "borderline_excluded"
    df.loc[(diq.isna()) & (ghb.isna()), "_target_note"] = "both_missing_excluded"

    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create final feature columns."""
    df["age_years"] = df["RIDAGEYR"]
    df["sex_male"]  = df["RIAGENDR"].map({1: 1.0, 2: 0.0})
    df["height_cm"] = df.get("BMXHT",    pd.Series(np.nan, index=df.index))
    df["weight_kg"] = df.get("BMXWT",    pd.Series(np.nan, index=df.index))
    df["waist_cm"]  = df.get("BMXWAIST", pd.Series(np.nan, index=df.index))

    bmi_direct   = df.get("BMXBMI", pd.Series(np.nan, index=df.index))
    bmi_computed = df["weight_kg"] / ((df["height_cm"] / 100) ** 2)
    df["bmi"] = bmi_direct.fillna(bmi_computed)
    # Plausibility
    df["bmi"] = df["bmi"].where((df["bmi"] >= 10) & (df["bmi"] <= 80))

    return df


FINAL_COLS = [
    "SEQN", "_cycle",
    "SDMVPSU", "SDMVSTRA", "WTMEC2YR", "WTINT2YR",
    # Features
    "age_years", "sex_male",
    "height_cm", "weight_kg", "bmi", "waist_cm",
    "sys_bp", "dia_bp",
    "mod_days_per_week", "vig_days_per_week", "sedentary_min_day",
    "smoked_100", "current_smoker",
    # Target
    "outcome", "_target_note",
    # Reference only (never model features)
    "DIQ010", "LBXGH",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nhanes", default=str(ROOT / "data" / "nhanes"))
    parser.add_argument("--out", default=str(ROOT / "data" / "nhanes_processed.csv"))
    parser.add_argument("--audit", default=str(ROOT / "reports" / "public_screening" / "dataset_audit_raw.json"))
    args = parser.parse_args()

    nhanes_dir = Path(args.nhanes)
    out_path = Path(args.out)
    audit_path = Path(args.audit)
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    df = load_cycle_j(nhanes_dir)

    # Process
    df = compute_bp(df)
    df = recode_physical_activity(df)
    df = recode_smoking(df)
    df = build_target(df)
    df = build_features(df)

    # Filter: adults 21+
    df = df[df["age_years"] >= 21].copy()
    n_adults = len(df)
    print(f"\nAfter age>=21: {n_adults:,}")

    # Target distribution
    print(f"Outcome distribution:")
    print(f"  Positive (1): {(df['outcome'] == 1).sum():,}")
    print(f"  Negative (0): {(df['outcome'] == 0).sum():,}")
    print(f"  Missing:      {df['outcome'].isna().sum():,}")
    print(f"  Notes: {df['_target_note'].value_counts().to_dict()}")

    # Keep eligible
    eligible = df[df["outcome"].notna()].copy()
    n_eligible = len(eligible)
    print(f"\nEligible (defined outcome): {n_eligible:,}")
    print(f"  Positive: {(eligible['outcome'] == 1).sum():,}  ({eligible['outcome'].mean()*100:.1f}%)")
    print(f"  Negative: {(eligible['outcome'] == 0).sum():,}")

    # Missingness of features in eligible set
    print(f"\nMissingness (% of eligible rows):")
    feature_cols = ["age_years", "sex_male", "bmi", "waist_cm", "sys_bp", "dia_bp",
                    "mod_days_per_week", "vig_days_per_week", "sedentary_min_day",
                    "smoked_100", "current_smoker"]
    for col in feature_cols:
        if col in eligible.columns:
            pct = eligible[col].isna().mean() * 100
            print(f"  {col:30s}: {pct:.1f}%")

    # Select columns
    keep_cols = [c for c in FINAL_COLS if c in eligible.columns]
    out_df = eligible[keep_cols].copy()

    # Fingerprint
    sha = hashlib.sha256(out_df.to_csv(index=False).encode()).hexdigest()

    # Save
    out_df.to_csv(out_path, index=False)
    print(f"\nSaved: {out_path}  ({len(out_df):,} rows)")
    print(f"Fingerprint: {sha}")

    # Audit
    audit = {
        "dataset_source": "NHANES — National Health and Nutrition Examination Survey",
        "official_url": "https://wwwn.cdc.gov/Nchs/Nhanes/",
        "cycles_used": ["2017-2018 (cycle J)"],
        "cycles_note": (
            "2015-2016 (cycle H) is not available at the new CDC data hosting URL structure. "
            "Only 2017-2018 is used. The 2021-2023 cycle is excluded due to documented "
            "15-month survey gap, updated sampling design, and pandemic-era protocol changes."
        ),
        "access_conditions": "Public domain — US Government CDC data, no registration required",
        "license": "Public domain",
        "download_date": datetime.datetime.utcnow().isoformat() + "Z",
        "target_definition": {
            "positive": "DIQ010==1 (diagnosed, non-gestational) OR LBXGH>=6.5 (HbA1c>=6.5%)",
            "negative": "DIQ010==2 (no) AND LBXGH<6.5",
            "excluded": "Borderline (DIQ010==3), refused/don't know, gestational-only, both missing",
            "note": "Survey-defined phenotype combining self-report and single HbA1c. NOT a clinical diagnosis.",
            "leakage": "LBXGH and DIQ010 used ONLY for target. NEVER exposed as model features.",
        },
        "population": "US non-institutionalized civilian adults aged 21+, 2017-2018 survey",
        "age_topcoding_note": "RIDAGEYR is top-coded at 80; all participants 80+ appear as age=80",
        "counts": {
            "raw_total": 9254,
            "adults_21plus": int(n_adults),
            "eligible_defined_outcome": int(n_eligible),
            "positive": int((eligible["outcome"] == 1).sum()),
            "negative": int((eligible["outcome"] == 0).sum()),
            "prevalence_pct": float((eligible["outcome"].mean()) * 100),
            "age_80_topcoded": int((eligible["age_years"] == 80).sum()),
        },
        "missingness_pct": {
            col: float(eligible[col].isna().mean() * 100) if col in eligible.columns else None
            for col in feature_cols
        },
        "features": feature_cols,
        "output_fingerprint_sha256": sha,
        "output_file": str(out_path),
        "limitations": [
            "Single NHANES cycle (2017-2018); not pooled across cycles",
            "2015-2016 data unavailable at new CDC URL structure",
            "Survey target: not independently clinically validated",
            "Physical activity self-report may be unreliable",
            "Sedentary time has significant missingness in PA module",
            "Age top-coded at 80 — 80+ participants not distinguishable",
            "Survey weights not applied during model training",
            "NHANES examines a cross-sectional sample; temporal causation cannot be inferred",
        ],
    }
    audit_path.write_text(json.dumps(audit, indent=2))
    print(f"Audit saved: {audit_path}")


if __name__ == "__main__":
    main()
