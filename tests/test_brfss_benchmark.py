"""
Tests for CDC BRFSS Research Benchmark (UCI ID 891).
Verifies real downloaded dataset metadata, model card, independent 3-model metrics,
FastAPI endpoints, and frontend scientific honesty statements.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def test_brfss_model_card_and_reports_exist():
    card_path = ROOT / "models" / "brfss_benchmark" / "model_card.json"
    assert card_path.is_file()
    card = json.loads(card_path.read_text(encoding="utf-8"))
    assert card["dataset"]["n_records"] == 253680
    assert card["dataset"]["n_features"] == 21
    assert card["dataset"]["target_column"] == "Diabetes_binary"
    assert set(card["models"].keys()) == {"Logistic Regression", "Random Forest", "Gradient Boosting"}
    assert "not validated for Indian adults" in card["limitation_statement"]


def test_brfss_models_have_independent_metrics():
    card = json.loads((ROOT / "models" / "brfss_benchmark" / "model_card.json").read_text(encoding="utf-8"))
    cms = {m: tuple(v["confusion_matrix"].values()) for m, v in card["models"].items()}
    # Ensure confusion matrices are genuinely distinct across the 3 algorithms
    assert len(set(cms.values())) == 3


def test_api_brfss_endpoints():
    from backend.main import app
    client = TestClient(app, raise_server_exceptions=False)

    rm = client.get("/api/v1/brfss-benchmark/metadata")
    assert rm.status_code == 200
    assert rm.json()["available"] is True
    assert rm.json()["dataset"]["n_records"] == 253680

    re = client.get("/api/v1/brfss-benchmark/evaluation")
    assert re.status_code == 200
    body = re.json()
    assert body["available"] is True
    assert len(body["model_comparison"]) == 3
    assert set(body["roc_curves"].keys()) == {"Logistic Regression", "Random Forest", "Gradient Boosting"}
    assert set(body["pr_curves"].keys()) == {"Logistic Regression", "Random Forest", "Gradient Boosting"}


def test_frontend_brfss_section_and_limitation():
    research_src = (ROOT / "frontend" / "src" / "app" / "research" / "page.tsx").read_text(encoding="utf-8")
    datasets_src = (ROOT / "frontend" / "src" / "app" / "datasets" / "page.tsx").read_text(encoding="utf-8")
    assert "CDC BRFSS RESEARCH BENCHMARK" in research_src
    assert "CDC BRFSS" in datasets_src
    assert "limitation_statement" in research_src
