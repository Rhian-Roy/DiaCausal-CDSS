"""Evidence level of each option's estimate (docs/PLAN_2026-10.md section 8.11, P24).

    Insufficient   propensity below 0.05, or the 95% interval wider than 1.5 points, or the retrieval abstained
    Low            interval wider than 1.0, or propensity 0.05 to 0.10, or fewer than 2 cited passages
    Moderate       everything else
    High           never: every estimate comes from a synthetic cohort (it would need real-world validation)

The cut-offs are in data/params.yaml, group `evidence_level` (TEAM-SET); none is typed here. web/engine.js mirrors
`assess`, `abstain_why` and `abstain_card` line by line (`evidenceLevel`, `abstainWhy`, `abstainCard`), reading the same
numbers from web/model.json; tests/web compares the two on a grid of inputs, so change them together.

Worked example (plan 8.11): an interval from -1.2 to -0.6 is 0.6 points wide, the propensity is 0.31 and two passages are
cited, so the level is Moderate. The same option with a propensity of 0.07 is Low.

    assess(option, citations=2)          -> Assessment(level, reason)   one OptionOut (or its dict) of the engine's output
    classify(width, propensity, ...)     -> (level, [the reasons that applied])   the rule on bare numbers (the benchmark)
    abstain_why(option)                  -> the "Why:" line of the abstain card
    abstain_card(option)                 -> the four lines of the abstain card, exactly as in section 8.11
    count_citations(texts, option)       -> how many passages name the option (its class word or its example molecule)

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from diacausal import INTENDED_USE
from diacausal.config import load_params

LEVELS = ("Moderate", "Low", "Insufficient")
# How the card names each option in short (the same words as LABEL in web/app.js; a test compares them).
SHORT_NAME = {"SGLT2i": "SGLT2i", "DPP4i": "DPP-4i", "SU": "Sulfonylurea"}
STILL_SEE = "What you can still see: cited guideline passages (Investigate tab)."


@dataclass(frozen=True)
class Rule:
    insufficient_propensity_below: float
    insufficient_width_above: float
    low_width_above: float
    low_propensity_below: float
    low_citations_below: int


@dataclass(frozen=True)
class Assessment:
    level: str | None  # None for an option the rules removed ("Not assessed")
    reason: str


def load_rule(params=None) -> Rule:
    """The cut-offs from params.yaml. Refuses to run with High switched on: the data are synthetic."""
    g = (params or load_params()).group("evidence_level")
    if g["high_enabled"]:
        raise ValueError("evidence_level.high_enabled is true, but High is never shown on synthetic data (plan 8.11)")
    return Rule(float(g["insufficient_propensity_below"]), float(g["insufficient_width_above"]), float(g["low_width_above"]),
                float(g["low_propensity_below"]), int(g["low_citations_below"]))


def round2(x: float) -> float:
    """Half away from zero to 2 decimals, done the same way as round2 in web/engine.js (so both print the same text)."""
    return math.copysign(math.floor(abs(x) * 100 + 0.5) / 100, x)


def fmt2(x: float) -> str:
    return f"{round2(x):.2f}"


def fmt_g(x: float) -> str:
    """A cut-off as written in params.yaml (1.5, 0.05, 2): Python's :g, which matches JavaScript's String(x) for these."""
    return f"{x:g}"


def _get(obj: Any, name: str):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name)


def width_of(option) -> float:
    e = _get(option, "effect")
    return round(_get(e, "ci_high") - _get(e, "ci_low"), 3)


def classify(width: float, propensity: float, citations: int | None = None, retrieval_abstained: bool = False,
             rule: Rule | None = None) -> tuple[str, list[str]]:
    """The section 8.11 rule on bare numbers: (level, the reasons that applied, in plain words). `citations=None` means no search
    ran (the benchmark), so the citation part of the rule is not used."""
    r = rule or load_rule()
    if retrieval_abstained:
        return "Insufficient", ["no licence-cleared passage answers this question"]
    if propensity < r.insufficient_propensity_below:
        return "Insufficient", [f"propensity {fmt2(propensity)} (below {fmt_g(r.insufficient_propensity_below)})"]
    if width > r.insufficient_width_above:
        return "Insufficient", [f"the 95% interval is {fmt2(width)} points wide (more than {fmt_g(r.insufficient_width_above)})"]
    low = []
    if width > r.low_width_above:
        low.append(f"the 95% interval is {fmt2(width)} points wide (more than {fmt_g(r.low_width_above)})")
    if propensity < r.low_propensity_below:
        low.append(f"propensity {fmt2(propensity)} (below {fmt_g(r.low_propensity_below)})")
    if citations is not None and citations < r.low_citations_below:
        low.append(f"{_passages(citations)} (fewer than {fmt_g(r.low_citations_below)})")
    return ("Low", low) if low else ("Moderate", [])


def _passages(n: int) -> str:
    return f"{n} cited passage" + ("" if n == 1 else "s")


def assess(option, *, citations: int | None, retrieval_abstained: bool = False, rule: Rule | None = None) -> Assessment:
    """The level of one option of the engine's output, with its one-line reason."""
    r = rule or load_rule()
    status = _get(option, "status")
    if status == "excluded":
        ids = ", ".join(_get(s, "rule_id") for s in _get(option, "safety") if _get(s, "action") == "EXCLUDE")
        return Assessment(None, f"Not assessed: removed by rule {ids} before estimation.")
    if status != "estimate" or retrieval_abstained:
        return Assessment("Insufficient", f"Insufficient: {abstain_why(option, r, retrieval_abstained)}.")
    w, p = width_of(option), _get(_get(option, "confidence"), "propensity")
    level, reasons = classify(w, p, citations, retrieval_abstained, r)
    if level == "Moderate":
        parts = [f"the 95% interval is {fmt2(w)} points wide", f"propensity {fmt2(p)}"]
        if citations is not None:
            parts.append(_passages(citations))
        return Assessment("Moderate", "Moderate: " + ", ".join(parts) + ".")
    return Assessment(level, f"{level}: " + "; ".join(reasons) + ".")


def abstain_why(option, rule: Rule | None = None, retrieval_abstained: bool = False) -> str:
    """The "Why:" of the abstain card (no full stop): which part of the rule made this option Insufficient, with its numbers."""
    r = rule or load_rule()
    if retrieval_abstained:
        return "no licence-cleared passage answers this question"
    reason = _get(option, "insufficient_reason") or ""
    conf = _get(option, "confidence")
    if conf is not None and _get(conf, "propensity") < r.insufficient_propensity_below:
        return (f"too few similar patients received this option in the reference data "
                f"(propensity {fmt2(_get(conf, 'propensity'))}; threshold {fmt_g(r.insufficient_propensity_below)})")
    if reason.startswith("Too uncertain"):
        return f"this patient's 95% interval is wider than {fmt_g(r.insufficient_width_above)} points, so no useful estimate can be shown"
    if reason.startswith("Outside the cohort: "):
        return "this patient is outside the range of the reference data (" + reason[len("Outside the cohort: "):] + ")"
    if _get(option, "status") == "estimate":  # an estimate that is Insufficient on the numbers alone (the engine abstains first)
        level, reasons = classify(width_of(option), _get(conf, "propensity"), None, False, r)
        return "; ".join(reasons)
    return reason[:1].lower() + reason[1:].rstrip(".")


def abstain_card(option, rule: Rule | None = None, retrieval_abstained: bool = False) -> list[str]:
    """The abstain card of section 8.11, line by line."""
    return [f"Insufficient evidence for: {SHORT_NAME[_get(option, 'arm')]}",
            f"Why: {abstain_why(option, rule, retrieval_abstained)}.",
            STILL_SEE,
            f"The clinician decides. {INTENDED_USE}"]


def count_citations(texts: Iterable[str], option) -> int:
    """How many passages name the option: its class word ("sglt2", "dpp-4", "sulfonylurea") or its example molecule. The same
    test as the "Evidence for this option" search of web/app.js."""
    keys = [_get(option, "name").split(" ")[0].lower(), _get(option, "example_molecule").lower()]
    return sum(any(k in t.lower() for k in keys) for t in texts)
