"""What to do with the JSON a local model returns (`AnswerDraftV1`, plan 8.4): turn its claims into the cited sentences the rest
of the pipeline already understands, and check the numbers in them.

    to_items(draft, passages, min_support)   claims -> ({"text", "cites": [passage numbers]}, ...) plus every problem found
    numbers_in(text)                         the numbers written in a text
    numbers_match(...)                       plan 8.10 check 3: every number of the draft is in the causal output or the drivers,
                                             or is a citation page or version

The citation check is the SAME function that checks the older numbered-sentence answers (`guards.output_guards.check_answer`): every
claim must cite a passage that was shown, and most of its words must be in the passages it cites; a dose is refused. P23 replaces
this with the seven checks of plan 8.10; `numbers_match` is the check the benchmark reports and P23 can reuse.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from diacausal.api.schemas import AnswerDraftV1
from diacausal.guards.output_guards import _usable, check_answer

_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?")
# Digits that are part of a NAME, not a number: drug classes ("SGLT-2", "SGLT2i", "DPP-4", "DPP4"), "type 1" / "type 2", "HbA1c".
_NAME = re.compile(r"\b(?:sglt|dpp)[- ]?\d\w*|\btype[- ]?[12]\b|\bhba1c\b", re.I)


def numbers_in(text: str) -> list[str]:
    """Every number written in the text, as written ("-0.9", "8.4", "2016"); a minus sign counts as part of the number. The digits
    inside names ("SGLT-2", "DPP-4", "type 2 diabetes", "HbA1c") are not numbers."""
    return [m.group() for m in _NUMBER.finditer(_NAME.sub(" ", text))]


def _normal(number: str) -> str:
    return number.lstrip("-").lstrip("+")


def draft_text(draft: AnswerDraftV1) -> str:
    """All the prose of a draft (what a clinician would read), for the number check."""
    return " ".join([draft.question_context, *[c.claim for c in draft.evidence_summary], draft.limitations])


def numbers_match(draft: AnswerDraftV1, allowed_sources: Iterable[str], passages: list[dict]) -> tuple[bool, list[str]]:
    """(ok, the numbers that are not allowed). A number is allowed if it appears in one of `allowed_sources` (the causal output
    and the drivers, as text), or is the page or a number of the version of a passage the draft cites."""
    allowed = {_normal(n) for text in allowed_sources for n in numbers_in(text)}
    by_id = {p["chunk_id"]: p for p in passages}
    cited = {cid for c in draft.evidence_summary for cid in c.chunk_ids}
    for cid in cited:
        p = by_id.get(cid)
        if p:
            allowed |= {_normal(n) for n in numbers_in(f"{p['citation']['page']} {p['citation']['version']}")}
    unlisted = [n for n in numbers_in(draft_text(draft)) if _normal(n) not in allowed]
    return not unlisted, unlisted


def to_items(draft: AnswerDraftV1, passages: list[dict], min_support: float, max_claims: int = 4) -> tuple[list[dict], list[str]]:
    """The draft's claims as cited sentences: ([{"text", "cites": [n, ...]}], problems). `n` is the 1-based position of the passage in
    `passages`, the same numbering the template and the citation check use. A claim that cites no passage, or one that was not
    shown, is a problem (the whole draft then falls back to the template)."""
    number_of = {p["chunk_id"]: n for n, p in _usable(passages)}
    claims = draft.evidence_summary[:max_claims]
    if not claims:
        return [], ["the draft has no claim"]
    lines, problems = [], []
    for claim in claims:
        cites = sorted({number_of[cid] for cid in claim.chunk_ids if cid in number_of})
        if not claim.chunk_ids or len(cites) != len(set(claim.chunk_ids)):
            problems.append("a claim cites a passage that was not shown" if claim.chunk_ids else "a claim has no citation")
            continue
        lines.append(claim.claim.strip().rstrip(".") + ". " + "".join(f"[{n}]" for n in cites))
    if problems:
        return [], problems
    items, issues = check_answer(" ".join(lines), passages, min_support)
    return items, issues
