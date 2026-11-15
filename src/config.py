"""Central settings for the Diabetes Management System (educational prototype).

Everything a student might want to change lives in this one file, so there are
no "magic numbers" hidden inside the other modules.
"""
from pathlib import Path

# ----------------------------------------------------------------- locations
ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "diabetes.csv"
DB_PATH = ROOT / "data" / "predictions.db"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
EXPERIMENTS_DIR = REPORTS_DIR / "experiments"

# ------------------------------------------------------------------- columns
FEATURES = [
    "Pregnancies", "Glucose", "BloodPressure", "SkinThickness",
    "Insulin", "BMI", "DiabetesPedigreeFunction", "Age",
]
TARGET = "Outcome"

# For these five columns a value of 0 is physiologically impossible, so a 0
# really means "not measured". (Pregnancies = 0 is a perfectly valid answer.)
ZERO_AS_MISSING = ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"]

# Label and unit shown to people (UCI documents the meaning of each column).
FEATURE_LABELS = {
    "Pregnancies": "Number of pregnancies",
    "Glucose": "Plasma glucose, 2 h after oral glucose load (mg/dL)",
    "BloodPressure": "Diastolic blood pressure (mm Hg)",
    "SkinThickness": "Triceps skin-fold thickness (mm)",
    "Insulin": "2-hour serum insulin (mu U/ml)",
    "BMI": "Body mass index (kg/m^2)",
    "DiabetesPedigreeFunction": "Diabetes pedigree function (family-history score)",
    "Age": "Age (years)",
}

# ------------------------------------------------------- experiment settings
RANDOM_STATE = 42          # fixes every random choice -> repeatable results
TEST_SIZE = 0.20           # the 80:20 split
CV_FOLDS = 5               # cross-validation folds used on the TRAINING part
DECISION_THRESHOLD = 0.50  # probability >= threshold -> predicted "positive"
TIE_TOLERANCE = 0.005      # two scores closer than this count as a tie
MODEL_ORDER = ["Logistic Regression", "Gaussian Naive Bayes", "Random Forest"]  # simplest first

# Targets copied from the project brief. They are TARGETS, never results.
PROJECT_TARGETS = {"roc_auc": 0.95, "accuracy": 0.96, "f1": 0.75, "recall": 0.65}

# ------------------------------------------- what the GENUINE Pima file is
# Verified on three independent public copies on 2026-10-01 (see data/README_DATA.md).
EXPECTED_ROWS = 768
EXPECTED_CLASS_COUNTS = {0: 500, 1: 268}
EXPECTED_ZERO_COUNTS = {
    "Pregnancies": 111, "Glucose": 5, "BloodPressure": 35,
    "SkinThickness": 227, "Insulin": 374, "BMI": 11,
}
# Hash of the *values* (independent of line endings and "31" vs "31.0").
KNOWN_CANONICAL_SHA256 = "00921e2c6a3f645b215270e6b481a1b3e6283f1db4ee498d0de9b5a9cd0b240b"

# --------------------------------------------------- input limits for the app
# HARD limits: outside these a value is physiologically impossible (or outside
# the studied population: women aged 21+) -> the app refuses to predict.
# These are engineering choices made by us, NOT clinical thresholds.
HARD_LIMITS = {
    "Pregnancies": (0, 20),
    "Glucose": (40, 500),
    "BloodPressure": (30, 150),
    "SkinThickness": (3, 100),
    "Insulin": (1, 1000),
    "BMI": (10, 80),
    "DiabetesPedigreeFunction": (0.01, 3.0),
    "Age": (21, 100),
}
