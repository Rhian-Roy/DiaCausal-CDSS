"""Fit every model of the causal pipeline on one observed dataset (shared by the
benchmark, the demo and the API, so they can never disagree)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from diacausal_engine.cohort import features, observed_view, treatment_index
from diacausal_engine.config import Params
from diacausal_engine.estimators import DRLearner, aipw_scores, crossfit_outcomes
from diacausal_engine.propensity import clip, crossfit_propensity, fit_full


@dataclass
class Fitted:
    X: np.ndarray
    T: np.ndarray
    Y: np.ndarray
    e: np.ndarray  # cross-fitted, clipped propensities (n, 3)
    mu: np.ndarray  # cross-fitted outcome predictions (n, 3)
    phi: np.ndarray  # AIPW scores (n, 3)
    propensity: Pipeline  # full-data model for new patients
    dr: DRLearner
    observed: pd.DataFrame


def fit_all(params: Params, cohort: pd.DataFrame, seed: int) -> Fitted:
    obs = observed_view(cohort)
    X, T, Y = features(params, obs), treatment_index(obs), obs["y"].to_numpy(float)
    folds = int(params.get("engine.crossfit_folds"))
    e = clip(crossfit_propensity(X, T, folds, seed), params.get("engine.propensity_clip"))
    mu = crossfit_outcomes(X, T, Y, folds, params.group("engine.outcome_model"), seed)
    phi = aipw_scores(Y, T, e, mu)
    return Fitted(X, T, Y, e, mu, phi, fit_full(X, T), DRLearner().fit(X, phi), obs)
