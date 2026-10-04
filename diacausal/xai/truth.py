"""The synthetic generator's true effect modifiers, DERIVED from data/params.yaml (never typed here).

The true expected 6-month HbA1c change under option `a` is (diacausal/causal_inference/cohort.py, true_expected_outcomes)

    drift + rtm*(hba1c - c_h) + female_term + base_a + per_hba1c_a*(hba1c - c_h) + per_10_egfr_a*(egfr - c_e)/10
          + per_duration_year_a*(duration - c_d)

The drift, the regression-to-the-mean term and the sex term are the same for every option, so they CANCEL in a comparison.
What is left, option a minus option b, is linear in three features only: hba1c, egfr and duration_years. Every other
feature has a true effect-modification of exactly zero. (That is what makes this synthetic benchmark checkable; the paper
must not claim real-world effects are linear.)

Slopes are per ORIGINAL unit of the feature (HbA1c points per % of HbA1c, per mL/min/1.73m2 of eGFR, per year).
"""

from __future__ import annotations

import numpy as np

from diacausal.causal_inference.dag import load_dag
from diacausal.config import ARMS, CONTRASTS, Params

COMPARISONS = tuple(f"{a}-{b}" for a, b in CONTRASTS)
_OUTCOME = "generator.outcome"


def _arm_slopes(params: Params, arm: str) -> dict[str, float]:
    """Slope of E[Y(arm)|X] per original unit, for the features that enter the formula."""
    e = params.group(f"{_OUTCOME}.effects.{arm}")
    return {"hba1c": e["per_hba1c_pct"], "egfr": e["per_10_egfr"] / 10.0, "duration_years": e["per_duration_year"]}


def true_slopes(params: Params) -> dict[str, dict[str, float]]:
    """{comparison: {feature: true slope per original unit}} for every feature of the DAG's adjustment set
    (0.0 for a feature that does not modify the effect)."""
    features = load_dag(params).adjustment_set
    out = {}
    for a, b in CONTRASTS:
        sa, sb = _arm_slopes(params, a), _arm_slopes(params, b)
        out[f"{a}-{b}"] = {f: float(sa.get(f, 0.0) - sb.get(f, 0.0)) for f in features}
    return out


def modifiers(params: Params) -> dict[str, list[str]]:
    """{comparison: the features whose true slope is not zero}, in the order of the adjustment set."""
    return {c: [f for f, s in slopes.items() if s != 0.0] for c, slopes in true_slopes(params).items()}


def true_importance(params: Params, sd: dict[str, float]) -> dict[str, dict[str, float]]:
    """{comparison: {feature: |true slope| x SD of the feature}}: how much the true effect moves per SD of the feature."""
    return {c: {f: abs(s) * sd[f] for f, s in slopes.items()} for c, slopes in true_slopes(params).items()}


def true_effect(params: Params, mu_true: np.ndarray) -> dict[str, np.ndarray]:
    """{comparison: true patient-level effect} from the test cohort's true expected outcomes (n, 3)."""
    idx = {arm: j for j, arm in enumerate(ARMS)}
    return {f"{a}-{b}": mu_true[:, idx[a]] - mu_true[:, idx[b]] for a, b in CONTRASTS}
