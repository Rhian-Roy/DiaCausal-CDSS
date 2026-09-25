"""Step (c): cross-fitted multinomial propensity model and the overlap check.

Plain English: the propensity score is "how likely was a patient like this to get each of
the three drugs?". We learn it with multinomial logistic regression (one model, three
probabilities that add up to 1).

Cross-fitting: we split the cohort into 5 parts; each part's scores come from a model
trained on the other 4. So no patient is scored by a model that has already seen them,
which stops over-fitting from making the correction look better than it is.

Overlap: if this patient's probability for a drug is below 0.05 (params.yaml), almost no
similar patient got that drug, so a fair comparison is impossible and we say
"insufficient evidence" instead of guessing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from diacausal_engine import ARMS
from diacausal_engine.config import Params
from diacausal_engine.dag import load_dag


def propensity_model() -> Pipeline:
    """Standardise, then multinomial logistic regression (lbfgs fits all 3 arms jointly)."""
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000, C=1.0))


def _proba(model: Pipeline, X: np.ndarray) -> np.ndarray:
    """(n, 3) probabilities in ARMS order, even if a fold lacked an arm."""
    out = np.zeros((len(X), len(ARMS)))
    out[:, model.classes_] = model.predict_proba(X)
    return out


def crossfit_propensity(X: np.ndarray, T: np.ndarray, folds: int, seed: int) -> np.ndarray:
    """Out-of-fold propensity scores, (n, 3). Row i never saw patient i in training."""
    oof = np.zeros((len(X), len(ARMS)))
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    for train, test in splitter.split(X, T):
        model = propensity_model().fit(X[train], T[train])
        oof[test] = _proba(model, X[test])
    return oof


def fit_full(X: np.ndarray, T: np.ndarray) -> Pipeline:
    """One model on the whole cohort, used to score a NEW patient."""
    return propensity_model().fit(X, T)


def predict(model: Pipeline, X: np.ndarray) -> np.ndarray:
    return _proba(model, np.atleast_2d(X))


def clip(p: np.ndarray, low: float) -> np.ndarray:
    """Keep weights finite: no probability below `low` (params: engine.propensity_clip)."""
    q = np.clip(p, low, 1.0)
    return q / q.sum(axis=1, keepdims=True)


def overlap_check(p_row: np.ndarray, threshold: float) -> dict[str, bool]:
    """True = enough similar patients got this option; False = insufficient evidence."""
    p_row = np.asarray(p_row, dtype=float).ravel()
    return {arm: bool(p_row[j] >= threshold) for j, arm in enumerate(ARMS)}


def support_check(patient: dict, cohort: pd.DataFrame, params: Params) -> list[str]:
    """Reasons this patient is outside what the cohort covers (empty list = inside).

    Not a clinical rule: it only says "the model has never seen a patient like this",
    e.g. type 1 diabetes, or an eGFR lower than anyone in the cohort.
    """
    reasons: list[str] = []
    if patient.get("t1d") and not cohort["t1d"].any():
        reasons.append("type 1 diabetes: the cohort contains only type 2 diabetes")
    for col in load_dag(params).adjustment_set:
        if col not in patient:
            continue
        value = float(patient[col])
        values = cohort[col]
        if values.nunique() <= 2:
            if value not in set(values.astype(float)):
                reasons.append(f"{col} = {value:g}: no patient in the cohort has this value")
        elif value < values.min() or value > values.max():
            reasons.append(
                f"{col} = {value:g} is outside the cohort's range ({values.min():g} to {values.max():g})"
            )
    return reasons
