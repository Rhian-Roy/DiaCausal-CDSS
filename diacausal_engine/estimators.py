"""Steps (d) and (e): average effects (naive, IPW, matching, AIPW) and per-patient effects.

Every formula is written out in NumPy so each line can be explained; scikit-learn is only
used to fit the two helper models (propensity and outcome). Every estimate carries a 95%
interval.

Notation (for one option a):
    Y   observed 6-month HbA1c change (percentage points; negative = HbA1c fell)
    T   which option the patient received (0 = SGLT2i, 1 = DPP4i, 2 = SU)
    e_a propensity: P(T = a | patient details)
    mu_a outcome model: predicted Y if the patient had received a
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import StratifiedKFold
from sklearn.neighbors import NearestNeighbors

from diacausal_engine import ARMS, CONTRASTS

IDX = {a: i for i, a in enumerate(ARMS)}


@dataclass(frozen=True)
class Estimate:
    """One number with its 95% interval. `target` is an arm ("SGLT2i") or a contrast ("SGLT2i-DPP4i")."""

    method: str
    target: str
    value: float
    se: float
    low: float
    high: float

    def covers(self, truth: float) -> bool:
        return self.low <= truth <= self.high


def _est(method: str, target: str, value: float, se: float, z: float) -> Estimate:
    return Estimate(method, target, float(value), float(se), float(value - z * se), float(value + z * se))


def _from_influence(method: str, psi: np.ndarray, point: np.ndarray, z: float) -> list[Estimate]:
    """Estimates + SEs from per-patient influence values psi (n, 3): SE = sd / sqrt(n)."""
    n = len(psi)
    out = [_est(method, a, point[IDX[a]], psi[:, IDX[a]].std(ddof=1) / np.sqrt(n), z) for a in ARMS]
    for a, b in CONTRASTS:
        d = psi[:, IDX[a]] - psi[:, IDX[b]]
        out.append(_est(method, f"{a}-{b}", point[IDX[a]] - point[IDX[b]], d.std(ddof=1) / np.sqrt(n), z))
    return out


# ── d) naive ─────────────────────────────────────────────────────────────────


def naive(Y: np.ndarray, T: np.ndarray, z: float) -> list[Estimate]:
    """Unfair comparison: the plain average in each drug group (Welch standard errors)."""
    means, variances, counts = {}, {}, {}
    for a in ARMS:
        y = Y[T == IDX[a]]
        means[a], variances[a], counts[a] = y.mean(), y.var(ddof=1), len(y)
    out = [_est("naive", a, means[a], np.sqrt(variances[a] / counts[a]), z) for a in ARMS]
    for a, b in CONTRASTS:
        se = np.sqrt(variances[a] / counts[a] + variances[b] / counts[b])
        out.append(_est("naive", f"{a}-{b}", means[a] - means[b], se, z))
    return out


# ── d) IPW ───────────────────────────────────────────────────────────────────


def ipw_mean(Y: np.ndarray, got_it: np.ndarray, e_arm: np.ndarray) -> tuple[float, np.ndarray]:
    """Hajek (stabilised) inverse-probability-weighted mean of Y under one option.

    Each patient who got the option counts 1/e times: a patient for whom this drug was
    unusual stands in for the many similar patients who did not get it.
    Returns the mean and each patient's influence value (for the standard error).
    """
    w = got_it / e_arm
    mean = (w * Y).sum() / w.sum()
    psi = w * (Y - mean) / w.mean() + mean
    return float(mean), psi


def ipw(Y: np.ndarray, T: np.ndarray, e: np.ndarray, z: float) -> list[Estimate]:
    psi = np.zeros((len(Y), len(ARMS)))
    point = np.zeros(len(ARMS))
    for a in ARMS:
        point[IDX[a]], psi[:, IDX[a]] = ipw_mean(Y, (T == IDX[a]).astype(float), e[:, IDX[a]])
    return _from_influence("IPW", psi, point, z)


# ── d) propensity-score matching ─────────────────────────────────────────────


def _matched_outcomes(Y: np.ndarray, T: np.ndarray, logit_e: np.ndarray) -> np.ndarray:
    """(n, 3): own Y for the option received; the nearest match's Y for the other two.

    With three options we match on all three (log) propensities at once, so a match is a
    patient who was equally likely to get each drug.
    """
    out = np.empty((len(Y), len(ARMS)))
    for a in ARMS:
        donors = np.flatnonzero(T == IDX[a])
        nn = NearestNeighbors(n_neighbors=1).fit(logit_e[donors])
        _, j = nn.kneighbors(logit_e)
        out[:, IDX[a]] = Y[donors[j[:, 0]]]
        mine = T == IDX[a]
        out[mine, IDX[a]] = Y[mine]
    return out


def matching(Y: np.ndarray, T: np.ndarray, e: np.ndarray, z: float, n_boot: int, seed: int) -> list[Estimate]:
    """1-nearest-neighbour matching on the propensity vector; bootstrap 95% CI (approximate)."""
    logit_e = np.log(e)
    point = _matched_outcomes(Y, T, logit_e).mean(axis=0)
    rng = np.random.default_rng(seed)
    boots = np.empty((n_boot, len(ARMS)))
    n = len(Y)
    for b in range(n_boot):
        i = rng.integers(0, n, n)
        if len(np.unique(T[i])) < len(ARMS):
            i = np.arange(n)
        boots[b] = _matched_outcomes(Y[i], T[i], logit_e[i]).mean(axis=0)
    out = [_est("matching", a, point[IDX[a]], boots[:, IDX[a]].std(ddof=1), z) for a in ARMS]
    for a, b in CONTRASTS:
        d = boots[:, IDX[a]] - boots[:, IDX[b]]
        out.append(_est("matching", f"{a}-{b}", point[IDX[a]] - point[IDX[b]], d.std(ddof=1), z))
    return out


# ── d) AIPW (doubly robust; the cross-fitted "double machine learning" score) ──


def outcome_model(settings: dict, seed: int) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=int(settings["max_iter"]),
        learning_rate=float(settings["learning_rate"]),
        max_depth=int(settings["max_depth"]),
        random_state=seed,
    )


def crossfit_outcomes(X: np.ndarray, T: np.ndarray, Y: np.ndarray, folds: int, settings: dict, seed: int) -> np.ndarray:
    """Out-of-fold mu_a(X) for every patient and every option, (n, 3).

    For each fold, one model per option is trained on the OTHER folds' patients who got
    that option, then predicts for this fold's patients (whatever they actually got).
    """
    mu = np.zeros((len(Y), len(ARMS)))
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed + 1)
    for train, test in splitter.split(X, T):
        for a in ARMS:
            rows = train[T[train] == IDX[a]]
            mu[test, IDX[a]] = outcome_model(settings, seed).fit(X[rows], Y[rows]).predict(X[test])
    return mu


def aipw_scores(Y: np.ndarray, T: np.ndarray, e: np.ndarray, mu: np.ndarray) -> np.ndarray:
    """phi_a = mu_a(X) + 1{T=a} (Y - mu_a(X)) / e_a(X), for every patient and option, (n, 3).

    The outcome model makes a guess; the second term corrects that guess using the
    patients who really got option a, weighted by 1/e. If EITHER model is right, the
    average of phi is right — hence "doubly robust".
    """
    got = (T[:, None] == np.arange(len(ARMS))[None, :]).astype(float)
    return mu + got * (Y[:, None] - mu) / e


def aipw(phi: np.ndarray, z: float) -> list[Estimate]:
    return _from_influence("AIPW", phi, phi.mean(axis=0), z)


def by_target(estimates: list[Estimate]) -> dict[str, Estimate]:
    return {e.target: e for e in estimates}
