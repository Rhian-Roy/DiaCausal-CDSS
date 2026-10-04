"""Step (e): the DR-learner, the per-patient estimate (split out of estimators.py in restructure step 4).

Kennedy's doubly robust learner: regress the AIPW score of each option on the patient's details with a linear
second stage; HC3 robust standard errors give the 95% interval. The averages and the helper models stay in
estimators.py, which this file imports; nothing there imports this file.
"""

from __future__ import annotations

import numpy as np

from diacausal.causal_inference.estimators import IDX, TARGETS
from diacausal.config import ARMS, CONTRASTS


def pseudo_outcomes(phi: np.ndarray) -> np.ndarray:
    """(n, 6): the AIPW score for each option, then each pairwise difference."""
    cols = [phi[:, IDX[a]] for a in ARMS] + [phi[:, IDX[a]] - phi[:, IDX[b]] for a, b in CONTRASTS]
    return np.column_stack(cols)


class DRLearner:
    """Kennedy's DR-learner with a linear second stage and HC3 robust standard errors.

    Plain English: phi is a noisy but fair "what would have happened under option a" for
    every patient. Regressing phi on the patient's details averages out the noise and
    gives a formula; plugging THIS patient's details into the formula gives their
    personalised estimate. The robust standard error of that prediction gives the 95%
    interval:  x' beta  +/-  1.96 * sqrt(x' V x).
    """

    def fit(self, X: np.ndarray, phi: np.ndarray) -> DRLearner:
        self.mean_ = X.mean(axis=0)
        self.scale_ = np.where(X.std(axis=0) > 0, X.std(axis=0), 1.0)
        B = self._basis(X)
        pseudo = pseudo_outcomes(phi)
        bread = np.linalg.pinv(B.T @ B)
        leverage = np.einsum("ij,jk,ik->i", B, bread, B)
        self.beta_ = bread @ B.T @ pseudo  # (p, 6)
        resid = pseudo - B @ self.beta_
        adj = resid / (1.0 - np.clip(leverage, 0, 0.99))[:, None]  # HC3
        self.cov_ = np.stack([bread @ (B.T * adj[:, k] ** 2) @ B @ bread for k in range(len(TARGETS))])
        return self

    def _basis(self, X: np.ndarray) -> np.ndarray:
        Xs = (np.atleast_2d(X) - self.mean_) / self.scale_
        return np.column_stack([np.ones(len(Xs)), Xs])

    def predict(self, X: np.ndarray, z: float) -> dict[str, np.ndarray]:
        """{target: (n, 3) array of [estimate, low, high]}."""
        B = self._basis(X)
        out = {}
        for k, target in enumerate(TARGETS):
            value = B @ self.beta_[:, k]
            se = np.sqrt(np.einsum("ij,jk,ik->i", B, self.cov_[k], B))
            out[target] = np.column_stack([value, value - z * se, value + z * se])
        return out
