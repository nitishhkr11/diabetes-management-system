"""
Public screening config — feature schema and input limits for Model 2.
Kept separate from src/config.py (Pima model) to prevent cross-contamination.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_MODELS_DIR = ROOT / "models" / "public_screening"
PUBLIC_DATA_PATH  = ROOT / "data" / "nhanes_processed.csv"
PUBLIC_REPORTS_DIR = ROOT / "reports" / "public_screening"

# Exact feature order — must match model card
PUBLIC_FEATURES = [
    "age_years",
    "sex_male",
    "bmi",
    "waist_cm",
    "sys_bp",
    "dia_bp",
    "mod_days_per_week",
    "vig_days_per_week",
    "sedentary_min_day",
    "smoked_100",
    "current_smoker",
]

PUBLIC_FEATURE_LABELS = {
    "age_years":           "Age (years)",
    "sex_male":            "Sex",
    "bmi":                 "BMI (kg/m²)",
    "waist_cm":            "Waist circumference (cm)",
    "sys_bp":              "Systolic blood pressure (mmHg)",
    "dia_bp":              "Diastolic blood pressure (mmHg)",
    "mod_days_per_week":   "Moderate physical activity (days/week)",
    "vig_days_per_week":   "Vigorous physical activity (days/week)",
    "sedentary_min_day":   "Sedentary time (minutes/day)",
    "smoked_100":          "Ever smoked ≥100 cigarettes",
    "current_smoker":      "Currently smoking",
}

PUBLIC_INPUT_LIMITS = {
    "age_years":           (21,   80),
    "sex_male":            (0,    1),
    "bmi":                 (10.0, 70.0),
    "waist_cm":            (40.0, 200.0),
    "sys_bp":              (60.0, 220.0),
    "dia_bp":              (20.0, 130.0),
    "mod_days_per_week":   (0,    7),
    "vig_days_per_week":   (0,    7),
    "sedentary_min_day":   (0,    1440),
    "smoked_100":          (0,    1),
    "current_smoker":      (0,    1),
}

PUBLIC_MODEL_VERSION = "ps_v1"
