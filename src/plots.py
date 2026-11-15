"""Plot helpers (matplotlib).

Design rules used here (so every figure in the report looks like one family):
  * each MODEL keeps the same colour in every chart (blue / orange / aqua);
  * thin marks, light solid grid, no 3-D, no dual axes;
  * red = pushes the score UP, blue = pushes it DOWN (always also shown as +/- text);
  * every chart has a table twin in reports/*.csv, so colour is never the only channel.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve

from . import config as C

SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
MODEL_COLORS = {"Logistic Regression": "#2a78d6", "Gaussian Naive Bayes": "#eb6834", "Random Forest": "#1baf7a"}
CLASS_COLORS = {0: "#2a78d6", 1: "#eb6834"}
UP, DOWN = "#e34948", "#2a78d6"
SEQ = LinearSegmentedColormap.from_list("seq", ["#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b"])
DIV = LinearSegmentedColormap.from_list("div", ["#2a78d6", "#f0efec", "#e34948"])


def apply_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "axes.labelcolor": INK2,
        "axes.titlecolor": INK, "axes.titleweight": "bold", "axes.titlesize": 11,
        "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "grid.linestyle": "-",
        "axes.axisbelow": True, "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.labelcolor": INK2, "ytick.labelcolor": INK2, "text.color": INK,
        "font.size": 9, "legend.frameon": False, "lines.linewidth": 1.8, "lines.markersize": 6,
    })


apply_style()


def save(fig, path, dpi: int = 150) -> None:
    from pathlib import Path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------ evaluation
def plot_roc(y_true, probas: dict, title: str = "ROC curves on the test set"):
    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    ax.plot([0, 1], [0, 1], color=MUTED, lw=1, label="chance (AUC 0.500)")
    for name, p in probas.items():
        fpr, tpr, _ = roc_curve(y_true, p)
        ax.plot(fpr, tpr, color=MODEL_COLORS.get(name, INK), label=f"{name} (AUC {roc_auc_score(y_true, p):.3f})")
    ax.set(xlim=(0, 1), ylim=(0, 1.01), xlabel="False positive rate (1 - specificity)",
           ylabel="True positive rate (recall)", title=title)
    ax.set_aspect("equal")
    ax.legend(loc="lower right")
    return fig


def plot_confusion(cm, title: str, ax=None):
    """cm = [[tn, fp], [fn, tp]]"""
    cm = np.asarray(cm)
    own = ax is None
    if own:
        fig, ax = plt.subplots(figsize=(3.6, 3.3))
    else:
        fig = ax.figure
    ax.imshow(cm, cmap=SEQ, vmin=0, vmax=cm.sum(axis=1).max())
    ax.grid(False)
    total = cm.sum(axis=1, keepdims=True)
    for i in range(2):
        for j in range(2):
            dark = cm[i, j] > 0.5 * cm.sum(axis=1).max()
            ax.text(j, i, f"{cm[i, j]}\n({cm[i, j] / total[i, 0]:.0%} of row)", ha="center", va="center",
                    color="white" if dark else INK, fontsize=9)
    ax.set_xticks([0, 1], ["Predicted:\nno diabetes", "Predicted:\ndiabetes"])
    ax.set_yticks([0, 1], ["Actual:\nno diabetes", "Actual:\ndiabetes"])
    ax.set_title(title, fontsize=10)
    for s in ax.spines.values():
        s.set_visible(False)
    return fig


def plot_confusion_panel(cms: dict, title: str = "Confusion matrices on the test set"):
    fig, axes = plt.subplots(1, len(cms), figsize=(3.5 * len(cms), 3.4))
    for ax, (name, cm) in zip(np.atleast_1d(axes), cms.items()):
        plot_confusion(cm, name, ax=ax)
    fig.suptitle(title, x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    return fig


def plot_cv_scores(cv_table: pd.DataFrame, metric: str = "roc_auc", title: str | None = None):
    """Dot = mean over the CV folds, line = +/- 1 standard deviation."""
    fig, ax = plt.subplots(figsize=(6.2, 2.4 + 0.2 * len(cv_table)))
    rows = list(cv_table.itertuples())[::-1]
    for i, r in enumerate(rows):
        mean, std = getattr(r, f"{metric}_mean"), getattr(r, f"{metric}_std")
        ax.plot([mean - std, mean + std], [i, i], color=MODEL_COLORS[r.model], lw=2)
        ax.plot(mean, i, "o", color=MODEL_COLORS[r.model], markersize=8, markeredgecolor=SURFACE, markeredgewidth=2)
        ax.text(mean + std + 0.006, i, f"{mean:.3f} +/- {std:.3f}", va="center", color=INK, fontsize=9)
    ax.set_yticks(range(len(rows)), [r.model for r in rows])
    ax.set(xlim=(0.5, 0.98), xlabel=f"{metric.replace('_', '-').upper()} (5-fold CV on the training part)",
           title=title or f"Cross-validated {metric.replace('_', '-').upper()}")
    ax.grid(axis="y", visible=False)
    return fig


def plot_calibration(y_true, probas: dict, n_bins: int = 5, title: str = "Calibration on the test set"):
    fig, ax = plt.subplots(figsize=(5.2, 4.6))
    ax.plot([0, 1], [0, 1], color=MUTED, lw=1, label="perfectly calibrated")
    for name, p in probas.items():
        frac, mean_pred = calibration_curve(y_true, p, n_bins=n_bins, strategy="quantile")
        ax.plot(mean_pred, frac, "o-", color=MODEL_COLORS.get(name, INK), markeredgecolor=SURFACE,
                markeredgewidth=1.5, markersize=7, label=f"{name} (Brier {brier_score_loss(y_true, p):.3f})")
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Mean predicted probability (per bin)",
           ylabel="Observed share with diabetes", title=title)
    ax.set_aspect("equal")
    ax.legend(loc="upper left", fontsize=8)
    return fig


def plot_threshold(table: pd.DataFrame, chosen: float, title: str):
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    series = [("recall", "#2a78d6", "Recall"), ("precision", "#eb6834", "Precision"), ("f1", "#1baf7a", "F1")]
    for col, colour, label in series:
        ax.plot(table["threshold"], table[col], color=colour, label=label)
        ax.text(table["threshold"].iloc[-1] + 0.01, table[col].iloc[-1], label, color=INK2, va="center", fontsize=8)
    ax.axvline(chosen, color=MUTED, lw=1)
    ax.text(chosen + 0.005, 1.0, f"threshold {chosen:.2f}", color=INK2, fontsize=8, va="top")
    ax.set(xlim=(table["threshold"].min(), table["threshold"].max() + 0.08), ylim=(0, 1.02),
           xlabel="Decision threshold on the predicted probability", ylabel="Score", title=title)
    ax.legend(loc="lower left", ncol=3)
    return fig


def plot_interval_summary(summary: pd.DataFrame, metrics: list, title: str):
    """summary has columns model, metric, median, lo, hi (one row per model x metric)."""
    fig, axes = plt.subplots(1, len(metrics), figsize=(3.7 * len(metrics), 2.8), sharey=True)
    for ax, metric in zip(np.atleast_1d(axes), metrics):
        sub = summary[summary.metric == metric].set_index("model").loc[list(MODEL_COLORS)][::-1]
        for i, (name, r) in enumerate(sub.iterrows()):
            ax.plot([r.lo, r.hi], [i, i], color=MODEL_COLORS[name], lw=2)
            ax.plot(r["median"], i, "o", color=MODEL_COLORS[name], markersize=8, markeredgecolor=SURFACE, markeredgewidth=2)
            ax.text(r.hi + 0.004, i, f"{r['median']:.3f}", va="center", fontsize=8, color=INK)
        ax.set_yticks(range(len(sub)), list(sub.index))
        ax.set_title(metric.replace("_", "-").upper(), fontsize=10)
        ax.grid(axis="y", visible=False)
    fig.suptitle(title, x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    return fig


def plot_scenarios(summary: pd.DataFrame, title: str, order: list, labels: dict | None = None,
                   xlabel: str = "ROC-AUC on the test part", reference: float | None = None,
                   reference_label: str = ""):
    """One row per scenario, three dots per row (one per model), whiskers = +/- 1 SD over repeats.

    summary needs the columns: scenario, model, mean, sd.
    """
    offsets = {"Logistic Regression": -0.22, "Gaussian Naive Bayes": 0.0, "Random Forest": 0.22}
    rows = order[::-1]
    fig, ax = plt.subplots(figsize=(7.6, 0.62 * len(rows) + 1.5))
    for i, scen in enumerate(rows):
        sub = summary[summary.scenario == scen].set_index("model")
        for model, off in offsets.items():
            r = sub.loc[model]
            ax.plot([r["mean"] - r["sd"], r["mean"] + r["sd"]], [i + off] * 2, color=MODEL_COLORS[model], lw=1.6)
            ax.plot(r["mean"], i + off, "o", color=MODEL_COLORS[model], markersize=6.5,
                    markeredgecolor=SURFACE, markeredgewidth=1.5)
            ax.text(r["mean"] + r["sd"] + 0.004, i + off, f"{r['mean']:.3f}", va="center", fontsize=7.5, color=INK2)
    ax.set_yticks(range(len(rows)), [(labels or {}).get(s, s) for s in rows])
    ax.set_ylim(-0.6, len(rows) - 0.4)
    if reference is not None:
        ax.axvline(reference, color=MUTED, lw=1, ls="--")
        ax.text(reference - 0.004, len(rows) - 0.45, reference_label, ha="right", va="top", fontsize=8, color=INK2)
    ax.set(xlabel=xlabel, title=title)
    ax.grid(axis="y", visible=False)
    handles = [plt.Line2D([0], [0], marker="o", color=MODEL_COLORS[m], lw=1.6, markeredgecolor=SURFACE, label=m)
               for m in offsets]
    fig.legend(handles=handles, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.04), fontsize=8.5)
    return fig


def plot_sweep(sweep: pd.DataFrame, feature: str, train_max: float, title: str):
    """Predicted probability of every model while ONE feature is changed (others fixed)."""
    fig, ax = plt.subplots(figsize=(6.4, 3.9))
    for model, g in sweep.groupby("model", sort=False):
        ax.plot(g[feature], g["probability"], color=MODEL_COLORS.get(model, INK), label=model)
    ax.axvline(train_max, color=MUTED, lw=1, ls="--")
    ax.text(train_max + 3, 0.03, f"largest {feature} value\nseen in training ({train_max:g})", fontsize=8, color=INK2)
    ax.set(ylim=(0, 1.02), xlabel=feature, ylabel="Predicted probability", title=title)
    ax.legend(loc="upper left")
    return fig


# --------------------------------------------------------------------- SHAP
def plot_contributions(expl: dict, title: str | None = None):
    """Signed horizontal bars: why THIS patient got THIS score."""
    items = expl["contributions"][::-1]            # smallest at the bottom
    units = "probability points" if expl["units"] == "probability" else "log-odds"
    fig, ax = plt.subplots(figsize=(6.4, 0.45 * len(items) + 1.6))
    ys = np.arange(len(items))
    vals = [d["contribution"] for d in items]
    ax.barh(ys, vals, color=[UP if v > 0 else DOWN for v in vals], height=0.55)
    span = max(abs(v) for v in vals) or 1.0
    for y, d in zip(ys, items):
        v = d["contribution"]
        text = "0.000" if abs(v) < 0.0005 else f"{v:+.3f}"      # avoid a confusing "-0.000"
        ax.text(v + (0.02 * span if v >= 0 else -0.02 * span), y, text, va="center",
                ha="left" if v >= 0 else "right", fontsize=8.5, color=INK)
    labels = [f"{d['feature']} = {d['value']:.3g}" + (" (filled in)" if d["was_missing"] else "") for d in items]
    ax.set_yticks(ys, labels)
    ax.axvline(0, color=AXIS, lw=1)
    ax.set_xlim(-1.35 * span, 1.35 * span)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel(f"Contribution to the score ({units}); red raises it, blue lowers it")
    base, out = expl["base_value"], expl["output_value"]
    ax.set_title(title or (f"Baseline {base:.2f}  ->  this patient {out:.2f}  ({units})"))
    return fig


def plot_global_importance(imp: pd.DataFrame, title: str = "Average impact of each feature (mean |SHAP|)",
                           units: str = "model-output units"):
    d = imp.iloc[::-1]
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.barh(d["feature"], d["mean_abs_shap"], color="#2a78d6", height=0.55)
    for y, v in enumerate(d["mean_abs_shap"]):
        ax.text(v + 0.002, y, f"{v:.3f}", va="center", fontsize=8.5)
    ax.set(xlabel=f"mean |SHAP value| on the test set ({units})", title=title)
    ax.grid(axis="y", visible=False)
    return fig


# ---------------------------------------------------------------------- EDA
def plot_zero_counts(df: pd.DataFrame):
    cols = ["Pregnancies"] + C.ZERO_AS_MISSING
    counts = [(c, int((df[c] == 0).sum())) for c in cols]
    counts.sort(key=lambda t: t[1])
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    colors = [MUTED if c == "Pregnancies" else "#2a78d6" for c, _ in counts]
    ax.barh([c for c, _ in counts], [n for _, n in counts], color=colors, height=0.55)
    for y, (c, n) in enumerate(counts):
        tag = "valid zero (never pregnant)" if c == "Pregnancies" else "impossible -> missing"
        ax.text(n + 4, y, f"{n}  ({n / len(df):.1%})  {tag}", va="center", fontsize=8.5)
    ax.set(xlim=(0, 640), xlabel="rows containing 0", title="Zeros in the raw data")
    ax.grid(axis="y", visible=False)
    return fig


def plot_feature_distributions(df: pd.DataFrame):
    """Histograms by class AFTER treating the impossible zeros as missing."""
    clean = df.copy()
    for c in C.ZERO_AS_MISSING:
        clean[c] = clean[c].where(clean[c] != 0)
    fig, axes = plt.subplots(2, 4, figsize=(12, 5.2))
    for ax, feat in zip(axes.ravel(), C.FEATURES):
        bins = np.histogram_bin_edges(clean[feat].dropna(), bins=20)
        for cls, label in ((0, "no diabetes"), (1, "diabetes")):
            ax.hist(clean.loc[clean[C.TARGET] == cls, feat].dropna(), bins=bins, density=True,
                    color=CLASS_COLORS[cls], alpha=0.55, label=label, edgecolor=SURFACE, linewidth=0.5)
        ax.set_title(feat, fontsize=9.5)
        ax.set_yticks([])
        ax.grid(axis="y", visible=False)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=2)
    fig.suptitle("Feature distributions by outcome (zeros treated as missing)", x=0.01, ha="left",
                 fontsize=11, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return fig


def plot_correlation(df: pd.DataFrame):
    clean = df.copy()
    for c in C.ZERO_AS_MISSING:
        clean[c] = clean[c].where(clean[c] != 0)
    corr = clean.corr(numeric_only=True)
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(corr.values, cmap=DIV, vmin=-1, vmax=1)
    ax.grid(False)
    ax.set_xticks(range(len(corr)), corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr)), corr.columns)
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=7,
                    color="white" if abs(corr.values[i, j]) > 0.6 else INK)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.colorbar(im, ax=ax, shrink=0.75, label="Pearson correlation")
    ax.set_title("Correlation (zeros treated as missing)")
    return fig
