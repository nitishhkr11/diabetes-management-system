"""
Madras Diabetes Research Foundation Indian Diabetes Risk Score (MDRF-IDRS).

Implements the published MDRF-IDRS scoring rules evaluated in the ICMR-INDIAB study:
https://ijmr.org.in/evaluation-of-madras-diabetes-risk-score-in-detecting-undiagnosed-diabetes-in-the-indian-population-results-from-the-indian-council-of-medical-research-india-diabetes-population-based-study/

This is a non-laboratory risk-screening score for adults aged 20+, NOT a clinical diagnosis
and NOT a personalised probability. GlucoGuide does not possess ICMR-INDIAB raw data.
"""
from __future__ import annotations

from typing import Literal

MDRF_SOURCE_URL = (
    "https://ijmr.org.in/evaluation-of-madras-diabetes-risk-score-in-detecting-"
    "undiagnosed-diabetes-in-the-indian-population-results-from-the-indian-council-"
    "of-medical-research-india-diabetes-population-based-study/"
)
MDRF_GUIDELINE_VERSION = "MDRF-IDRS (ICMR-INDIAB IJMR)"

ACTIVITY_POINTS: dict[str, int] = {
    "vigorous": 0,    # Regular vigorous exercise or strenuous manual work
    "moderate": 10,   # Regular moderate exercise or moderate physical activity
    "mild": 20,       # Regular mild exercise or mild physical activity
    "sedentary": 30,  # No exercise and sedentary activities
}

FAMILY_HISTORY_POINTS: dict[str, int] = {
    "none": 0,        # Neither parent has diabetes
    "one_parent": 10, # One parent has diabetes
    "both_parents": 20,  # Both parents have diabetes
}


def compute_mdrf_idrs(
    *,
    age_years: float,
    sex: Literal["female", "male"],
    waist_value: float,
    waist_unit: Literal["cm", "in"] = "cm",
    physical_activity: Literal["vigorous", "moderate", "mild", "sedentary"],
    family_history: Literal["none", "one_parent", "both_parents"],
) -> dict:
    """Compute the MDRF-IDRS score (0-100) and risk category with strict validation."""
    if age_years < 20 or age_years > 120:
        raise ValueError(
            "MDRF-IDRS validation in ICMR-INDIAB covers adults aged 20 years and above "
            "(supported input range: 20-120 years)."
        )

    sex_norm = sex.strip().lower()
    if sex_norm not in ("female", "male"):
        raise ValueError("Sex must be 'female' or 'male' for waist threshold scoring.")

    unit_norm = waist_unit.strip().lower()
    if unit_norm not in ("cm", "in"):
        raise ValueError("Waist unit must be 'cm' or 'in'.")

    waist_cm = float(waist_value) * 2.54 if unit_norm == "in" else float(waist_value)
    if waist_cm < 40.0 or waist_cm > 200.0:
        raise ValueError("Waist circumference must be between 40 cm and 200 cm (15.7-78.7 in).")

    act_norm = physical_activity.strip().lower()
    if act_norm not in ACTIVITY_POINTS:
        raise ValueError("Invalid physical_activity; choose vigorous, moderate, mild, or sedentary.")

    fam_norm = family_history.strip().lower()
    if fam_norm not in FAMILY_HISTORY_POINTS:
        raise ValueError("Invalid family_history; choose none, one_parent, or both_parents.")

    # 1. Age points
    if age_years < 35:
        age_pts = 0
    elif age_years < 50:
        age_pts = 20
    else:
        age_pts = 30

    # 2. Waist circumference points (sex-specific cm cutoffs)
    if sex_norm == "female":
        if waist_cm < 80.0:
            waist_pts = 0
        elif waist_cm < 90.0:
            waist_pts = 10
        else:
            waist_pts = 20
    else:
        if waist_cm < 90.0:
            waist_pts = 0
        elif waist_cm < 100.0:
            waist_pts = 10
        else:
            waist_pts = 20

    # 3. Physical activity & 4. Family history points
    activity_pts = ACTIVITY_POINTS[act_norm]
    family_pts = FAMILY_HISTORY_POINTS[fam_norm]

    total_score = age_pts + waist_pts + activity_pts + family_pts

    # Risk categories: <30 Low, 30-50 Moderate, >=60 High
    if total_score < 30:
        risk_category = "low"
        risk_label = "Low risk"
        next_steps = (
            "Your MDRF-IDRS score is in the low-risk screening band (< 30). Maintain regular physical "
            "activity, a balanced diet, and routine preventive health check-ups as advised by a clinician."
        )
    elif total_score <= 50:
        risk_category = "moderate"
        risk_label = "Moderate risk"
        next_steps = (
            "Your MDRF-IDRS score is in the moderate-risk screening band (30-50). Consider discussing "
            "routine blood glucose screening (fasting plasma glucose or HbA1c) with a healthcare professional."
        )
    else:
        risk_category = "high"
        risk_label = "High risk"
        next_steps = (
            "Your MDRF-IDRS score is in the high-risk screening band (60 or above). Please consult a "
            "qualified healthcare professional for laboratory blood glucose testing (such as fasting plasma "
            "glucose, 2-hour OGTT, or HbA1c). This score is not a diagnosis."
        )

    return {
        "ok": True,
        "tool": "mdrf_idrs",
        "guideline_version": MDRF_GUIDELINE_VERSION,
        "source_url": MDRF_SOURCE_URL,
        "score": total_score,
        "max_score": 100,
        "risk_category": risk_category,
        "risk_label": risk_label,
        "breakdown": {
            "age_points": age_pts,
            "waist_points": waist_pts,
            "activity_points": activity_pts,
            "family_history_points": family_pts,
        },
        "normalized_inputs": {
            "age_years": float(age_years),
            "sex": sex_norm,
            "waist_cm": round(waist_cm, 2),
            "waist_unit_submitted": unit_norm,
            "physical_activity": act_norm,
            "family_history": fam_norm,
        },
        "next_steps": next_steps,
        "disclaimer": (
            "MDRF-IDRS is a population-validated risk-screening score, NOT a diabetes diagnosis and "
            "NOT a personalised clinical probability. Validated in Indian adults aged 20 and above; "
            "not validated for individuals under 20. GlucoGuide does not hold ICMR-INDIAB raw participant data."
        ),
    }
