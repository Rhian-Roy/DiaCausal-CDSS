"""What is kept of a model's draft that passed the output guards (plan 8.10, last paragraph): the question context, at most 4 evidence
claims with their chunk IDs, and the limitations. Nothing else of the draft goes on (the `insufficient_reason` text, for one, is dropped;
only the fact that the model found no answer is kept).

    parse(draft, max_claims)            AnswerDraftV1 -> ParsedDraft
    to_sentences(parsed, passages)      the claims as {"text", "cites": [position of the passage]}, the form the card builder reads

A claim whose chunk IDs are not among the passages is dropped here too (the guards already dropped them; this keeps the parser safe on
its own). The formatter (diacausal/output/formatter.py) builds the card from this and takes every NUMBER from CausalOutputV1.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

from dataclasses import dataclass

from diacausal.api.schemas import AnswerDraftV1
from diacausal.guards.output_guards import _usable


@dataclass(frozen=True)
class ParsedClaim:
    text: str
    chunk_ids: tuple[str, ...]


@dataclass(frozen=True)
class ParsedDraft:
    question_context: str
    claims: tuple[ParsedClaim, ...]
    limitations: str
    insufficient: bool  # the model found no answer in the passages (its reason text is not kept)


def parse(draft: AnswerDraftV1, max_claims: int = 4) -> ParsedDraft:
    claims = tuple(ParsedClaim(c.claim.strip(), tuple(c.chunk_ids)) for c in draft.evidence_summary[:max_claims])
    return ParsedDraft(draft.question_context.strip(), claims, draft.limitations.strip(), draft.insufficient)


def to_sentences(parsed: ParsedDraft, passages: list[dict]) -> list[dict]:
    """[{"text": "claim.", "cites": [n, ...]}] where n is the 1-based position of the passage in `passages` (the numbering the template
    and the citation checker use)."""
    number_of = {p["chunk_id"]: n for n, p in _usable(passages)}
    out = []
    for claim in parsed.claims:
        if claim.chunk_ids and all(cid in number_of for cid in claim.chunk_ids):
            out.append({"text": claim.text.rstrip(".") + ".", "cites": sorted({number_of[cid] for cid in claim.chunk_ids})})
    return out
