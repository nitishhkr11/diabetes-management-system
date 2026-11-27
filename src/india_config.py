"""
India-specific screening config — ICMR-INDIAB research model (Model 3).

Completely independent from src/config.py (Pima) and src/public_config.py (NHANES).
No artifacts, feature schemas, or endpoints are shared.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INDIA_RAW_DIR = ROOT / "data" / "private" / "indiab" / "raw"
INDIA_PROCESSED_DIR = ROOT / "data" / "private" / "indiab" / "processed"
INDIA_MANIFEST_PATH = ROOT / "data" / "private" / "indiab" / "manifest.json"
INDIA_AUDIT_DIR = ROOT / "data" / "reports"
INDIA_MODELS_DIR = ROOT / "models" / "india_indiab"
INDIA_REPORTS_DIR = ROOT / "reports" / "india_indiab"

INDIA_MODEL_LABEL = "ICMR-INDIAB Indian adult research model"
INDIA_MODEL_VERSION = "in_v1"
INDIA_MIN_AGE = 20
INDIA_MAX_AGE = 100

DATA_ACQUISITION_STATUSES = (
    "NOT REQUESTED",
    "REQUEST SUBMITTED",
    "ACCESS APPROVED",
    "DATA RECEIVED",
    "DATA VERIFIED",
    "MODEL TRAINED",
)

# Survey design & identifier columns (never used as model features)
SURVEY_DESIGN_COLUMNS = [
    "participant_id",
    "psu_id",
    "stratum_id",
    "survey_weight",
]

# Variables used to construct WHO diabetes target — strictly forbidden as predictors
FORBIDDEN_LEAKAGE_VARIABLES = {
    "diabetes_label",
    "fasting_glucose",
    "post_load_glucose_2h",
    "random_glucose",
    "hba1c",
    "self_reported_diabetes",
    "diabetes_medication",
    "newly_detected_diabetes",
    "known_diabetes",
}

# Candidate non-laboratory predictors for ICMR-INDIAB
INDIA_CANDIDATE_NUMERIC_FEATURES = [
    "age_years",
    "bmi",
    "waist_cm",
    "waist_height_ratio",
    "sys_bp",
    "dia_bp",
    "physical_activity_score",
]

INDIA_CANDIDATE_CATEGORICAL_FEATURES = [
    "sex",
    "residence_type",
    "state_region",
    "family_history_diabetes",
    "tobacco_use",
    "alcohol_use",
    "education_level",
    "ses_indicator",
]

INDIA_ALL_CANDIDATE_FEATURES = (
    INDIA_CANDIDATE_NUMERIC_FEATURES + INDIA_CANDIDATE_CATEGORICAL_FEATURES
)

INDIA_FEATURE_LABELS = {
    "age_years": "Age (years, 20+)",
    "sex": "Sex",
    "bmi": "BMI (kg/m²)",
    "waist_cm": "Waist circumference (cm)",
    "waist_height_ratio": "Waist-to-height ratio",
    "sys_bp": "Systolic blood pressure (mmHg)",
    "dia_bp": "Diastolic blood pressure (mmHg)",
    "family_history_diabetes": "Family history of diabetes",
    "physical_activity_score": "Physical activity level",
    "tobacco_use": "Tobacco use (smoking/smokeless)",
    "alcohol_use": "Alcohol use",
    "education_level": "Education level",
    "ses_indicator": "Socioeconomic indicator",
    "residence_type": "Residence (rural/urban)",
    "state_region": "State or region",
}

INDIA_INPUT_LIMITS = {
    "age_years": (20.0, 100.0),
    "bmi": (10.0, 70.0),
    "waist_cm": (40.0, 200.0),
    "waist_height_ratio": (0.25, 1.20),
    "sys_bp": (60.0, 240.0),
    "dia_bp": (30.0, 140.0),
    "physical_activity_score": (0.0, 10000.0),
}

# Existing model labels (preserved and clarified per governance rules)
PIMA_MODEL_LABEL = "Historical Pima research benchmark"
NHANES_MODEL_LABEL = "US population research benchmark"
