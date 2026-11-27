"""
Reproducible ICMR-INDIAB dataset audit & target-construction pipeline.

Verifies:
- Manifest permission status and input file existence
- Codebook schema and required survey design columns (PSU, stratum, weight)
- Age >= 20 eligibility (flags < 20)
- Sex, state/region, and rural/urban coverage
- Missingness per feature, duplicate participant IDs, invalid measurements
- WHO diagnostic target availability & class balance (without leakage)

Stops training and reports exact blockers when required data, labels,
permissions, or sampling columns are missing.

Outputs:
- data/reports/indiab_audit.json
- data/reports/indiab_audit.md
- data/reports/indiab_audit.html
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import india_config as IC  # noqa: E402


def load_manifest(manifest_path: Path = IC.INDIA_MANIFEST_PATH) -> dict[str, Any]:
    if not manifest_path.exists():
        return {"permission_status": "NOT REQUESTED", "files": []}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def derive_who_diabetes_target(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, dict[str, Any]]:
    """
    Construct the documented ICMR-INDIAB WHO diabetes outcome:
      Positive (1): fasting_glucose >= 126 mg/dL OR post_load_glucose_2h >= 200 mg/dL
                    OR self_reported_diabetes == 1 (known diabetes on/per protocol)
      Negative (0): not positive AND at least one valid diagnostic criterion confirming normoglycaemia/prediabetes
                    (fasting_glucose < 126 and post_load_glucose_2h < 200 when available, self_reported_diabetes != 1)
      Excluded (NaN): missing all diagnostic inputs.

    Returns (target_series, known_vs_new_series, summary_dict).
    """
    if "diabetes_label" in df.columns and df["diabetes_label"].notna().any():
        target = pd.to_numeric(df["diabetes_label"], errors="coerce")
        known = (
            df["self_reported_diabetes"]
            if "self_reported_diabetes" in df.columns
            else pd.Series(np.nan, index=df.index)
        )
        summary = {
            "source": "precomputed_diabetes_label",
            "positive": int((target == 1).sum()),
            "negative": int((target == 0).sum()),
            "missing": int(target.isna().sum()),
        }
        return target, known, summary

    fbg = pd.to_numeric(df["fasting_glucose"], errors="coerce") if "fasting_glucose" in df.columns else pd.Series(np.nan, index=df.index)
    ogtt = pd.to_numeric(df["post_load_glucose_2h"], errors="coerce") if "post_load_glucose_2h" in df.columns else pd.Series(np.nan, index=df.index)
    self_rep = pd.to_numeric(df["self_reported_diabetes"], errors="coerce") if "self_reported_diabetes" in df.columns else pd.Series(np.nan, index=df.index)

    has_any_diag = fbg.notna() | ogtt.notna() | self_rep.notna()
    is_known = self_rep == 1
    is_newly_detected = (~is_known) & ((fbg >= 126.0) | (ogtt >= 200.0))
    is_positive = is_known | is_newly_detected

    target = pd.Series(np.nan, index=df.index, dtype=float)
    target.loc[has_any_diag & (~is_positive)] = 0.0
    target.loc[has_any_diag & is_positive] = 1.0

    subtype = pd.Series("non_diabetes", index=df.index, dtype=object)
    subtype.loc[~has_any_diag] = "missing"
    subtype.loc[is_known] = "known_diabetes"
    subtype.loc[is_newly_detected] = "newly_detected_diabetes"

    summary = {
        "source": "who_criteria_fbg_126_ogtt_200_or_known",
        "positive": int((target == 1).sum()),
        "negative": int((target == 0).sum()),
        "missing": int(target.isna().sum()),
        "known_diabetes": int(is_known.sum()),
        "newly_detected_diabetes": int(is_newly_detected.sum()),
    }
    return target, subtype, summary


def audit_dataframe(
    df: pd.DataFrame,
    manifest: dict[str, Any],
    *,
    require_permission: bool = True,
) -> dict[str, Any]:
    """Run all schema, eligibility, missingness, leakage, and design checks on a DataFrame."""
    blockers: list[str] = []
    warnings: list[str] = []

    perm = manifest.get("permission_status", "NOT REQUESTED")
    if require_permission and perm not in ("DATA RECEIVED", "DATA VERIFIED", "MODEL TRAINED"):
        blockers.append(
            f"Permission/acquisition status is '{perm}'. Must be 'DATA RECEIVED' or 'DATA VERIFIED' before training."
        )

    # 1. Required survey design & demographic columns
    required_cols = ["participant_id", "psu_id", "stratum_id", "survey_weight", "age_years", "sex"]
    missing_required = [c for c in required_cols if c not in df.columns]
    if missing_required:
        blockers.append(f"Missing required survey/demographic columns: {missing_required}")

    # 2. Target availability
    target, _, target_summary = derive_who_diabetes_target(df)
    if target_summary["positive"] == 0 or target_summary["negative"] == 0:
        blockers.append(
            f"Insufficient outcome classes for modelling: positive={target_summary['positive']}, negative={target_summary['negative']}."
        )

    # 3. Age >= 20 coverage
    age_stats: dict[str, Any] = {}
    if "age_years" in df.columns:
        ages = pd.to_numeric(df["age_years"], errors="coerce")
        under_20 = int((ages < IC.INDIA_MIN_AGE).sum())
        if under_20 > 0:
            warnings.append(
                f"{under_20} records have age_years < {IC.INDIA_MIN_AGE}; these must be excluded (model restricted to 20+)."
            )
        age_stats = {
            "min": float(ages.min()) if ages.notna().any() else None,
            "max": float(ages.max()) if ages.notna().any() else None,
            "under_20_count": under_20,
            "eligible_20plus_count": int((ages >= IC.INDIA_MIN_AGE).sum()),
            "missing_count": int(ages.isna().sum()),
        }

    # 4. Duplicates
    dup_ids = 0
    if "participant_id" in df.columns:
        dup_ids = int(df["participant_id"].duplicated().sum())
        if dup_ids > 0:
            warnings.append(f"{dup_ids} duplicate participant_id rows detected.")

    # 5. Sex, rural/urban, state representation
    sex_dist = df["sex"].value_counts(dropna=False).to_dict() if "sex" in df.columns else {}
    residence_dist = df["residence_type"].value_counts(dropna=False).to_dict() if "residence_type" in df.columns else {}
    state_count = int(df["state_region"].nunique(dropna=True)) if "state_region" in df.columns else 0
    if state_count == 0:
        warnings.append("state_region column missing or empty — state/regional subgroup evaluation unavailable.")
    if not residence_dist:
        warnings.append("residence_type column missing — rural/urban subgroup evaluation unavailable.")

    # 6. Survey design validity
    design_checks: dict[str, Any] = {}
    for col in ("psu_id", "stratum_id", "survey_weight"):
        if col in df.columns:
            nulls = int(df[col].isna().sum())
            design_checks[col] = {
                "present": True,
                "missing": nulls,
                "n_unique": int(df[col].nunique(dropna=True)),
            }
            if nulls > 0:
                warnings.append(f"Survey design column '{col}' has {nulls} missing values.")
        else:
            design_checks[col] = {"present": False}

    if "survey_weight" in df.columns:
        w = pd.to_numeric(df["survey_weight"], errors="coerce")
        non_pos = int((w <= 0).sum())
        if non_pos > 0:
            warnings.append(f"survey_weight has {non_pos} non-positive values.")

    # 7. Candidate predictor availability & missingness + invalid range checks
    feature_report: dict[str, Any] = {}
    available_predictors: list[str] = []
    for feat in IC.INDIA_ALL_CANDIDATE_FEATURES:
        if feat in df.columns:
            s = df[feat]
            miss_pct = round(float(s.isna().mean() * 100.0), 2)
            invalid_count = 0
            if feat in IC.INDIA_INPUT_LIMITS:
                lo, hi = IC.INDIA_INPUT_LIMITS[feat]
                num = pd.to_numeric(s, errors="coerce")
                invalid_count = int(((num < lo) | (num > hi)).sum())
            feature_report[feat] = {
                "present": True,
                "missing_pct": miss_pct,
                "invalid_out_of_range": invalid_count,
            }
            available_predictors.append(feat)
        else:
            feature_report[feat] = {"present": False, "missing_pct": 100.0, "invalid_out_of_range": 0}

    if not available_predictors:
        blockers.append("No candidate non-laboratory predictors found in dataset.")

    # 8. Leakage check: ensure no forbidden variable is listed as an approved predictor
    leakage_overlap = sorted(set(available_predictors) & IC.FORBIDDEN_LEAKAGE_VARIABLES)
    if leakage_overlap:
        blockers.append(f"Target leakage detected in candidate features: {leakage_overlap}")

    passed = len(blockers) == 0
    return {
        "audited_at": datetime.datetime.utcnow().isoformat() + "Z",
        "dataset_name": manifest.get("dataset_name", "ICMR-INDIAB"),
        "permission_status": perm,
        "audit_passed": passed,
        "ready_for_training": passed,
        "row_count": int(len(df)),
        "duplicate_participant_ids": dup_ids,
        "blockers": blockers,
        "warnings": warnings,
        "age_coverage": age_stats,
        "sex_distribution": {str(k): int(v) for k, v in sex_dist.items()},
        "residence_distribution": {str(k): int(v) for k, v in residence_dist.items()},
        "state_region_count": state_count,
        "target_summary": target_summary,
        "survey_design": design_checks,
        "available_predictors": available_predictors,
        "feature_availability": feature_report,
    }


def run_audit(
    data_path: Path | None = None,
    manifest_path: Path = IC.INDIA_MANIFEST_PATH,
    out_dir: Path = IC.INDIA_AUDIT_DIR,
) -> dict[str, Any]:
    """Locate authorised ICMR-INDIAB files, audit them if present, and write reports."""
    manifest = load_manifest(manifest_path)
    perm = manifest.get("permission_status", "NOT REQUESTED")

    if data_path is None:
        candidates = sorted(list(IC.INDIA_RAW_DIR.glob("*.csv")) + list(IC.INDIA_RAW_DIR.glob("*.parquet")))
        data_path = candidates[0] if candidates else None

    if data_path is None or not data_path.exists():
        report = {
            "audited_at": datetime.datetime.utcnow().isoformat() + "Z",
            "dataset_name": manifest.get("dataset_name", "ICMR-INDIAB National Diabetes Study"),
            "permission_status": perm,
            "audit_passed": False,
            "ready_for_training": False,
            "row_count": 0,
            "blockers": [
                f"Authorised ICMR-INDIAB data file not found in {IC.INDIA_RAW_DIR}.",
                f"Current permission status is '{perm}'.",
                "Missing required variables: participant_id, psu_id, stratum_id, survey_weight, age_years, sex, and WHO diagnostic target inputs.",
            ],
            "warnings": [],
            "available_predictors": [],
        }
    else:
        df = pd.read_parquet(data_path) if data_path.suffix.lower() == ".parquet" else pd.read_csv(data_path)
        report = audit_dataframe(df, manifest, require_permission=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "indiab_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    md_lines = [
        "# ICMR-INDIAB Dataset Audit Report",
        "",
        f"- **Audited at:** {report['audited_at']}",
        f"- **Permission status:** `{report['permission_status']}`",
        f"- **Audit passed:** `{report['audit_passed']}`",
        f"- **Ready for training:** `{report['ready_for_training']}`",
        f"- **Rows:** {report['row_count']}",
        "",
        "## Blockers",
    ]
    if report["blockers"]:
        md_lines.extend(f"- {b}" for b in report["blockers"])
    else:
        md_lines.append("- None")
    if report.get("warnings"):
        md_lines.extend(["", "## Warnings"] + [f"- {w}" for w in report["warnings"]])
    md_text = "\n".join(md_lines) + "\n"
    (out_dir / "indiab_audit.md").write_text(md_text, encoding="utf-8")

    html_doc = (
        "<!doctype html><html><head><meta charset='utf-8'><title>ICMR-INDIAB Audit</title></head><body>"
        f"<h1>ICMR-INDIAB Dataset Audit Report</h1>"
        f"<p><strong>Status:</strong> {html.escape(str(report['permission_status']))} | "
        f"<strong>Ready for training:</strong> {report['ready_for_training']}</p>"
        "<h2>Blockers</h2><ul>"
        + "".join(f"<li>{html.escape(b)}</li>" for b in (report["blockers"] or ["None"]))
        + "</ul></body></html>"
    )
    (out_dir / "indiab_audit.html").write_text(html_doc, encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ICMR-INDIAB dataset readiness.")
    parser.add_argument("--data", type=Path, default=None, help="Optional path to authorised CSV/Parquet.")
    args = parser.parse_args()
    report = run_audit(data_path=args.data)
    print(json.dumps({"audit_passed": report["audit_passed"], "permission_status": report["permission_status"], "blockers": report["blockers"]}, indent=2))
    return 0 if report["audit_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
