"""
Clinical Laboratory Blood Test Result Interpretation (ADA & ICMR/WHO criteria).

Supports:
- HbA1c (%)
- Fasting plasma glucose (mg/dL or mmol/L)
- 2-hour oral glucose tolerance test (OGTT, mg/dL or mmol/L)
- Random plasma glucose (mg/dL or mmol/L) with classic symptom check
- Pregnancy pathway check (gestational diabetes uses separate clinical thresholds)

Educational & guidance tool only — never replaces qualified clinical evaluation.
"""
from __future__ import annotations

from typing import Any, Literal

MMOL_TO_MGDL = 18.0182
LAB_GUIDELINE_VERSION = "ADA Standards of Care / ICMR-WHO Reference"


def _to_mg_dl(value: float, unit: Literal["mg/dL", "mmol/L"]) -> float:
    if unit == "mg/dL":
        return float(value)
    if unit == "mmol/L":
        return float(value) * MMOL_TO_MGDL
    raise ValueError("Glucose unit must be 'mg/dL' or 'mmol/L'.")


def interpret_lab_results(
    *,
    is_pregnant: bool = False,
    hba1c_pct: float | None = None,
    fasting_glucose: float | None = None,
    fasting_unit: Literal["mg/dL", "mmol/L"] = "mg/dL",
    ogtt_2h_glucose: float | None = None,
    ogtt_unit: Literal["mg/dL", "mmol/L"] = "mg/dL",
    random_glucose: float | None = None,
    random_unit: Literal["mg/dL", "mmol/L"] = "mg/dL",
    has_classic_symptoms: bool = False,
) -> dict[str, Any]:
    """Interpret laboratory blood test results with clinical safety guards."""
    if is_pregnant:
        return {
            "ok": True,
            "tool": "lab_interpretation",
            "guideline_version": LAB_GUIDELINE_VERSION,
            "pregnancy_pathway": True,
            "overall_category": "pregnancy_specialist_pathway",
            "overall_label": "Separate Pregnancy / Gestational Diabetes Pathway Required",
            "results": [],
            "confirmation_required": True,
            "guidance": (
                "Gestational diabetes mellitus (GDM) uses pregnancy-specific diagnostic thresholds "
                "(such as DIPSI / IADPSG / WHO pregnancy OGTT criteria) that differ from non-pregnant "
                "adult cutoffs. Please consult your obstetrician or qualified healthcare provider "
                "for pregnancy-appropriate screening and interpretation."
            ),
            "guideline_notes": [
                "Standard adult HbA1c, fasting glucose, and 2-hour OGTT cutoffs are not applied during pregnancy.",
            ],
            "disclaimer": (
                "Educational interpretation only — not a medical diagnosis. A single home glucometer "
                "reading does not establish a clinical diagnosis."
            ),
        }

    if all(v is None for v in (hba1c_pct, fasting_glucose, ogtt_2h_glucose, random_glucose)):
        raise ValueError("Provide at least one laboratory test value (HbA1c, fasting glucose, 2h OGTT, or random glucose).")

    findings: list[dict[str, Any]] = []
    categories_seen: list[str] = []

    if hba1c_pct is not None:
        val = float(hba1c_pct)
        if val < 3.0 or val > 20.0:
            raise ValueError("HbA1c must be between 3.0% and 20.0%.")
        if val < 5.7:
            cat, lbl = "normal", "Normal range (< 5.7%)"
        elif val < 6.5:
            cat, lbl = "prediabetes", "Prediabetes range (5.7%–6.4%)"
        else:
            cat, lbl = "diabetes", "Diabetes range (≥ 6.5%)"
        categories_seen.append(cat)
        findings.append({"test": "HbA1c", "value_display": f"{val:.1f}%", "category": cat, "label": lbl})

    if fasting_glucose is not None:
        mg = _to_mg_dl(float(fasting_glucose), fasting_unit)
        if mg < 30.0 or mg > 600.0:
            raise ValueError("Fasting plasma glucose must be between 30 and 600 mg/dL (1.7–33.3 mmol/L).")
        if mg < 100.0:
            cat, lbl = "normal", "Normal range (< 100 mg/dL, ADA)"
        elif mg < 126.0:
            cat, lbl = "prediabetes", "Prediabetes range (100–125 mg/dL, ADA)"
        else:
            cat, lbl = "diabetes", "Diabetes range (≥ 126 mg/dL)"
        categories_seen.append(cat)
        findings.append({
            "test": "Fasting plasma glucose",
            "value_display": f"{mg:.1f} mg/dL",
            "category": cat,
            "label": lbl,
        })

    if ogtt_2h_glucose is not None:
        mg = _to_mg_dl(float(ogtt_2h_glucose), ogtt_unit)
        if mg < 30.0 or mg > 800.0:
            raise ValueError("2-hour OGTT glucose must be between 30 and 800 mg/dL (1.7–44.4 mmol/L).")
        if mg < 140.0:
            cat, lbl = "normal", "Normal range (< 140 mg/dL)"
        elif mg < 200.0:
            cat, lbl = "prediabetes", "Prediabetes / Impaired Glucose Tolerance range (140–199 mg/dL)"
        else:
            cat, lbl = "diabetes", "Diabetes range (≥ 200 mg/dL)"
        categories_seen.append(cat)
        findings.append({
            "test": "2-hour OGTT",
            "value_display": f"{mg:.1f} mg/dL",
            "category": cat,
            "label": lbl,
        })

    unequivocal_hyperglycemia = False
    if random_glucose is not None:
        mg = _to_mg_dl(float(random_glucose), random_unit)
        if mg < 30.0 or mg > 800.0:
            raise ValueError("Random plasma glucose must be between 30 and 800 mg/dL (1.7–44.4 mmol/L).")
        if mg >= 200.0 and has_classic_symptoms:
            cat = "diabetes"
            lbl = "Diabetes range (≥ 200 mg/dL with classic hyperglycaemia symptoms)"
            unequivocal_hyperglycemia = True
        elif mg >= 200.0:
            cat = "indeterminate_requires_confirmation"
            lbl = "Elevated random glucose (≥ 200 mg/dL without classic symptoms — not diagnostic alone)"
        else:
            cat = "non_diagnostic"
            lbl = "Below 200 mg/dL (a random reading < 200 mg/dL does not rule out diabetes or prediabetes)"
        categories_seen.append(cat)
        findings.append({
            "test": "Random plasma glucose",
            "value_display": f"{mg:.1f} mg/dL",
            "category": cat,
            "label": lbl,
        })

    if "diabetes" in categories_seen:
        overall_category = "diabetes_range"
        overall_label = "Result in Diabetes Range — Clinical Confirmation Required"
        confirmation_required = not unequivocal_hyperglycemia
        guidance = (
            "One or more laboratory values fall in the diabetes range. Unless there is unequivocal "
            "hyperglycaemia (classic symptoms with random plasma glucose ≥ 200 mg/dL), clinical "
            "confirmation with repeat or additional laboratory testing is generally required. Please "
            "consult a qualified healthcare professional."
        )
    elif "indeterminate_requires_confirmation" in categories_seen:
        overall_category = "indeterminate_requires_confirmation"
        overall_label = "Elevated Random Glucose — Confirmatory Lab Testing Needed"
        confirmation_required = True
        guidance = (
            "Random plasma glucose ≥ 200 mg/dL in an asymptomatic person does NOT establish a diabetes "
            "diagnosis on its own. Please consult a healthcare professional for fasting plasma glucose, "
            "2-hour OGTT, or HbA1c testing."
        )
    elif "prediabetes" in categories_seen:
        overall_category = "prediabetes_range"
        overall_label = "Result in Prediabetes Range"
        confirmation_required = False
        guidance = (
            "One or more values fall in the prediabetes range. Discuss lifestyle interventions, "
            "follow-up monitoring, and confirmatory testing with a qualified healthcare professional."
        )
    elif "normal" in categories_seen:
        overall_category = "normal_range"
        overall_label = "Result in Normal Reference Range"
        confirmation_required = False
        guidance = (
            "Entered laboratory values are within the normal reference range. Continue periodic "
            "check-ups as recommended by your healthcare provider."
        )
    else:
        overall_category = "non_diagnostic"
        overall_label = "Non-Diagnostic Random Glucose Reading"
        confirmation_required = False
        guidance = (
            "A random glucose below 200 mg/dL does not rule out prediabetes or diabetes. For formal "
            "evaluation, consult a healthcare professional for fasting plasma glucose, OGTT, or HbA1c."
        )

    return {
        "ok": True,
        "tool": "lab_interpretation",
        "guideline_version": LAB_GUIDELINE_VERSION,
        "pregnancy_pathway": False,
        "overall_category": overall_category,
        "overall_label": overall_label,
        "confirmation_required": confirmation_required,
        "results": findings,
        "guidance": guidance,
        "guideline_notes": [
            "ADA defines Impaired Fasting Glucose (prediabetes) as 100–125 mg/dL, whereas WHO/ICMR-INDIAB criteria often use 110–125 mg/dL.",
            "HbA1c ≥ 6.5%, Fasting Plasma Glucose ≥ 126 mg/dL, or 2-hour OGTT ≥ 200 mg/dL require confirmatory testing in asymptomatic individuals.",
            "A single home glucometer (capillary) reading does not establish a clinical diagnosis.",
        ],
        "disclaimer": (
            "This laboratory interpretation is for educational guidance only and is NOT a medical "
            "diagnosis. Always consult a qualified healthcare professional."
        ),
    }
