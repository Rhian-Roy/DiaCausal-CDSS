"""DiaCausal causal engine v0.3 — three options added to metformin.

Research prototype for clinician evaluation; not a marketed medical device;
not for unsupervised clinical use.

For one adult with type 2 diabetes already on metformin, it estimates the 6-month
change in HbA1c (percentage points) under each option — SGLT2 inhibitor, DPP-4
inhibitor, sulfonylurea — with a 95% interval, after cited safety rules have run.
The clinician decides.

Modules follow the "Causal Inference Pipeline" column of the team's flow chart:
    cohort.py      causal dataset (synthetic, India-calibrated; or a CSV later)
    dag.py         DAG formulation; treatment, outcome and adjustment set
    guardrails.py  safety rules from data/rules.csv (run before any estimate)
    propensity.py  cross-fitted multinomial propensity model + overlap check
    estimators.py  naive / IPW / matching / AIPW averages; DR-learner per patient
    metrics.py     bias, RMSE, coverage, PEHE, policy regret, balance
    recommend.py   one patient -> structured Causal Output (or NOT_APPLICABLE)
    api.py         FastAPI: POST /api/v1/recommend
"""

__version__ = "0.3.0"

INTENDED_USE = (
    "Research prototype for clinician evaluation; not a marketed medical device; "
    "not for unsupervised clinical use."
)

ARMS = ("SGLT2i", "DPP4i", "SU")
# Every pairwise comparison, written "first minus second".
CONTRASTS = (("SGLT2i", "DPP4i"), ("SU", "DPP4i"), ("SGLT2i", "SU"))
