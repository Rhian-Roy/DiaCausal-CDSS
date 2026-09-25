"""Refutation tests and sensitivity analysis: try to break our own answer.

Plain English: if the method is sound, some deliberate "tricks" must NOT fool it.
    placebo treatment     shuffle who got which drug at random (20 times) -> the effect must vanish:
                          at least 85% of the placebo 95% CIs contain 0 (a single shuffle is
                          expected to "fail" 5% of the time, which is why we repeat it)
    random common cause   add a column of pure noise as an extra "confounder" -> the answer must not move
    data subset           re-run on a random 80% of patients -> the answer must stay about the same
    E-value               how strong would a HIDDEN confounder have to be to explain the effect away?
                          (VanderWeele & Ding 2017; bigger = more robust)

Passing these does not PROVE the answer is right (nothing can, with observational data), but
failing one would show something is wrong. All settings come from data/params.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from diacausal_engine import CONTRASTS
from diacausal_engine.config import Params
from diacausal_engine.estimators import Estimate, aipw, aipw_scores, by_target, crossfit_outcomes
from diacausal_engine.propensity import clip, crossfit_propensity


def aipw_contrasts(params: Params, X: np.ndarray, T: np.ndarray, Y: np.ndarray, seed: int) -> dict[str, Estimate]:
    """Cross-fitted AIPW on any (X, T, Y) — the same recipe the benchmark uses."""
    folds = int(params.get("engine.crossfit_folds"))
    e = clip(crossfit_propensity(X, T, folds, seed), params.get("engine.propensity_clip"))
    mu = crossfit_outcomes(X, T, Y, folds, params.group("engine.outcome_model"), seed)
    return by_target(aipw(aipw_scores(Y, T, e, mu), params.get("engine.ci_z")))


@dataclass(frozen=True)
class RefutationRow:
    check: str
    contrast: str
    original: float
    original_se: float
    new_estimate: float
    new_ci_low: float
    new_ci_high: float
    criterion: str
    passed: bool


def refute(params: Params, X: np.ndarray, T: np.ndarray, Y: np.ndarray, seed: int) -> list[RefutationRow]:
    rng = np.random.default_rng(seed)
    k = params.get("engine.refutation.stability_se_multiple")
    original = aipw_contrasts(params, X, T, Y, seed)

    repeats = int(params.get("engine.refutation.placebo_repeats"))
    placebos = [aipw_contrasts(params, X, rng.permutation(T), Y, seed + i) for i in range(repeats)]
    min_share = params.get("engine.refutation.placebo_min_share_containing_zero")
    noisy = aipw_contrasts(params, np.column_stack([X, rng.normal(size=len(X))]), T, Y, seed)
    keep = rng.random(len(X)) < params.get("engine.refutation.subset_fraction")
    subset = aipw_contrasts(params, X[keep], T[keep], Y[keep], seed)

    rows = []
    for a, b in CONTRASTS:
        t = f"{a}-{b}"
        o = original[t]
        share = float(np.mean([p[t].low <= 0.0 <= p[t].high for p in placebos]))
        mean_placebo = Estimate("placebo", t, float(np.mean([p[t].value for p in placebos])), 0.0,
                                float(np.mean([p[t].low for p in placebos])), float(np.mean([p[t].high for p in placebos])))
        checks = [
            ("placebo treatment", mean_placebo,
             f"{share:.0%} of {repeats} placebo CIs contain 0 (need >= {min_share:.0%})", share >= min_share),
            ("random common cause", noisy[t], f"within {k:g} SE of original", abs(noisy[t].value - o.value) <= k * o.se),
            ("data subset", subset[t], f"within {k:g} SE of original", abs(subset[t].value - o.value) <= k * o.se),
        ]
        for name, est, criterion, ok in checks:
            rows.append(RefutationRow(name, t, o.value, o.se, est.value, est.low, est.high, criterion, bool(ok)))
    return rows


def _evalue_from_rr(rr: float) -> float:
    """E-value for a risk ratio (VanderWeele & Ding 2017): RR + sqrt(RR * (RR - 1)), with RR >= 1."""
    rr = max(rr, 1.0 / rr)
    return float(rr + np.sqrt(rr * (rr - 1.0)))


def e_value(estimate: Estimate, outcome_sd: float, params: Params) -> tuple[float, float]:
    """(E-value for the estimate, E-value for the CI bound nearest 0).

    Continuous outcome: d = estimate / SD(Y); approximate RR = exp(0.91 * d). If the 95% CI
    crosses 0, the CI's E-value is 1 (no hidden confounding is needed to reach "no effect").
    """
    c = params.get("engine.refutation.evalue_smd_to_log_rr")
    point = _evalue_from_rr(float(np.exp(c * estimate.value / outcome_sd)))
    if estimate.low <= 0.0 <= estimate.high:
        return point, 1.0
    nearest = estimate.high if estimate.value < 0 else estimate.low
    return point, _evalue_from_rr(float(np.exp(c * nearest / outcome_sd)))
