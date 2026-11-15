"""End-to-end: the research release trains and reloads its hashed artifacts."""
import subprocess
import sys

import pandas as pd
import pytest

from src.predict import load_artifacts
from tests.conftest import ROOT


@pytest.mark.slow
def test_training_script_runs_nested_protocol_and_stays_honest(real_df, tmp_path):
    models, reports = tmp_path / "models", tmp_path / "reports"
    run = subprocess.run(
        [sys.executable, "scripts/train.py", "--bootstrap", "300", "--models-dir", str(models),
         "--reports-dir", str(reports), "--model-card", str(tmp_path / "MODEL_CARD.md")],
        cwd=ROOT, capture_output=True, text=True, timeout=900)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]

    art = load_artifacts(models)                                    # also re-checks every SHA-256
    assert art.selected in art.pipelines and art.card["dataset"]["canonical_sha256"]
    assert set(art.pipelines) == {"Logistic Regression", "Gaussian Naive Bayes", "Random Forest",
                                  "SVM (RBF)", "Gradient Boosting"}
    test = pd.read_csv(reports / "test_metrics.csv")
    assert len(test) == 1 and test["roc_auc"].between(0.70, 0.90).all(), test[["model", "roc_auc"]]
    assert test.iloc[0].model == art.selected
    assert float(art.card["threshold"]) == pytest.approx(float(test.iloc[0].threshold))
    assert len(pd.read_csv(reports / "nested_oof_metrics.csv")) == 5
    assert (reports / "threshold_table_nested_oof.csv").exists()
    assert (reports / "research_experiment.json").exists()
    assert (reports / "baseline_vs_research.csv").exists()
