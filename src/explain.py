"""Patient-level and global explanations with SHAP.

SHAP gives every feature a number: how much it pushed THIS prediction up (+) or
down (-) compared with a baseline (the average prediction on background data).
The numbers always add up:   baseline + sum(contributions) = model output.

Units differ by model - this is a classic viva trap:
  * Random Forest + TreeExplainer  -> probability points
  * Gaussian NB  + exact explainer -> probability points
  * Logistic Regression + LinearExplainer -> log-odds
SHAP explains what the MODEL does. It does not prove that a feature CAUSES diabetes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from . import config as C


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


class PatientExplainer:
    def __init__(self, pipeline, background_raw: pd.DataFrame, max_background: int = 100,
                 seed: int = C.RANDOM_STATE):
        self.pipeline = pipeline
        self.prep = pipeline[:-1]          # zero->NaN, impute, scale (already fitted)
        self.show = pipeline[:2]           # zero->NaN, impute  (values in original units)
        self.model = pipeline[-1]
        bg = self.prep.transform(background_raw)
        if len(bg) > max_background:
            bg = bg.sample(max_background, random_state=seed)
        if isinstance(self.model, RandomForestClassifier):
            self.explainer = shap.TreeExplainer(self.model)
            self.units = "probability"
        elif isinstance(self.model, LogisticRegression):
            self.explainer = shap.LinearExplainer(self.model, bg)
            self.units = "log-odds"
        else:                               # Gaussian Naive Bayes (or any other model)
            columns = list(bg.columns)

            def f(a):
                return self.model.predict_proba(pd.DataFrame(a, columns=columns))[:, 1]

            self.explainer = shap.Explainer(f, shap.maskers.Independent(bg, max_samples=max_background))
            self.units = "probability"

    # -------------------------------------------------------------- raw values
    def shap_values(self, raw_rows: pd.DataFrame):
        """Return (values[n, 8], base[n], scaled_frame) for the POSITIVE class."""
        Z = self.prep.transform(raw_rows)
        ex = self.explainer(Z)
        values = np.asarray(ex.values)
        base = np.asarray(ex.base_values, dtype=float)
        if values.ndim == 3:                # tree models return one slice per class
            values = values[:, :, 1]
            base = base[:, 1]
        base = np.broadcast_to(base, (values.shape[0],)).astype(float)
        return values, base, Z

    def _model_output(self, Z: pd.DataFrame) -> np.ndarray:
        if self.units == "log-odds":
            return self.model.decision_function(Z)
        return self.model.predict_proba(Z)[:, 1]

    # ------------------------------------------------------------ one patient
    def explain_one(self, raw_row: pd.DataFrame) -> dict:
        values, base, Z = self.shap_values(raw_row)
        shown = self.show.transform(raw_row).iloc[0]
        contribs = []
        for j, feat in enumerate(C.FEATURES):
            raw_val = raw_row.iloc[0][feat]
            was_missing = bool(pd.isna(raw_val) or (feat in C.ZERO_AS_MISSING and raw_val == 0))
            contribs.append({"feature": feat, "value": float(shown[feat]),
                             "was_missing": was_missing, "contribution": float(values[0, j])})
        contribs.sort(key=lambda d: abs(d["contribution"]), reverse=True)
        output = float(base[0] + values[0].sum())
        model_out = float(self._model_output(Z)[0])
        probability = float(_sigmoid(output)) if self.units == "log-odds" else output
        return {"units": self.units, "base_value": float(base[0]), "output_value": output,
                "probability": probability, "contributions": contribs,
                "additivity_error": abs(output - model_out)}

    # ----------------------------------------------------------------- global
    def explanation(self, raw_rows: pd.DataFrame) -> shap.Explanation:
        """shap.Explanation in ORIGINAL units, ready for shap.plots.beeswarm / bar."""
        values, base, _ = self.shap_values(raw_rows)
        data = self.show.transform(raw_rows)[C.FEATURES].to_numpy()
        return shap.Explanation(values=values, base_values=base, data=data, feature_names=C.FEATURES)

    def global_importance(self, raw_rows: pd.DataFrame) -> pd.DataFrame:
        values, _, _ = self.shap_values(raw_rows)
        imp = pd.DataFrame({"feature": C.FEATURES, "mean_abs_shap": np.abs(values).mean(axis=0)})
        return imp.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
