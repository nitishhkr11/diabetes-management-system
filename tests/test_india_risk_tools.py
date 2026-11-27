"""
Comprehensive tests for MDRF-IDRS, Laboratory Result Interpretation,
FastAPI endpoints, authentication/consent/RLS safeguards, and input validation.
"""
from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.lab_interpretation import interpret_lab_results
from src.mdrf_idrs import compute_mdrf_idrs

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# 1. MDRF-IDRS unit & boundary tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("age,expected_pts", [(20, 0), (34, 0), (35, 20), (49, 20), (50, 30), (75, 30)])
def test_idrs_age_boundaries(age, expected_pts):
    res = compute_mdrf_idrs(
        age_years=age, sex="male", waist_value=80, physical_activity="vigorous", family_history="none"
    )
    assert res["breakdown"]["age_points"] == expected_pts


def test_idrs_rejects_under_20():
    with pytest.raises(ValueError, match="20"):
        compute_mdrf_idrs(
            age_years=19, sex="female", waist_value=75, physical_activity="vigorous", family_history="none"
        )


@pytest.mark.parametrize("sex,waist,expected_pts", [
    ("female", 79.9, 0),
    ("female", 80.0, 10),
    ("female", 89.9, 10),
    ("female", 90.0, 20),
    ("male", 89.9, 0),
    ("male", 90.0, 10),
    ("male", 99.9, 10),
    ("male", 100.0, 20),
])
def test_idrs_sex_specific_waist_thresholds(sex, waist, expected_pts):
    res = compute_mdrf_idrs(
        age_years=30, sex=sex, waist_value=waist, physical_activity="vigorous", family_history="none"
    )
    assert res["breakdown"]["waist_points"] == expected_pts


def test_idrs_waist_inches_conversion():
    # 36 inches = 91.44 cm -> male 90-99 cm = 10 pts; female >= 90 cm = 20 pts
    rm = compute_mdrf_idrs(age_years=30, sex="male", waist_value=36, waist_unit="in", physical_activity="vigorous", family_history="none")
    rf = compute_mdrf_idrs(age_years=30, sex="female", waist_value=36, waist_unit="in", physical_activity="vigorous", family_history="none")
    assert rm["breakdown"]["waist_points"] == 10
    assert rf["breakdown"]["waist_points"] == 20


@pytest.mark.parametrize("act,pts", [("vigorous", 0), ("moderate", 10), ("mild", 20), ("sedentary", 30)])
def test_idrs_activity_points(act, pts):
    res = compute_mdrf_idrs(age_years=25, sex="male", waist_value=80, physical_activity=act, family_history="none")
    assert res["breakdown"]["activity_points"] == pts


@pytest.mark.parametrize("fam,pts", [("none", 0), ("one_parent", 10), ("both_parents", 20)])
def test_idrs_family_history_points(fam, pts):
    res = compute_mdrf_idrs(age_years=25, sex="male", waist_value=80, physical_activity="vigorous", family_history=fam)
    assert res["breakdown"]["family_history_points"] == pts


def test_idrs_risk_categories_and_max_score():
    low = compute_mdrf_idrs(age_years=25, sex="female", waist_value=70, physical_activity="moderate", family_history="one_parent")
    assert low["score"] == 20 and low["risk_category"] == "low"

    mod = compute_mdrf_idrs(age_years=35, sex="female", waist_value=82, physical_activity="vigorous", family_history="none")
    assert mod["score"] == 30 and mod["risk_category"] == "moderate"

    high = compute_mdrf_idrs(age_years=55, sex="male", waist_value=102, physical_activity="sedentary", family_history="both_parents")
    assert high["score"] == 100 and high["risk_category"] == "high"
    assert "not a diabetes diagnosis" in high["disclaimer"].lower()


# ---------------------------------------------------------------------------
# 2. Lab test interpretation unit tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("a1c,expected", [(5.4, "normal"), (5.7, "prediabetes"), (6.4, "prediabetes"), (6.5, "diabetes")])
def test_lab_hba1c_ranges(a1c, expected):
    res = interpret_lab_results(hba1c_pct=a1c)
    assert res["results"][0]["category"] == expected


@pytest.mark.parametrize("fpg,expected", [(95, "normal"), (100, "prediabetes"), (125, "prediabetes"), (126, "diabetes")])
def test_lab_fasting_glucose_ranges(fpg, expected):
    res = interpret_lab_results(fasting_glucose=fpg, fasting_unit="mg/dL")
    assert res["results"][0]["category"] == expected
    assert any("110–125" in n for n in res["guideline_notes"])


def test_lab_mmol_unit_conversion():
    # 7.0 mmol/L * 18.0182 = 126.13 mg/dL -> diabetes range
    res = interpret_lab_results(fasting_glucose=7.0, fasting_unit="mmol/L")
    assert res["results"][0]["category"] == "diabetes"


@pytest.mark.parametrize("ogtt,expected", [(130, "normal"), (140, "prediabetes"), (199, "prediabetes"), (200, "diabetes")])
def test_lab_ogtt_ranges(ogtt, expected):
    res = interpret_lab_results(ogtt_2h_glucose=ogtt)
    assert res["results"][0]["category"] == expected


def test_lab_random_glucose_symptom_requirement():
    asymp = interpret_lab_results(random_glucose=215, has_classic_symptoms=False)
    assert asymp["overall_category"] == "indeterminate_requires_confirmation"
    assert asymp["confirmation_required"] is True

    symp = interpret_lab_results(random_glucose=215, has_classic_symptoms=True)
    assert symp["overall_category"] == "diabetes_range"
    assert symp["confirmation_required"] is False


def test_lab_pregnancy_pathway_and_confirmation_advice():
    preg = interpret_lab_results(is_pregnant=True, fasting_glucose=98)
    assert preg["pregnancy_pathway"] is True
    assert preg["overall_category"] == "pregnancy_specialist_pathway"

    diab = interpret_lab_results(hba1c_pct=6.8)
    assert diab["confirmation_required"] is True
    assert "confirmation" in diab["guidance"].lower()
    assert any("home glucometer" in n.lower() for n in diab["guideline_notes"])


def test_lab_invalid_values_rejected():
    with pytest.raises(ValueError):
        interpret_lab_results()
    with pytest.raises(ValueError):
        interpret_lab_results(hba1c_pct=25.0)
    with pytest.raises(ValueError):
        interpret_lab_results(fasting_glucose=10.0, fasting_unit="mg/dL")


# ---------------------------------------------------------------------------
# 3. API, Auth, Consent & RLS Schema tests
# ---------------------------------------------------------------------------

def test_api_india_risk_endpoints_and_security():
    from backend.main import app
    client = TestClient(app, raise_server_exceptions=False)

    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200

    r_idrs = client.post("/api/v1/india-risk/idrs", json={
        "age_years": 42,
        "sex": "female",
        "waist_value": 85,
        "waist_unit": "cm",
        "physical_activity": "moderate",
        "family_history": "one_parent",
    })
    assert r_idrs.status_code == 200
    assert r_idrs.json()["score"] == 50
    assert r_idrs.json()["risk_category"] == "moderate"

    r_bad_age = client.post("/api/v1/india-risk/idrs", json={
        "age_years": 18,
        "sex": "male",
        "waist_value": 85,
        "physical_activity": "vigorous",
        "family_history": "none",
    })
    assert r_bad_age.status_code == 422

    r_lab = client.post("/api/v1/india-risk/lab-interpret", json={
        "hba1c_pct": 6.6,
        "is_pregnant": False,
    })
    assert r_lab.status_code == 200
    assert r_lab.json()["overall_category"] == "diabetes_range"
    assert r_lab.json()["confirmation_required"] is True

    # Auth required for all history endpoints
    assert client.get("/api/v1/india-risk/history").status_code == 401
    assert client.get("/api/v1/india-risk/history/export").status_code == 401
    assert client.post("/api/v1/india-risk/history", json={"consent": True, "assessment_type": "mdrf_idrs"}).status_code == 401
    assert client.delete("/api/v1/india-risk/history").status_code == 401


def test_supabase_rls_schema_present():
    schema = (ROOT / "backend" / "schema_india_screening.sql").read_text(encoding="utf-8")
    assert "india_risk_assessments" in schema
    assert "enable row level security" in schema
    assert "auth.uid()) = user_id" in schema
    assert "consent = true" in schema
