"""One-page demonstration: why some public repositories report ROC-AUC 0.94 on the Pima data.

    python scripts/leakage_demo.py

Several public projects ship a copy of the file in which every missing value was replaced by
the median of the SAME CLASS. This script applies that recipe to the genuine file and trains the
same Random Forest (200 trees, random_state=42, stratified 80:20 split, as in one of those
repositories) twice: once on the leaky table and once with the correct leak-free pipeline.
Only a single split is used here, so treat the numbers as an illustration; experiment B in
scripts/experiments.py repeats this over 20 splits.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import accuracy_score, roc_auc_score  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from src import config as C  # noqa: E402
from src.data_validation import load_dataset  # noqa: E402
from src.leaky_recipes import class_conditional_fill, class_medians  # noqa: E402
from src.preprocessing import build_pipeline, split_data  # noqa: E402

# (factory, scale the leaky table first?)  The Random Forest in that repository used the raw numbers.
MODELS = {
    "Random Forest (200 trees)": (lambda: RandomForestClassifier(n_estimators=200, random_state=C.RANDOM_STATE), False),
    "Logistic Regression": (lambda: LogisticRegression(max_iter=1000), True),
}


def scores(fitted, X_test, y_test):
    p = fitted.predict_proba(X_test)[:, 1]
    return roc_auc_score(y_test, p), accuracy_score(y_test, p >= 0.5)


def main() -> int:
    df = load_dataset()
    print("Constants the 'same-class median' recipe writes into the five columns:")
    print(class_medians(df).round(2).to_string())
    print(f"\nrows that got a constant: Glucose {C.EXPECTED_ZERO_COUNTS['Glucose']}, BloodPressure "
          f"{C.EXPECTED_ZERO_COUNTS['BloodPressure']}, SkinThickness {C.EXPECTED_ZERO_COUNTS['SkinThickness']}, "
          f"Insulin {C.EXPECTED_ZERO_COUNTS['Insulin']}, BMI {C.EXPECTED_ZERO_COUNTS['BMI']}")

    leaky = class_conditional_fill(df)
    X, y = leaky[C.FEATURES], leaky[C.TARGET]
    Xl_tr, Xl_te, yl_tr, yl_te = train_test_split(X, y, test_size=C.TEST_SIZE, random_state=C.RANDOM_STATE, stratify=y)
    X_tr, X_te, y_tr, y_te = split_data(df)

    print(f"\n{'model':28s} {'leaky table: AUC / accuracy':>30s} {'correct pipeline: AUC / accuracy':>36s}")
    for name, (make, scale) in MODELS.items():
        leaky_fit = (make_pipeline(StandardScaler(), make()) if scale else make()).fit(Xl_tr, yl_tr)
        clean_fit = build_pipeline(make()).fit(X_tr, y_tr)
        (a1, c1), (a2, c2) = scores(leaky_fit, Xl_te, yl_te), scores(clean_fit, X_te, y_te)
        print(f"{name:28s} {a1:>18.4f} / {c1:.4f} {a2:>24.4f} / {c2:.4f}")
    print("\nReading: the flexible model (Random Forest) gains a lot from the leak; the simple one barely does.")
    print("A big jump for a flexible model with no jump for Logistic Regression is a classic leakage fingerprint.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
