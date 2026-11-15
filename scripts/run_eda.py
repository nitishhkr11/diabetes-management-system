"""Exploratory data analysis: what is in the file, and what is wrong with it?

    python scripts/run_eda.py

Writes tables to reports/ and pictures to reports/figures/. Nothing here is used
for training; it only helps you understand (and defend) the cleaning rules.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import pandas as pd  # noqa: E402
from scipy.stats import fisher_exact  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

from src import config as C  # noqa: E402
from src import plots as P  # noqa: E402
from src.data_validation import load_dataset  # noqa: E402


def main() -> int:
    df = load_dataset()
    y = df[C.TARGET]
    clean = df.copy()
    for col in C.ZERO_AS_MISSING:
        clean[col] = clean[col].where(clean[col] != 0)

    print(f"Rows: {len(df)}   positives: {int(y.sum())} ({y.mean():.1%})   negatives: {int((1 - y).sum())}")

    # 1. one row per feature: how complete, how spread out, how well it separates the classes alone
    rows = []
    for feat in C.FEATURES:
        x = clean[feat]
        ok = x.notna()
        pos, neg = x[ok & (y == 1)], x[ok & (y == 0)]
        pooled_sd = (((len(pos) - 1) * pos.var() + (len(neg) - 1) * neg.var()) / (len(pos) + len(neg) - 2)) ** 0.5
        rows.append({
            "feature": feat,
            "n_zero_in_file": int((df[feat] == 0).sum()),
            "zero_means_missing": feat in C.ZERO_AS_MISSING,
            "n_usable": int(ok.sum()),
            "mean": x.mean(), "sd": x.std(), "median": x.median(), "min": x.min(), "max": x.max(),
            "mean_if_no_diabetes": neg.mean(), "mean_if_diabetes": pos.mean(),
            "cohens_d": (pos.mean() - neg.mean()) / pooled_sd,
            "single_feature_auc": roc_auc_score(y[ok], x[ok]),
        })
    summary = pd.DataFrame(rows)
    summary.to_csv(C.REPORTS_DIR / "eda_summary.csv", index=False)
    show = summary[["feature", "n_zero_in_file", "n_usable", "median", "mean_if_no_diabetes",
                    "mean_if_diabetes", "cohens_d", "single_feature_auc"]]
    print("\nPer-feature summary (zeros in the five 'impossible zero' columns treated as missing):")
    print(show.round(3).to_string(index=False))

    # 2. is the 'missing' status itself related to the outcome? (it would be a data-collection artefact)
    rows = []
    for feat in C.ZERO_AS_MISSING:
        is_zero = df[feat] == 0
        a, b = int(y[is_zero].sum()), int((~y[is_zero].astype(bool)).sum())
        c, d = int(y[~is_zero].sum()), int((~y[~is_zero].astype(bool)).sum())
        _, p = fisher_exact([[a, b], [c, d]])
        rows.append({"feature": feat, "rows_with_zero": int(is_zero.sum()),
                     "share_diabetic_if_zero": y[is_zero].mean(), "share_diabetic_if_measured": y[~is_zero].mean(),
                     "fisher_p": p})
    miss = pd.DataFrame(rows)
    miss.to_csv(C.REPORTS_DIR / "eda_missingness_vs_outcome.csv", index=False)
    print("\nDoes 'being missing' tell you anything about the outcome?")
    print(miss.round(4).to_string(index=False))

    # 3. how many rows are incomplete?
    n_missing_per_row = clean[C.ZERO_AS_MISSING].isna().sum(axis=1)
    print("\nRows by number of unknown measurements (of 5):")
    print(n_missing_per_row.value_counts().sort_index().to_string())
    print(f"Rows with all five measured (complete cases): {int((n_missing_per_row == 0).sum())}")

    # 4. pictures
    P.save(P.plot_zero_counts(df), C.FIGURES_DIR / "eda_zero_counts.png")
    P.save(P.plot_feature_distributions(df), C.FIGURES_DIR / "eda_distributions.png")
    P.save(P.plot_correlation(df), C.FIGURES_DIR / "eda_correlation.png")
    print(f"\nSaved tables to {C.REPORTS_DIR} and pictures to {C.FIGURES_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
