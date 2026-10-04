"""Pass-through stubs for what is not built yet (the list is in diacausal/registry.py: `stubs()`).

A stub changes nothing and CHECKS nothing; it says so in the trace ("... layer is a STUB: nothing was checked") so a
pass-through is never mistaken for a check that ran. When the real one lands, change one line in the registry.
"""

from __future__ import annotations

from diacausal.orchestrator.context import Context
from diacausal.tracing import stub_notice


def query_processing(ctx: Context, question: str) -> str:
    """P16: rewrite the question for search. Today the question is searched as typed."""
    stub_notice("query processing", ctx.request_id)
    return question


def shap_drivers(ctx: Context) -> dict:
    """P25: SHAP drivers of each option's estimate. Today: none."""
    stub_notice("shap drivers", ctx.request_id)
    return {}


def evidence_levels(ctx: Context) -> list:
    """P24: the Moderate / Low / Insufficient label per option. Today: none (an empty list, not a guess)."""
    stub_notice("evidence levels", ctx.request_id)
    return []


def prompt_builder(ctx: Context) -> None:
    """P22: the prompt for the local model. Today the template writes the answer and needs none; the older
    prompt code inside llm/explain.py serves `mode: ollama` until this exists."""
    stub_notice("prompt builder", ctx.request_id)


def full_output_checks(ctx: Context) -> None:
    """P23: the seven output checks of plan 8.10 (parse, citations, numbers, dose threshold, excluded option,
    insufficient wording, identifier/causal wording). The real layer already runs the dose and citation checks."""
    stub_notice("full output checks", ctx.request_id)
