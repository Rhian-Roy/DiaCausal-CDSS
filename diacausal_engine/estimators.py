# diacausal_engine/estimators.py  (shim; removed in restructure step 9)
# This module was split into two, so the shim names what it re-exports instead of aliasing one module.
from diacausal.causal_inference.dr_learner import DRLearner, pseudo_outcomes  # noqa: F401
from diacausal.causal_inference.estimators import (  # noqa: F401
    IDX, TARGETS, Estimate, _est, _from_influence, _matched_outcomes, aipw, aipw_scores, by_target,
    crossfit_outcomes, ipw, ipw_mean, levels_to_targets, matching, naive, outcome_model, s_learner, t_learner,
)
