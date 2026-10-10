"""Version C: exact SHAP on the causal engine's own estimate (docs/XAI_PLAN.md sections 3 and 6; plan section 7; P25).

The DR-learner's final stage is linear: the estimate of a comparison for a patient x is

    estimate_c(x) = beta_c[0] + sum_j beta_c[j+1] * (x_j - mean_j) / scale_j

with one column per feature and no interaction, so the exact Shapley value of feature j (with the cohort mean as the
reference) is the term itself:

    phi_cj(x) = slope_cj * (x_j - mean_j),    slope_cj = beta_c[j+1] / scale_j   (HbA1c points per original unit)
    base_c    = beta_c[0]                     (the estimate at the cohort mean = the cohort's average effect)
    base_c + sum_j phi_cj(x) = estimate_c(x)  exactly (checked to 1e-9 here, and by shap.LinearExplainer in tests/xai)

95% interval of a contribution, with no bootstrap: phi_cj = c_j * beta_c[j+1] with c_j = (x_j - mean_j) / scale_j a fixed number,
so its standard error is |c_j| * sqrt(V_c[j+1, j+1]) from the final stage's HC3 covariance V_c, and the interval is
phi_cj +/- z * that, with the engine's z (1.959964). Same assumptions as the engine's own interval: the cohort means and scales and
the earlier cross-fitted models are treated as fixed, and each interval is marginal (not joint over features).

A feature is a CLEAR driver when its interval excludes zero. Because c_j is fixed, that happens exactly when |beta_cj| > z * SE, so
the SET of clear features of a comparison is a property of the model, not of the patient; the patient decides their order. The
card shows up to `max_drivers` clear drivers (params.yaml `xai.max_drivers`), largest |phi| first, and never pads with unclear ones.

    explain_effect(dr, x, target, z)     -> EffectExplanation (base, estimate, a Contribution per feature)
    drivers(explanation, max_drivers)    -> the clear contributions to show, largest first
    driver_records(...)                  -> the same as DriverV1 rows for the API's card
    version C's metrics: diacausal/xai/cate_shap_benchmark.py (python -m diacausal.xai.cate_shap_benchmark [--quick])

DRIVERS, NEVER CAUSES: a driver says the estimate is larger or smaller for patients with that detail. Pure NumPy: no shap import
here (only the cross-check test uses shap), so the API, the website export and CI stay light.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from diacausal.config import ARMS, load_params
from diacausal.causal_inference.estimators import TARGETS
from diacausal.xai import truth

COMPARISONS = truth.COMPARISONS
COMPARATOR = "DPP4i"
CARD_COMPARISONS = tuple(f"{a}-{COMPARATOR}" for a in ARMS if a != COMPARATOR)  # the card explains each option against DPP-4i
ADDITIVITY_TOLERANCE = 1e-9


@dataclass(frozen=True)
class Contribution:
    feature: str
    value: float  # this patient's value
    mean: float  # the training cohort's mean (the reference point)
    slope_per_unit: float  # HbA1c points per original unit of the feature
    phi: float  # the SHAP value: slope_per_unit * (value - mean)
    se: float
    ci_low: float
    ci_high: float
    clear: bool  # the 95% interval of phi excludes zero


@dataclass(frozen=True)
class EffectExplanation:
    target: str
    base: float
    estimate: float
    contributions: list[Contribution] = field(default_factory=list)

    @property
    def additivity_error(self) -> float:
        return abs(self.base + sum(c.phi for c in self.contributions) - self.estimate)


def max_drivers(params=None) -> int:
    return int((params or load_params()).get("xai.max_drivers"))


def explain_effect(dr, x: Sequence[float], target: str, z: float, features: Sequence[str]) -> EffectExplanation:
    """Exact SHAP of one target of a fitted DRLearner (`mean_`, `scale_`, `beta_`, `cov_`) for one patient row `x` (the features in
    the order of `features`, the DAG's adjustment set). Raises if the contributions do not add up to the estimate within 1e-9."""
    k = TARGETS.index(target)
    x = np.asarray(x, float).ravel()
    c = (x - dr.mean_) / dr.scale_  # the standardised, centred value: a fixed number for this patient
    beta = dr.beta_[:, k]
    se_coef = np.sqrt(np.clip(np.diag(dr.cov_[k])[1:], 0.0, None))
    phi = c * beta[1:]
    se = np.abs(c) * se_coef
    estimate = float(np.r_[1.0, c] @ beta)
    contributions = [Contribution(feature=f, value=float(x[j]), mean=float(dr.mean_[j]), slope_per_unit=float(beta[j + 1] / dr.scale_[j]),
                                  phi=float(phi[j]), se=float(se[j]), ci_low=float(phi[j] - z * se[j]), ci_high=float(phi[j] + z * se[j]),
                                  clear=bool(abs(beta[j + 1]) > z * se_coef[j]))
                     for j, f in enumerate(features)]
    out = EffectExplanation(target=target, base=float(beta[0]), estimate=estimate, contributions=contributions)
    if out.additivity_error > ADDITIVITY_TOLERANCE:
        raise ArithmeticError(f"{target}: the contributions do not add up to the estimate")
    return out


def drivers(explanation: EffectExplanation, limit: int) -> list[Contribution]:
    """The clear contributions (interval excludes zero), largest |phi| first (ties: feature order), at most `limit`. A patient exactly
    at the cohort mean of a clear feature gets phi = 0 for it: that is not shown either (it says nothing about this patient)."""
    clear = [(i, c) for i, c in enumerate(explanation.contributions) if c.clear and c.phi != 0.0]
    return [c for _, c in sorted(clear, key=lambda ic: (-abs(ic[1].phi), ic[0]))][:limit]


def other_details(dr, x: Sequence[float], target: str, z: float, features: Sequence[str], shown: Sequence[str]) -> tuple[float, float, float]:
    """(phi, ci_low, ci_high) of all the contributions NOT in `shown`, added up; the interval uses the joint HC3 covariance of those
    coefficients. The card's "all other details together" row (web/engine.js otherDetails mirrors it), so the rows add up."""
    k = TARGETS.index(target)
    c = (np.asarray(x, float).ravel() - dr.mean_) / dr.scale_
    idx = [j for j, f in enumerate(features) if f not in set(shown)]
    phi = float(c[idx] @ dr.beta_[1:, k][idx])
    cov = dr.cov_[k][1:, 1:][np.ix_(idx, idx)]
    se = float(np.sqrt(max(0.0, c[idx] @ cov @ c[idx])))
    return phi, phi - z * se, phi + z * se


def driver_records(explanation: EffectExplanation, limit: int) -> list[dict]:
    """DriverV1 rows ({feature, value, contribution, ci95}) for the API's card, rounded to 3 decimals as the card shows them."""
    return [{"feature": c.feature, "value": c.value, "contribution": round(c.phi, 3), "ci95": (round(c.ci_low, 3), round(c.ci_high, 3))}
            for c in drivers(explanation, limit)]


def explain_option_drivers(engine, patient, causal) -> dict[str, list[dict]]:
    """{option: DriverV1 rows} for every option the card explains (its comparison against DPP-4i), and only when BOTH the option
    and DPP-4i have an estimate. Excluded and abstained options get nothing."""
    status = {o.arm: o.status for o in causal.options}
    if status.get(COMPARATOR) != "estimate":
        return {}
    x = engine.feature_vector(patient)
    limit = max_drivers(engine.params)
    out = {}
    for comparison in CARD_COMPARISONS:
        option = comparison.split("-")[0]
        if status.get(option) == "estimate":
            out[option] = driver_records(explain_effect(engine.fitted.dr, x, comparison, engine.z, engine.adjustment), limit)
    return out
