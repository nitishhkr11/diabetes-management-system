"""Saving/loading models, input checks, predictions and SHAP explanations."""
import numpy as np
import pytest

from src import config as C
from src.explain import PatientExplainer
from src.predict import (ArtifactError, check_inputs, load_artifacts, predict_one, risk_band,
                         save_artifacts)
from src.preprocessing import training_profile

GOOD = dict(Pregnancies=2, Glucose=120, BloodPressure=70, SkinThickness=25, Insulin=100, BMI=30.0,
            DiabetesPedigreeFunction=0.4, Age=33)


@pytest.fixture(scope="module")
def saved(tmp_path_factory, synthetic_split, fitted_synthetic):
    X_train, _, _, _ = synthetic_split
    folder = tmp_path_factory.mktemp("models")
    card = {"profile": training_profile(X_train), "threshold": 0.5, "dataset": {"canonical_sha256": "test"},
            "cv_table": [], "test_table": []}
    save_artifacts(fitted_synthetic, "Logistic Regression", card, folder)
    return load_artifacts(folder, background=X_train, allow_unverified_dataset=True), folder


# ----------------------------------------------------------------- files
def test_saved_models_give_the_same_probabilities(saved, synthetic_split, fitted_synthetic):
    art, _ = saved
    assert art.card["model_version"] == art.card["files"][art.selected]["sha256"][:12]
    assert set(art.pipelines) == set(art.card["model_names"])
    _, X_test, _, _ = synthetic_split
    for name, pipe in fitted_synthetic.items():
        np.testing.assert_allclose(art.pipelines[name].predict_proba(X_test), pipe.predict_proba(X_test))


def test_a_tampered_model_file_is_refused_before_loading(saved):
    _, folder = saved
    path = folder / "logistic_regression.joblib"
    original = path.read_bytes()
    try:
        path.write_bytes(original + b"x")
        with pytest.raises(ArtifactError, match="SHA-256"):
            load_artifacts(folder, allow_unverified_dataset=True)
    finally:
        path.write_bytes(original)


def test_missing_model_card_says_what_to_do(tmp_path):
    with pytest.raises(ArtifactError, match="Train first"):
        load_artifacts(tmp_path)


def test_wrong_dataset_fingerprint_is_rejected_by_default(saved):
    _, folder = saved
    with pytest.raises(ArtifactError, match="verified Pima dataset"):
        load_artifacts(folder)


# ---------------------------------------------------------------- inputs
def test_a_normal_complete_input_has_no_errors_or_warnings(saved):
    art, _ = saved
    row, errors, warnings = check_inputs(GOOD, art.card["profile"])
    assert errors == [] and warnings == [] and row.shape == (1, 8)


def test_zero_in_a_measurement_means_unknown(saved):
    art, _ = saved
    row, errors, warnings = check_inputs({**GOOD, "Insulin": 0}, art.card["profile"])
    assert errors == [] and np.isnan(row.loc[0, "Insulin"]) and any("Insulin" in w for w in warnings)


def test_zero_pregnancies_is_a_valid_answer():
    row, errors, _ = check_inputs({**GOOD, "Pregnancies": 0})
    assert errors == [] and row.loc[0, "Pregnancies"] == 0


def test_required_fields_cannot_be_unknown():
    _, errors, _ = check_inputs({**GOOD, "Age": None})
    assert any("Age" in e for e in errors)


@pytest.mark.parametrize("field,value", [("Glucose", 30), ("Age", 15), ("BMI", -5),
                                         ("BloodPressure", 400), ("Pregnancies", 25)])
def test_impossible_values_are_blocked(field, value):
    _, errors, _ = check_inputs({**GOOD, field: value})
    assert any(field in e for e in errors)


def test_a_value_outside_the_training_range_warns_but_still_predicts(saved):
    art, _ = saved
    out = predict_one(art, {**GOOD, "Glucose": 400})
    assert out["ok"]
    assert any("outside the range seen in training" in w for w in out["warnings"])


def test_three_unknown_measurements_trigger_a_reliability_warning(saved):
    art, _ = saved
    out = predict_one(art, {**GOOD, "Insulin": 0, "SkinThickness": 0, "BloodPressure": 0})
    assert any("3 of 5 measurements are unknown" in w for w in out["warnings"])


# ----------------------------------------------------------- predictions
def test_prediction_has_every_field_the_app_needs(saved):
    art, _ = saved
    out = predict_one(art, GOOD)
    assert out["ok"] and 0 <= out["probability"] <= 1
    assert out["label"] == int(out["probability"] >= out["threshold"])
    assert out["band"] in {"Lower", "Intermediate", "Higher"}
    assert set(out["all_models"]) == set(art.pipelines)
    assert out["explanation"]["additivity_error"] < 1e-4


def test_rejected_input_returns_errors_and_no_probability(saved):
    art, _ = saved
    out = predict_one(art, {**GOOD, "Age": 15})
    assert out["ok"] is False and out["errors"] and "probability" not in out


def test_risk_band_edges():
    assert risk_band(0.50, 0.5) == "Higher"
    assert risk_band(0.25, 0.5) == "Intermediate"
    assert risk_band(0.249, 0.5) == "Lower"


# ------------------------------------------------------------------ SHAP
@pytest.mark.parametrize("name", C.MODEL_ORDER)
def test_shap_contributions_add_up_for_every_model(name, fitted_synthetic, synthetic_split):
    X_train, X_test, _, _ = synthetic_split
    explainer = PatientExplainer(fitted_synthetic[name], X_train)
    assert explainer.units == ("log-odds" if name == "Logistic Regression" else "probability")
    for i in (0, 5, 10):
        e = explainer.explain_one(X_test.iloc[[i]])
        assert e["base_value"] + sum(c["contribution"] for c in e["contributions"]) == pytest.approx(e["output_value"])
        assert e["additivity_error"] < 1e-4          # baseline + contributions = what the model really outputs
        assert 0 <= e["probability"] <= 1


def test_shap_direction_is_sensible_for_logistic_regression(fitted_synthetic, synthetic_split):
    X_train, X_test, _, _ = synthetic_split
    explainer = PatientExplainer(fitted_synthetic["Logistic Regression"], X_train)
    high, low = X_test.iloc[[0]].copy(), X_test.iloc[[0]].copy()
    high["Glucose"], low["Glucose"] = 190.0, 70.0
    c_high = {c["feature"]: c["contribution"] for c in explainer.explain_one(high)["contributions"]}
    c_low = {c["feature"]: c["contribution"] for c in explainer.explain_one(low)["contributions"]}
    assert c_high["Glucose"] > 0 > c_low["Glucose"]


def test_filled_in_values_are_flagged_in_the_explanation(fitted_synthetic, synthetic_split):
    X_train, X_test, _, _ = synthetic_split
    explainer = PatientExplainer(fitted_synthetic["Random Forest"], X_train)
    row = X_test.iloc[[0]].copy()
    row["Insulin"], row["Glucose"] = 0.0, 120.0
    flags = {c["feature"]: c["was_missing"] for c in explainer.explain_one(row)["contributions"]}
    assert flags["Insulin"] is True and flags["Glucose"] is False


def test_global_importance_lists_all_features(fitted_synthetic, synthetic_split):
    X_train, X_test, _, _ = synthetic_split
    imp = PatientExplainer(fitted_synthetic["Logistic Regression"], X_train).global_importance(X_test)
    assert sorted(imp["feature"]) == sorted(C.FEATURES)
    assert (imp["mean_abs_shap"] >= 0).all() and imp["mean_abs_shap"].is_monotonic_decreasing
