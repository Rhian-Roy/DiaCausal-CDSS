"""Explainable AI for the causal engine (docs/XAI_PLAN.md, plan section 7).

    baseline.py   version A: the XAI-only baseline (a gradient-boosted model on factual data, explained with TreeSHAP and
                  LIME, no causal adjustment, no intervals, no abstention). A BASELINE FOR THE ANALYSIS TAB ONLY: it never
                  reaches a doctor, the API or web/.
    truth.py      the generator's true effect modifiers, derived from data/params.yaml (never typed).

SHAP and LIME explain models, not causes: describe their output as "the estimate is larger/smaller for patients with ...".

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""
