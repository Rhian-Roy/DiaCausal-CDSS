"""What the causal engine was fitted on and with, read once at server start from the fitted Engine (no refit, no new estimate).

Every request's causal spans are answered by this one fitted engine, so the Observability screen shows it next to them: the reference
cohort (synthetic), the variables and their roles in the DAG, the models and the settings. Numbers here describe the SYNTHETIC
reference cohort and the configuration, never a patient. Cohort-level effects (ATE, ATT) are not computed by a request: they come from
the offline benchmark (results/benchmark_summary.csv, the Analysis tab).

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from diacausal import __version__
from diacausal.config import ARMS
from diacausal.observability.recorder import safe


def describe(engine, fit_ms: float | None) -> dict[str, Any]:
    from diacausal.causal_inference.dag import load_dag

    p, f = engine.params, engine.fitted
    dag = load_dag(p)
    roles: dict[str, list[str]] = {}
    for name, role in dag.roles.items():
        roles.setdefault(role, []).append(name)
    threshold = float(engine.threshold)
    thin = float(np.mean(f.e.min(axis=1) < threshold)) if f.e is not None and len(f.e) else None
    outcome_model = {k: p.get(f"engine.outcome_model.{k}") for k in ("max_iter", "learning_rate", "max_depth")}
    return safe({
        "engine": __version__, "params_version": p.version, "params_sha": p.fingerprint, "rules_sha": engine.rules.version,
        "fit_ms": round(fit_ms, 1) if fit_ms is not None else None,
        "fit_measured": fit_ms is not None,
        "reference_cohort": {"kind": "synthetic, India-calibrated (data/params.yaml)", "n": int(engine.n), "seed": int(engine.seed),
                             "rows_used": int(len(f.T)), "features": int(f.X.shape[1]),
                             "patients_per_arm": {a: int(np.sum(f.T == i)) for i, a in enumerate(ARMS)},
                             "share_below_overlap_threshold": round(thin, 4) if thin is not None else None},
        "variables": {"treatment": f"{dag.treatment}: one of {', '.join(ARMS)} added to metformin",
                      "outcome": f"{dag.outcome}: 6-month HbA1c change, percentage points",
                      "adjusted_for": list(engine.adjustment), "roles": roles,
                      "not_adjusted": roles.get("mediator", [])},
        "models": {
            "propensity": f"standardised logistic regression, cross-fitted in {int(p.get('engine.crossfit_folds'))} folds, "
                          f"clipped at {p.get('engine.propensity_clip')}",
            "outcome": f"HistGradientBoostingRegressor per option, cross-fitted ({', '.join(f'{k} {v}' for k, v in outcome_model.items())})",
            "scores": "AIPW (doubly robust) pseudo-outcomes per option",
            "per_patient_effect": "DR-learner (Kennedy): linear second stage on the AIPW scores, HC3 robust 95% interval",
            "secondary_outcomes": "the same propensities, own outcome models and DR-learners (weight change, hypoglycaemia)"
                                  if f.dr_weight is not None and f.dr_hypo is not None else "not fitted",
        },
        "settings": {"overlap_min_propensity": threshold, "max_interval_width": float(engine.max_width), "ci_z": float(engine.z),
                     "crossfit_folds": int(p.get("engine.crossfit_folds")), "propensity_clip": float(p.get("engine.propensity_clip"))},
        "provenance": "read from the fitted engine when the server started; nothing is re-estimated for this screen",
    })
