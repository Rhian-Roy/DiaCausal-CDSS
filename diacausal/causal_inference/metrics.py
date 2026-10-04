"""Step (f): grade the estimates against the known synthetic truth.

    bias      average (estimate - truth) across repeats: is it systematically off?
    RMSE      root-mean-squared error across repeats: how far off, typically?
    coverage  share of 95% intervals that contain the truth (target: about 0.95)
    PEHE      root-mean-squared error of PATIENT-level effects (lower is better)
    regret    how much worse, on average, the option with the best estimate is than the
              truly best option — both chosen only among options the safety rules and the
              overlap check allow (percentage points of HbA1c; 0 = perfect)
    SMD       standardised mean difference of a patient detail between drug groups;
              below 0.1 counts as balanced (Austin 2009)
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

from diacausal_engine import ARMS


def bias(estimates, truth: float) -> float:
    return float(np.mean(np.asarray(estimates, float) - truth))


def rmse(estimates, truth) -> float:
    return float(np.sqrt(np.mean((np.asarray(estimates, float) - np.asarray(truth, float)) ** 2)))


def coverage(lows, highs, truth) -> float:
    lows, highs, truth = (np.asarray(v, float) for v in (lows, highs, truth))
    return float(np.mean((lows <= truth) & (truth <= highs)))


def pehe(estimated, true) -> float:
    """Precision in Estimating Heterogeneous Effects = RMSE over patients."""
    return rmse(estimated, true)


def policy_regret(predicted: np.ndarray, true: np.ndarray, allowed: np.ndarray) -> tuple[float, int]:
    """(mean regret, patients decided). HbA1c change: lower (more negative) is better.

    predicted, true: (n, 3) expected change under each option; allowed: (n, 3) booleans.
    Patients with no allowed option are not decided (the system abstains for them).
    """
    decided = allowed.any(axis=1)
    if not decided.any():
        return float("nan"), 0
    pred = np.where(allowed, predicted, np.inf)[decided]
    tru = np.where(allowed, true, np.inf)[decided]
    chosen = pred.argmin(axis=1)
    regret = tru[np.arange(len(tru)), chosen] - tru.min(axis=1)
    return float(regret.mean()), int(decided.sum())


def abstention_rate(allowed: np.ndarray) -> float:
    """Share of (patient, option) pairs answered with 'insufficient evidence' or excluded."""
    return float(1.0 - np.asarray(allowed, bool).mean())


def smd(x: np.ndarray, T: np.ndarray, a: int, b: int, weights: np.ndarray | None = None) -> float:
    """Standardised mean difference of x between arms a and b (unweighted pooled SD)."""
    w = np.ones(len(x)) if weights is None else weights
    ia, ib = T == a, T == b
    mean_a = np.average(x[ia], weights=w[ia])
    mean_b = np.average(x[ib], weights=w[ib])
    sd = np.sqrt((x[ia].var(ddof=1) + x[ib].var(ddof=1)) / 2.0)
    return 0.0 if sd == 0 else float((mean_a - mean_b) / sd)


def balance_table(X: np.ndarray, names: list[str], T: np.ndarray, e: np.ndarray) -> list[dict]:
    """Largest |SMD| over the three pairs of options, before and after IPW weights 1/e."""
    w = 1.0 / e[np.arange(len(T)), T]
    rows = []
    for j, name in enumerate(names):
        pairs = list(combinations(range(len(ARMS)), 2))
        before = max(abs(smd(X[:, j], T, a, b)) for a, b in pairs)
        after = max(abs(smd(X[:, j], T, a, b, w)) for a, b in pairs)
        rows.append({"covariate": name, "smd_before": before, "smd_after": after})
    return rows
