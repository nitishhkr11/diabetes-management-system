"""Experiments that turn opinions into measurements.

    python scripts/experiments.py            # full run (about 4-6 minutes)
    python scripts/experiments.py --quick    # few repeats, for a smoke test
    python scripts/experiments.py --only A,B # run some experiments only

A  STABILITY  the same pipeline on 100 different random 80:20 splits:
               how much of one split's score is luck?
B  LEAKAGE    reproduce the classic mistakes one at a time and measure how much
               each one inflates the score compared with the correct procedure.
C  ZERO RULE  does "0 means missing + median" actually help? (design evidence)
D  EXTREMES   what do the saved models do with unusual or impossible inputs?

Every number quoted in the written guide comes from the CSV files written here.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.impute import KNNImputer, SimpleImputer  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from src import config as C  # noqa: E402
from src import modeling as M  # noqa: E402
from src import plots as P  # noqa: E402
from src.data_validation import load_dataset  # noqa: E402
from src.leaky_recipes import (class_conditional_fill, enlarged_copy, global_prepare,  # noqa: E402
                               oversample_before_split)
from src.predict import ArtifactError, load_artifacts, predict_one  # noqa: E402
from src.preprocessing import ZeroToNaN, build_pipeline, split_data  # noqa: E402

METRICS = ["roc_auc", "accuracy", "precision", "recall", "f1", "brier"]
OUT = C.EXPERIMENTS_DIR


def say(msg=""):
    print(msg, flush=True)


def summarise(runs: pd.DataFrame, by: list, metrics=METRICS) -> pd.DataFrame:
    """mean, SD, 2.5 / 50 / 97.5 percentiles, min and max over the repeats."""
    long = runs.melt(id_vars=by + ["seed"], value_vars=metrics, var_name="metric")
    g = long.groupby(by + ["metric"])["value"]
    out = g.agg(mean="mean", sd="std", lo=lambda s: s.quantile(0.025), median="median",
                hi=lambda s: s.quantile(0.975), min="min", max="max").reset_index()
    return out


# =========================================================================== A
def experiment_stability(df, seeds):
    say(f"[A] Stability: {len(seeds)} random 80:20 splits x 3 models")
    frames = []
    for k, seed in enumerate(seeds):
        Xtr, Xte, ytr, yte = split_data(df, random_state=seed)
        table = M.evaluate_models(M.fit_models(Xtr, ytr), Xte, yte)
        table.insert(0, "seed", seed)
        frames.append(table)
        if (k + 1) % 25 == 0:
            say(f"      {k + 1}/{len(seeds)} splits done")
    runs = pd.concat(frames, ignore_index=True)
    runs.to_csv(OUT / "stability_runs.csv", index=False)
    summary = summarise(runs, ["model"])
    summary.to_csv(OUT / "stability_summary.csv", index=False)

    rows = []
    for model, sub in runs.groupby("model"):
        for metric, goal in C.PROJECT_TARGETS.items():
            rows.append({"model": model, "metric": metric, "target": goal,
                         "share_of_splits_meeting_target": float((sub[metric] >= goal).mean()),
                         "best_value_in_any_split": float(sub[metric].max())})
    pd.DataFrame(rows).to_csv(OUT / "stability_targets.csv", index=False)

    wide = runs.pivot(index="seed", columns="model", values="roc_auc")
    rows = []
    for a, b in (("Random Forest", "Logistic Regression"), ("Logistic Regression", "Gaussian Naive Bayes"),
                 ("Random Forest", "Gaussian Naive Bayes")):
        d = wide[a] - wide[b]
        rows.append({"model_a": a, "model_b": b, "metric": "roc_auc", "mean_difference_a_minus_b": d.mean(),
                     "sd_difference": d.std(), "share_of_splits_a_better": float((d > 0).mean()),
                     "share_within_tie_tolerance": float((d.abs() <= C.TIE_TOLERANCE).mean())})
    pd.DataFrame(rows).to_csv(OUT / "stability_paired.csv", index=False)

    rows = []
    for metric in ("roc_auc", "accuracy"):
        w = runs.pivot(index="seed", columns="model", values=metric)
        rows.append({"metric": metric, "mean_of_best_of_three_per_split": w.max(axis=1).mean(),
                     **{f"mean_{m}": w[m].mean() for m in w.columns}})
    pd.DataFrame(rows).to_csv(OUT / "winners_curse.csv", index=False)

    picks = []
    for _, sub in runs.groupby("seed"):
        picks.append(M.select_best_model(sub.rename(columns={m: f"{m}_mean" for m in ("roc_auc", "f1", "accuracy")}))[0])
    counts = pd.Series(picks).value_counts().rename_axis("model").reset_index(name="splits_where_rule_picks_it")
    counts.to_csv(OUT / "stability_pick_counts.csv", index=False)

    keep = ["roc_auc", "accuracy", "f1", "recall"]
    P.save(P.plot_interval_summary(summary, keep, f"Test-part scores over {len(seeds)} random splits "
                                   "(dot = median, line = middle 95% of splits)"),
           C.FIGURES_DIR / "exp_stability_intervals.png")

    say("      mean (SD) [2.5% .. 97.5%] over splits:")
    for model in C.MODEL_ORDER:
        s = summary[summary.model == model].set_index("metric")
        say(f"      {model:22s} " + "  ".join(
            f"{m}={s.loc[m, 'mean']:.3f} ({s.loc[m, 'sd']:.3f}) [{s.loc[m, 'lo']:.3f}..{s.loc[m, 'hi']:.3f}]"
            for m in ("roc_auc", "accuracy", "f1", "recall")))
    say("      Best value in ANY split vs the brief's targets:")
    say(pd.read_csv(OUT / "stability_targets.csv").round(3).to_string(index=False))
    say("      Which model the selection rule picks when applied to the TEST scores of each split:")
    say(counts.to_string(index=False))
    say("      Paired AUC differences:")
    say(pd.read_csv(OUT / "stability_paired.csv").round(3).to_string(index=False))
    say("      Winner's curse (best-of-three per split vs each model on average):")
    say(pd.read_csv(OUT / "winners_curse.csv").round(4).to_string(index=False))
    return runs


# =========================================================================== B
SCENARIO_LABELS = {
    "correct": "Correct procedure",
    "global_impute_scale": "Impute + scale on all rows first",
    "class_conditional_impute": "Fill gaps with same-class median",
    "oversample_before_split": "Oversample before splitting",
    "duplicated_rows_lookalike": "Enlarged copy with repeated rows",
    "test_set_threshold_tuning": "Threshold tuned on the test part",
}


def build(kind, model):
    if kind == "standard":
        return build_pipeline(model)
    if kind == "scale_only":                       # data were imputed earlier; scaling stays in the pipeline
        return Pipeline([("scale", StandardScaler()), ("model", model)])
    return Pipeline([("model", model)])           # data were already imputed AND scaled before the split


def run_scenario(scenario, df, seed):
    data, kind, tune = df, "standard", False
    if scenario == "class_conditional_impute":
        data, kind = class_conditional_fill(df), "scale_only"
    elif scenario == "global_impute_scale":
        data, kind = global_prepare(df), "model_only"
    elif scenario == "oversample_before_split":
        data = oversample_before_split(df, seed)
    elif scenario == "duplicated_rows_lookalike":
        data = enlarged_copy(df, seed)
    elif scenario == "test_set_threshold_tuning":
        tune = True
    Xtr, Xte, ytr, yte = split_data(data, random_state=seed)
    rows = []
    for name, est in M.get_models().items():
        proba = build(kind, est).fit(Xtr, ytr).predict_proba(Xte)[:, 1]
        thr = C.DECISION_THRESHOLD
        if tune:                                    # cheating: choose the threshold by looking at the test part
            grid = np.round(np.arange(0.05, 0.951, 0.01), 2)
            truth = np.asarray(yte)
            thr = float(grid[int(np.argmax([((proba >= t).astype(int) == truth).mean() for t in grid]))])
        m = M.compute_metrics(yte, proba, thr)
        rows.append({"scenario": scenario, "seed": seed, "model": name, "threshold": thr,
                     **{k: m[k] for k in METRICS}})
    return rows


def experiment_leakage(df, seeds):
    say(f"[B] Leakage: {len(SCENARIO_LABELS)} procedures x {len(seeds)} splits x 3 models")
    rows = []
    for k, seed in enumerate(seeds):
        for scenario in SCENARIO_LABELS:
            rows += run_scenario(scenario, df, seed)
        if (k + 1) % 5 == 0:
            say(f"      {k + 1}/{len(seeds)} splits done")
    runs = pd.DataFrame(rows)
    runs.to_csv(OUT / "leakage_runs.csv", index=False)
    summary = summarise(runs, ["scenario", "model"])
    summary.to_csv(OUT / "leakage_summary.csv", index=False)

    base = summary[summary.scenario == "correct"].set_index(["model", "metric"])["mean"]
    infl = summary.copy()
    infl["correct_mean"] = [base[(m, k)] for m, k in zip(infl.model, infl.metric)]
    infl["inflation"] = infl["mean"] - infl["correct_mean"]
    infl.to_csv(OUT / "leakage_inflation.csv", index=False)

    order = list(SCENARIO_LABELS)
    P.save(P.plot_scenarios(summary[summary.metric == "roc_auc"], "Test ROC-AUC under each procedure "
                            f"(mean of {len(seeds)} splits, whiskers = 1 SD)", order, SCENARIO_LABELS,
                            reference=C.PROJECT_TARGETS["roc_auc"], reference_label="project target 0.95"),
           C.FIGURES_DIR / "exp_leakage_auc.png")
    P.save(P.plot_scenarios(summary[summary.metric == "accuracy"], "Test accuracy under each procedure "
                            f"(mean of {len(seeds)} splits, whiskers = 1 SD)", order, SCENARIO_LABELS,
                            xlabel="Accuracy on the test part", reference=C.PROJECT_TARGETS["accuracy"],
                            reference_label="project target 0.96"),
           C.FIGURES_DIR / "exp_leakage_accuracy.png")

    for metric in ("roc_auc", "accuracy", "recall"):
        pivot = summary[summary.metric == metric].pivot(index="scenario", columns="model", values="mean")
        pivot = pivot.loc[order, C.MODEL_ORDER]
        say(f"      mean test {metric}:")
        say(pivot.round(3).to_string())
    return runs


# =========================================================================== C
ZERO_VARIANTS = {
    "project_median": "Project rule: 0 -> missing, median fill",
    "mean": "0 -> missing, MEAN fill",
    "knn": "0 -> missing, KNN fill (k=5)",
    "indicator": "Median fill + 'was missing' flags",
    "drop_insulin_skin": "Drop Insulin + SkinThickness columns",
    "none": "Do nothing (keep the zeros)",
}


def zero_variant(name, model):
    zero = ZeroToNaN(C.ZERO_AS_MISSING)
    if name == "project_median":
        return build_pipeline(model)
    if name == "mean":
        return Pipeline([("zero", zero), ("impute", SimpleImputer(strategy="mean")),
                         ("scale", StandardScaler()), ("model", model)])
    if name == "knn":
        return Pipeline([("zero", zero), ("scale", StandardScaler()),
                         ("impute", KNNImputer(n_neighbors=5)), ("model", model)])
    if name == "indicator":
        return Pipeline([("zero", zero), ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                         ("scale", StandardScaler()), ("model", model)])
    if name == "drop_insulin_skin":
        keep = [f for f in C.FEATURES if f not in ("Insulin", "SkinThickness")]
        return Pipeline([("zero", zero), ("keep", ColumnTransformer([("keep", "passthrough", keep)])),
                         ("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()),
                         ("model", model)])
    return Pipeline([("scale", StandardScaler()), ("model", model)])      # "none"


def experiment_zero_rule(df, seeds):
    say(f"[C] Zero-handling choices: {len(ZERO_VARIANTS)} variants x {len(seeds)} splits x 3 models")
    rows = []
    for k, seed in enumerate(seeds):
        Xtr, Xte, ytr, yte = split_data(df, random_state=seed)
        for variant in ZERO_VARIANTS:
            for name, est in M.get_models().items():
                proba = zero_variant(variant, est).fit(Xtr, ytr).predict_proba(Xte)[:, 1]
                m = M.compute_metrics(yte, proba)
                rows.append({"scenario": variant, "seed": seed, "model": name, **{q: m[q] for q in METRICS}})
        if (k + 1) % 10 == 0:
            say(f"      {k + 1}/{len(seeds)} splits done")
    runs = pd.DataFrame(rows)
    runs.to_csv(OUT / "zero_rule_runs.csv", index=False)
    summary = summarise(runs, ["scenario", "model"])
    summary.to_csv(OUT / "zero_rule_summary.csv", index=False)
    P.save(P.plot_scenarios(summary[summary.metric == "roc_auc"],
                            f"Test ROC-AUC for different ways of handling the zeros ({len(seeds)} splits)",
                            list(ZERO_VARIANTS), ZERO_VARIANTS), C.FIGURES_DIR / "exp_zero_rule_auc.png")
    for metric in ("roc_auc", "accuracy"):
        pivot = summary[summary.metric == metric].pivot(index="scenario", columns="model", values="mean")
        say(f"      mean test {metric}:")
        say(pivot.loc[list(ZERO_VARIANTS), C.MODEL_ORDER].round(3).to_string())
    return runs


# =========================================================================== D
def experiment_extremes():
    say("[D] Unusual and impossible inputs (uses the saved models)")
    try:
        art = load_artifacts()
    except ArtifactError as exc:
        say(f"      skipped: {exc}")
        return None
    prof = art.card["profile"]
    typical = {f: prof[f]["median"] for f in C.FEATURES}
    low = dict(Pregnancies=0, Glucose=85, BloodPressure=68, SkinThickness=20, Insulin=70, BMI=22,
               DiabetesPedigreeFunction=0.20, Age=24)
    high = dict(Pregnancies=8, Glucose=180, BloodPressure=80, SkinThickness=35, Insulin=200, BMI=38,
                DiabetesPedigreeFunction=0.90, Age=52)
    cases = [
        ("Typical (training medians)", typical),
        ("Lower-risk profile", low),
        ("Higher-risk profile", high),
        ("Only the 3 required fields known", dict(Pregnancies=2, Glucose=0, BloodPressure=0, SkinThickness=0,
                                                   Insulin=0, BMI=0, DiabetesPedigreeFunction=0.4, Age=35)),
        ("Glucose 400", {**typical, "Glucose": 400}),
        ("BMI 70", {**typical, "BMI": 70}),
        ("Age 90", {**typical, "Age": 90}),
        ("Glucose 30", {**typical, "Glucose": 30}),
        ("Age 15", {**typical, "Age": 15}),
        ("BMI -5", {**typical, "BMI": -5}),
        ("Age missing", {**typical, "Age": None}),
    ]
    rows = []
    for label, raw in cases:
        res = predict_one(art, raw, explain=False)
        row = {"case": label, "accepted": res["ok"], "errors": " | ".join(res["errors"]),
               "warnings": " | ".join(res["warnings"])}
        for name in C.MODEL_ORDER:
            row[name] = res["all_models"][name] if res["ok"] else np.nan
        rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "extreme_inputs.csv", index=False)
    say(table[["case", "accepted"] + C.MODEL_ORDER].round(3).to_string(index=False))

    sweep_rows = []
    for g in range(50, 301, 5):
        row = pd.DataFrame([{**typical, "Glucose": float(g)}])[C.FEATURES]
        for name, pipe in art.pipelines.items():
            sweep_rows.append({"model": name, "Glucose": g, "probability": float(pipe.predict_proba(row)[0, 1])})
    sweep = pd.DataFrame(sweep_rows)
    sweep.to_csv(OUT / "glucose_sweep.csv", index=False)
    P.save(P.plot_sweep(sweep, "Glucose", prof["Glucose"]["max"],
                        "Predicted probability while only Glucose changes"), C.FIGURES_DIR / "exp_glucose_sweep.png")
    return table


# ========================================================================= main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true", help="few repeats (smoke test)")
    ap.add_argument("--only", default="A,B,C,D", help="comma-separated experiment letters")
    args = ap.parse_args(argv)
    want = {x.strip().upper() for x in args.only.split(",")}
    OUT.mkdir(parents=True, exist_ok=True)
    C.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    df = load_dataset()
    t0 = time.time()
    n_a, n_b, n_c = (8, 4, 4) if args.quick else (100, 20, 30)
    if "A" in want:
        experiment_stability(df, range(n_a))
    if "B" in want:
        experiment_leakage(df, range(n_b))
    if "C" in want:
        experiment_zero_rule(df, range(n_c))
    if "D" in want:
        experiment_extremes()
    say(f"Done in {time.time() - t0:.0f} s. Tables: {OUT}  Figures: {C.FIGURES_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
