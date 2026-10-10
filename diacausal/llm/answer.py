"""From the model's reply to the explanation the card is built from (P23): the seven output checks, then the parser, or the template.

    resolve(...)            a ModelReply (llm/providers/ollama.py) -> (explanation, GuardedDraftV1 | None)
    template_instead(...)   the template's explanation, marked as a fallback with its CODE and the failed check IDs

The explanation has the shape every provider returns (`status`, `sentences` with `cites`, `note`, `intended_use`) plus
    fallback        None when the model's draft was used, else a CODE (TIMEOUT, UNREACHABLE, INVALID_JSON, GUARD_NUMBERS, ...)
    failed_checks   the check IDs of plan 8.10 the draft failed (empty on a timeout, or when the model was not used)
    dropped_claims  claims the citation check dropped from a draft that was still used
and, for a draft that passed, `question_context` and `limitations`.
Anything but a PASS means the template answers: the model's text is never kept, logged or put in a reply.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from diacausal.api.schemas import CausalOutputV1, DriverV1, EligibleOptionsV1, GuardedDraftV1
from diacausal.guards.output_guards import failed_checks, run_output_guards
from diacausal.llm.providers.ollama import ModelReply
from diacausal.llm.providers.template import _reply, template
from diacausal.output.parser import parse, to_sentences


@dataclass
class GuardInputs:
    """What checks 3 to 7 compare a draft with: the rules' result, the causal output, the drivers, and the texts a number may come from."""

    eligible: EligibleOptionsV1 | None
    causal: CausalOutputV1
    drivers: dict[str, list[DriverV1]] = field(default_factory=dict)
    number_sources: tuple[str, ...] = ()


def template_instead(question: str, evidence: dict, cfg: dict, idf: dict[str, float] | None, code: str,
                     failed: list[str] | tuple[str, ...] = (), dropped: int = 0) -> dict:
    """The template's explanation, saying why it is the template (the CODE, never text from the model)."""
    out = template(question, evidence, cfg, idf)
    out["note"] = f"the local model could not be used ({code}); showing quoted sentences instead"
    return out | {"fallback": code, "failed_checks": list(failed), "dropped_claims": dropped}


def resolve(question: str, reply: ModelReply, *, evidence: dict, rag_cfg: dict, llm_cfg: dict, idf: dict[str, float] | None,
            inputs: GuardInputs) -> tuple[dict[str, Any], GuardedDraftV1 | None]:
    """The explanation for a request the model was asked about, and the guards' verdict (None when there was no text to check)."""
    if reply.code or reply.text is None:
        return template_instead(question, evidence, rag_cfg, idf, reply.code or "BAD_REPLY"), None
    max_claims = int(llm_cfg["max_claims"])
    guarded = run_output_guards(
        reply.text, passages=evidence["passages"], number_sources=inputs.number_sources, eligible=inputs.eligible, causal=inputs.causal,
        drivers=inputs.drivers, min_support=float(rag_cfg["explain_min_support"]), max_claims=max_claims)
    if guarded.status == "PASS":
        parsed = parse(guarded.draft, max_claims)
        kept = {"fallback": None, "failed_checks": [], "dropped_claims": guarded.dropped_claims}
        if parsed.insufficient:
            return _reply(question, "ollama", "INSUFFICIENT_EVIDENCE", [], "the model found no answer in the passages") | kept, guarded
        items = to_sentences(parsed, evidence["passages"])
        if items:
            return _reply(question, "ollama", "SUCCESS", items) | kept | {"question_context": parsed.question_context, "limitations": parsed.limitations}, guarded
    code = guarded.fallback_reason or "GUARD_CITATIONS"
    return template_instead(question, evidence, rag_cfg, idf, code, failed_checks(guarded), guarded.dropped_claims), guarded
