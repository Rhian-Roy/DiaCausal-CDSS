"""Observability: a record of what each request actually did, for the Observability screen (docs/OBSERVABILITY.md).

    recorder.py   one trace per request; one span per pipeline layer, per part of a layer and per step inside the engine
    summaries.py  what each layer left in the context, reduced to IDs, codes, counts, versions and settings (never values)
    store.py      the traces on this computer (SQLite, newest 1,000 kept for 30 days)
    engine_facts.py  what the engine was fitted on at startup (the reference cohort, the models, the settings)

What a trace NEVER holds: patient values, the question, prompts, passages, the model's text, secrets. The same rule as the console
trace (diacausal/tracing.py); tests/orchestrator/test_observability.py sends distinctive values through and searches the store.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""
