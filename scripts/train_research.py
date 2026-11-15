"""Run nested-CV model comparison and publish the selected Pima pipeline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, roc_curve

from src import config as C
from src.data_validation import canonical_sha256, load_dataset, sha256_file
from src.predict import save_artifacts
from src.preprocessing import split_data, training_profile
from src.explain import PatientExplainer
from src import plots as P
from src.research import (MODEL_GRIDS, calibration_bins, choose_threshold, fit_tuned, metrics,
                          nested_oof, select_family, stratified_bootstrap_ci)
from scripts.export_interactive_charts import write_interactive_chart_data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default=str(C.DATA_PATH))
    ap.add_argument("--models-dir", default=str(C.MODELS_DIR))
    ap.add_argument("--reports-dir", default=str(C.REPORTS_DIR))
    ap.add_argument("--model-card", default=str(C.ROOT / "docs" / "MODEL_CARD.md"))
    ap.add_argument("--outer-folds", type=int, default=5)
    ap.add_argument("--inner-folds", type=int, default=4)
    ap.add_argument("--bootstrap", type=int, default=2000)
    args = ap.parse_args(argv)
    models_dir, reports = Path(args.models_dir), Path(args.reports_dir)
    reports.mkdir(parents=True, exist_ok=True)
    old_card_path = models_dir / "model_card.json"
    old_card = json.loads(old_card_path.read_text(encoding="utf-8")) if old_card_path.exists() else {}
    df = load_dataset(args.data)
    raw_hash, data_hash = sha256_file(args.data), canonical_sha256(df)
    X_train, X_test, y_train, y_test = split_data(df)
    print(f"Validated {len(df)} rows. Stratified 80:20 split; training only for selection.", flush=True)
    print("Running nested stratified CV; preprocessing and tuning stay inside outer training folds.", flush=True)

    oof, cv_rows = {}, []
    for name in MODEL_GRIDS:
        pred = nested_oof(name, X_train, y_train, args.outer_folds, args.inner_folds)
        oof[name] = pred
        row = {"model": name, **metrics(y_train, pred, 0.5)}
        cv_rows.append(row)
        print(f"  {name}: OOF ROC-AUC={row['roc_auc']:.3f}; recall@0.50={row['recall']:.3f}", flush=True)
    cv_table = pd.DataFrame(cv_rows)

    # Explicit training-only ablation: compare fixed class-weight policy for
    # the same three estimator families using nested OOF scores at threshold .5.
    weighting_rows = []
    for name in ("Logistic Regression", "Random Forest", "SVM (RBF)"):
        for weight in (None, "balanced"):
            pred = nested_oof(name, X_train, y_train, args.outer_folds, args.inner_folds,
                              force_class_weight=weight)
            weighting_rows.append({"model": name, "class_weight": weight or "none",
                                   **metrics(y_train, pred, 0.5)})
        unweighted = weighting_rows[-2]
        weighted = weighting_rows[-1]
        print(f"  weighting {name}: recall {unweighted['recall']:.3f} -> "
              f"{weighted['recall']:.3f}; precision {unweighted['precision']:.3f} -> "
              f"{weighted['precision']:.3f}", flush=True)
    weighting_table = pd.DataFrame(weighting_rows)
    weighting_table.to_csv(reports / "class_weight_ablation.csv", index=False)

    # Predeclared: maximize nested OOF ROC-AUC; within .005 prefer simpler/approved.
    selected = select_family(cv_table)
    threshold, threshold_table = choose_threshold(y_train, oof[selected], 0.65, 0.50)
    feasible = threshold is not None
    if threshold is None:
        threshold = 0.50
    threshold_table.to_csv(reports / "threshold_table_nested_oof.csv", index=False)
    print(f"Selected {selected}. OOF threshold objective recall>=0.65 and precision>=0.50: " +
          (f"{threshold:.4f}" if feasible else "not feasible; use 0.50"), flush=True)

    print("Tuning each family on all training rows; test rows remain sealed.", flush=True)
    fitted, params, inner_scores = {}, {}, {}
    for name in MODEL_GRIDS:
        fitted[name], params[name], inner_scores[name] = fit_tuned(
            name, X_train, y_train, inner_folds=args.inner_folds)
        print(f"  fitted {name}", flush=True)

    # One and only one final test evaluation, after all choices are fixed.
    test_proba = fitted[selected].predict_proba(X_test)[:, 1]
    final_metrics = metrics(y_test, test_proba, threshold)
    test_row = {"model": selected, "threshold": threshold, **final_metrics}
    pd.DataFrame([test_row]).to_csv(reports / "test_metrics.csv", index=False)
    ci = stratified_bootstrap_ci(y_test, test_proba, threshold, args.bootstrap)
    pd.DataFrame([{"metric": k, "lower_95": v[0], "upper_95": v[1]} for k, v in ci.items()]).to_csv(
        reports / "test_bootstrap_ci.csv", index=False)
    calibration = calibration_bins(y_test, test_proba)
    calibration.to_csv(reports / "calibration_test_bins.csv", index=False)
    fig, ax = plt.subplots(figsize=(5.5, 4.2))
    ax.plot([0, 1], [0, 1], "--", color="#687386", label="Ideal")
    if not calibration.empty:
        ax.plot(calibration.mean_predicted, calibration.observed_fraction, "o-", color="#2b7a78",
                label="Selected model")
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Mean predicted score",
           ylabel="Observed positive fraction", title=f"Test calibration · {selected}")
    ax.legend()
    fig.tight_layout()
    (reports / "figures").mkdir(exist_ok=True)
    fig.savefig(reports / "figures" / "calibration_test.png", dpi=150)
    plt.close(fig)

    # Refresh the established figure filenames so no plot from the former
    # release is accidentally served alongside the new model card.
    fig, ax = plt.subplots(figsize=(5.5, 4.2))
    fpr, tpr, thresholds = roc_curve(y_test, test_proba, drop_intermediate=False)
    ax.plot(fpr, tpr, color="#2b7a78", label=f"{selected} (AUC {final_metrics['roc_auc']:.3f})")
    ax.plot([0, 1], [0, 1], "--", color="#687386")
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="False positive rate", ylabel="True positive rate",
           title="Selected model · final test ROC")
    ax.legend()
    fig.tight_layout()
    fig.savefig(reports / "figures" / "roc_test.png", dpi=150)
    plt.close(fig)
    cm = confusion_matrix(y_test, test_proba >= threshold, labels=[0, 1])
    fig, ax = plt.subplots(figsize=(4.2, 3.8))
    im = ax.imshow(cm, cmap="Blues")
    ax.set(xticks=[0, 1], yticks=[0, 1], xticklabels=["Negative", "Positive"],
           yticklabels=["Negative", "Positive"], xlabel="Predicted label", ylabel="Actual label",
           title=f"{selected} · threshold {threshold:.3f}")
    for (i, j), value in np.ndenumerate(cm):
        ax.text(j, i, str(value), ha="center", va="center", color="black")
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(reports / "figures" / "confusion_test.png", dpi=150)
    plt.close(fig)
    explainer = PatientExplainer(fitted[selected], X_train)
    shap_importance = explainer.global_importance(X_test)
    shap_importance.to_csv(reports / "shap_global_importance.csv", index=False)
    P.save(P.plot_global_importance(shap_importance, units=explainer.units),
           reports / "figures" / "shap_global_bar.png")
    import shap
    shap.plots.beeswarm(explainer.explanation(X_test), show=False, max_display=8)
    P.save(plt.gcf(), reports / "figures" / "shap_beeswarm.png")
    plt.close("all")

    comparison_path = reports / "baseline_vs_research.csv"
    if comparison_path.exists():
        prior = pd.read_csv(comparison_path)
        baseline = prior[prior.release != "new_selected"].to_dict("records")
    else:
        baseline = [{"release": "saved_baseline_threshold_0.50", **r}
                    for r in old_card.get("test_table", [])]
        old_op = old_card.get("operating_point", {})
        old_thr = old_op.get("threshold")
        if old_thr is not None and old_op.get("test_metrics_at_threshold"):
            baseline.append({"release": f"saved_baseline_threshold_{old_thr:.2f}",
                             "model": old_card.get("selected_model"), "threshold": old_thr,
                             **old_op["test_metrics_at_threshold"]})
    baseline.append({"release": "new_selected", **test_row})
    pd.DataFrame(baseline).to_csv(reports / "baseline_vs_research.csv", index=False)
    cv_table.to_csv(reports / "nested_oof_metrics.csv", index=False)
    config = {
        "seed": C.RANDOM_STATE, "split": {"test_size": C.TEST_SIZE, "stratified": True},
        "outer_cv": {"folds": args.outer_folds, "shuffle": True, "seed": C.RANDOM_STATE},
        "inner_cv": {"folds": args.inner_folds, "shuffle": True, "tuning_metric": "roc_auc"},
        "predeclared_selection": "highest nested OOF ROC-AUC; within 0.005 prefer simpler (LR, GNB, RF, SVM, GB)",
        "threshold_objective": {"minimum_recall": 0.65, "minimum_precision": 0.50,
                                "rule": "highest nested OOF threshold meeting both constraints",
                                "feasible": feasible, "deployed_threshold": threshold},
        "search_grids": {name: grid for name, (_, grid) in MODEL_GRIDS.items()},
        "selected_model": selected, "full_training_best_params": params,
        "full_training_inner_best_auc": inner_scores,
        "class_weight_ablation_report": "class_weight_ablation.csv",
        "bootstrap": {"method": "stratified percentile bootstrap", "resamples": args.bootstrap,
                      "seed": C.RANDOM_STATE, "alpha": 0.05},
        "data": {"raw_sha256": raw_hash, "canonical_sha256": data_hash, "rows": len(df)},
        "current_run_test_used_for_selection": False,
        "historical_test_exposure": True,
        "independent_test_claim": False,
        "test_exposure_note": "Prior repository experiments explicitly examined thresholds and candidate models on this same nominal holdout. Current-run nested CV does not select using it, but it is historically exposed and is reported descriptively, not as an independent confirmatory test.",
        "limitations": "Small fixed split; bootstrap intervals condition on this test split and exclude training/model-selection uncertainty.",
    }
    (reports / "research_experiment.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    card = {
        "dataset": {"raw_sha256": raw_hash, "canonical_sha256": data_hash, "rows": len(df)},
        "random_state": C.RANDOM_STATE, "test_size": C.TEST_SIZE, "cv_folds": args.outer_folds,
        "threshold": float(threshold), "selection_rule": config["predeclared_selection"],
        "threshold_objective": config["threshold_objective"],
        "features": C.FEATURES, "profile": training_profile(X_train),
        "cv_table": cv_table.to_dict("records"), "test_table": [test_row],
        "test_confidence_intervals": ci, "calibration_bins": calibration.to_dict("records"),
        "selected_params": params[selected], "experiment_config": "research_experiment.json",
        "intended_use": "Educational research prototype. Not a medical diagnosis or personal risk estimate.",
        "population": "Historical records from Pima women aged 21+ near Phoenix, Arizona. No transportability established.",
        "protocol": "Nested stratified CV on training split; preprocessing and hyperparameter tuning fitted within outer training folds. The current training run evaluates the selected model once after choices are fixed. This nominal test split was examined by prior repository experiments, so it is historically exposed and not an independent confirmatory test.",
        "current_run_test_used_for_selection": False,
        "historical_test_exposure": True,
        "independent_test_claim": False,
        "test_exposure_note": config["test_exposure_note"],
        "data_fingerprint": data_hash,
    }
    card = save_artifacts(fitted, selected, card, models_dir)
    write_interactive_chart_data(
        model_version=card["model_version"], model=selected, threshold=threshold,
        roc_auc=final_metrics["roc_auc"],
        roc_points=[{"false_positive_rate": float(x), "true_positive_rate": float(y),
                     "threshold": float(value) if np.isfinite(value) else None}
                    for x, y, value in zip(fpr, tpr, thresholds, strict=True)],
        confusion_matrix={
            "actual_negative": {"predicted_negative": int(cm[0, 0]), "predicted_positive": int(cm[0, 1])},
            "actual_positive": {"predicted_negative": int(cm[1, 0]), "predicted_positive": int(cm[1, 1])},
            "sample_count": int(len(y_test)),
        },
        calibration_bins=calibration.to_dict("records"), shap_units=explainer.units,
        shap_importance=[{"feature": row.feature, "mean_abs_shap": float(row.mean_abs_shap)}
                         for row in shap_importance.itertuples(index=False)],
        destination=reports / "interactive_charts.json",
    )
    config["model_version"] = card["model_version"]
    config["final_test_metrics"] = final_metrics
    config["test_confidence_intervals"] = ci
    (reports / "research_experiment.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    model_card = [
        "# Model card", "", f"Selected pipeline: **{selected}**", f"Version: {card['model_version']}",
        f"Threshold: {threshold:.4f} (selection feasible: {feasible})", "", "## Test result", "",
        "| Metric | Result |", "|---|---:|",
    ] + [f"| {k} | {v} |" for k, v in final_metrics.items()]
    model_card += ["", "95% stratified bootstrap intervals are in reports/test_bootstrap_ci.csv. They condition on the one test split and exclude training or model-selection uncertainty.",
                   "", "## Intended use and limitations", "", card["intended_use"],
                   "The nominal holdout was examined in prior repository threshold/model exploration and is therefore not an untouched independent test. Its results are descriptive only; no independent external validation or clinical calibration was performed. The dataset has 768 historical records from a narrow population. Its outcome is not a prospective diagnosis; glucose feature timing is not sufficiently documented to claim future prediction.",
                   "A threshold is an engineering operating point for this benchmark, not a clinical decision threshold.", ""]
    model_card_path = Path(args.model_card)
    model_card_path.parent.mkdir(parents=True, exist_ok=True)
    model_card_path.write_text("\n".join(model_card), encoding="utf-8")
    print(f"Final test {selected} at {threshold:.4f}: recall={final_metrics['recall']:.3f}, "
          f"precision={final_metrics['precision']:.3f}, ROC-AUC={final_metrics['roc_auc']:.3f}, "
          f"FNR={final_metrics['false_negative_rate']:.3f}; saved version {card['model_version']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
