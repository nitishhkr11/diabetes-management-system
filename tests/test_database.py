"""SQLite history: constraints, parameterised queries and CRUD."""
import sqlite3

import pytest

from src import database as db


def model_run(version="v1"):
    return {"model_version": version, "model_name": "Logistic Regression",
            "trained_at": "2026-01-01T00:00:00+00:00", "dataset_sha256": "abc",
            "cv_roc_auc": 0.84, "test_roc_auc": 0.81, "sklearn_version": "1.8.0"}


def record(version="v1", **changes):
    base = {"patient_ref": "demo-1",
            "inputs": {"Pregnancies": 2, "Glucose": 120, "BloodPressure": 70, "SkinThickness": None,
                       "Insulin": None, "BMI": 30.5, "DiabetesPedigreeFunction": 0.4, "Age": 33},
            "model_version": version, "probability": 0.42, "threshold": 0.5, "predicted_label": 0,
            "band": "Intermediate", "top_factors": ["Glucose +0.8"], "warnings": ["Insulin not provided"],
            "notes": "test"}
    base.update(changes)
    return base


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "test.db"
    db.register_model_run(model_run(), p)
    return p


def test_insert_get_list_delete(path):
    ids = [db.insert_prediction(record(patient_ref=f"p{i}"), path) for i in range(3)]
    assert ids == [1, 2, 3]
    assert db.count_predictions(path) == 3
    assert db.list_predictions(path=path)["id"].tolist() == [3, 2, 1]          # newest first
    assert db.list_predictions(limit=1, offset=1, path=path)["id"].tolist() == [2]
    row = db.get_prediction(2, path)
    assert row["patient_ref"] == "p1" and row["glucose"] == 120 and row["model_name"] == "Logistic Regression"
    assert db.delete_prediction(2, path) is True
    assert db.delete_prediction(2, path) is False
    assert db.get_prediction(2, path) is None


def test_unknown_values_are_stored_as_null(path):
    pid = db.insert_prediction(record(), path)
    row = db.get_prediction(pid, path)
    assert row["insulin"] is None and row["skin_thickness"] is None and row["bmi"] == 30.5


def test_a_prediction_must_point_to_a_registered_model(path):
    with pytest.raises(sqlite3.IntegrityError):
        db.insert_prediction(record(version="not-registered"), path)


@pytest.mark.parametrize("changes", [{"probability": 1.5}, {"probability": -0.1}, {"predicted_label": 2}])
def test_check_constraints_reject_impossible_values(path, changes):
    with pytest.raises(sqlite3.IntegrityError):
        db.insert_prediction(record(**changes), path)
    assert db.count_predictions(path) == 0                                      # nothing half-saved


def test_typed_sql_is_stored_as_plain_text_not_executed(path):
    nasty = "x'); DROP TABLE predictions;--"
    pid = db.insert_prediction(record(patient_ref=nasty, notes=nasty), path)
    assert db.count_predictions(path) == 1                                      # the table still exists
    assert db.get_prediction(pid, path)["patient_ref"] == nasty


def test_registering_the_same_model_twice_keeps_one_row(path):
    db.register_model_run(model_run(), path)
    with db.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM model_runs").fetchone()[0] == 1


def test_delete_all_returns_removed_record_count(path):
    for i in range(3):
        db.insert_prediction(record(patient_ref=f"case-{i}"), path)
    assert db.delete_all_predictions(path) == 3
    assert db.count_predictions(path) == 0
