"""SQLite storage for prediction history.

Two tables:
  model_runs   - one row per trained model (so every prediction can be traced back)
  predictions  - one row per saved prediction, linked to model_runs

All SQL uses "?" placeholders (never string formatting) so typed text can never
be run as SQL (SQL-injection safe).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import config as C

SCHEMA = """
CREATE TABLE IF NOT EXISTS model_runs (
    model_version   TEXT PRIMARY KEY,
    model_name      TEXT NOT NULL,
    trained_at      TEXT NOT NULL,
    dataset_sha256  TEXT,
    cv_roc_auc      REAL,
    test_roc_auc    REAL,
    sklearn_version TEXT
);
CREATE TABLE IF NOT EXISTS predictions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT    NOT NULL,
    patient_ref     TEXT,
    pregnancies     REAL,
    glucose         REAL,
    blood_pressure  REAL,
    skin_thickness  REAL,
    insulin         REAL,
    bmi             REAL,
    dpf             REAL,
    age             REAL,
    model_version   TEXT    NOT NULL REFERENCES model_runs(model_version),
    probability     REAL    NOT NULL CHECK (probability BETWEEN 0 AND 1),
    threshold       REAL    NOT NULL,
    predicted_label INTEGER NOT NULL CHECK (predicted_label IN (0, 1)),
    band            TEXT    NOT NULL,
    top_factors     TEXT,
    warnings        TEXT,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_predictions_created ON predictions(created_at);
"""

FEATURE_TO_COLUMN = {
    "Pregnancies": "pregnancies", "Glucose": "glucose", "BloodPressure": "blood_pressure",
    "SkinThickness": "skin_thickness", "Insulin": "insulin", "BMI": "bmi",
    "DiabetesPedigreeFunction": "dpf", "Age": "age",
}


@contextmanager
def connect(path=C.DB_PATH):
    """Open the database (creating tables if needed); commit on success, always close."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def register_model_run(run: dict, path=C.DB_PATH) -> None:
    """Insert the model description once (ignored if that version already exists)."""
    with connect(path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO model_runs (model_version, model_name, trained_at, dataset_sha256,"
            " cv_roc_auc, test_roc_auc, sklearn_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run["model_version"], run["model_name"], run.get("trained_at", _now()),
             run.get("dataset_sha256"), run.get("cv_roc_auc"), run.get("test_roc_auc"),
             run.get("sklearn_version")))


def insert_prediction(rec: dict, path=C.DB_PATH) -> int:
    """Save one prediction. `rec["inputs"]` maps feature name -> number or None."""
    inputs = rec["inputs"]
    cols = {FEATURE_TO_COLUMN[f]: (None if inputs.get(f) is None or pd.isna(inputs.get(f))
                                   else float(inputs[f])) for f in C.FEATURES}
    with connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO predictions (created_at, patient_ref, pregnancies, glucose, blood_pressure,"
            " skin_thickness, insulin, bmi, dpf, age, model_version, probability, threshold,"
            " predicted_label, band, top_factors, warnings, notes)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_now(), rec.get("patient_ref"), cols["pregnancies"], cols["glucose"], cols["blood_pressure"],
             cols["skin_thickness"], cols["insulin"], cols["bmi"], cols["dpf"], cols["age"],
             rec["model_version"], float(rec["probability"]), float(rec["threshold"]),
             int(rec["predicted_label"]), rec["band"],
             json.dumps(rec.get("top_factors", [])), json.dumps(rec.get("warnings", [])), rec.get("notes")))
        return int(cur.lastrowid)


def list_predictions(limit: int = 200, offset: int = 0, path=C.DB_PATH) -> pd.DataFrame:
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT p.*, m.model_name FROM predictions p JOIN model_runs m USING (model_version)"
            " ORDER BY p.id DESC LIMIT ? OFFSET ?", (int(limit), int(offset))).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def get_prediction(pred_id: int, path=C.DB_PATH) -> dict | None:
    with connect(path) as conn:
        row = conn.execute("SELECT p.*, m.model_name FROM predictions p JOIN model_runs m"
                           " USING (model_version) WHERE p.id = ?", (int(pred_id),)).fetchone()
    return dict(row) if row else None


def delete_prediction(pred_id: int, path=C.DB_PATH) -> bool:
    with connect(path) as conn:
        cur = conn.execute("DELETE FROM predictions WHERE id = ?", (int(pred_id),))
        return cur.rowcount == 1


def delete_all_predictions(path=C.DB_PATH) -> int:
    """Delete every prediction in this local database and return the count."""
    with connect(path) as conn:
        cur = conn.execute("DELETE FROM predictions")
        return int(cur.rowcount)


def count_predictions(path=C.DB_PATH) -> int:
    with connect(path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0])
