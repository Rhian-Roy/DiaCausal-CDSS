"""DiaCausal: the single package (docs/RESTRUCTURE_PLAN.md, section 3).

Holds the API contract (diacausal.api.schemas), the shared settings (diacausal.config), the safety-rule loader
(diacausal.guards) and, as the restructure proceeds, everything that used to live in diacausal_engine/ and
diacausal_rag/ (those packages stay as shims until step 9).

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised
clinical use.
"""

__version__ = "0.3.0"

INTENDED_USE = (
    "Research prototype for clinician evaluation; not a marketed medical device; "
    "not for unsupervised clinical use."
)
