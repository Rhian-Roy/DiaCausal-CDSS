"""Assemble AnswerCardV1 from the layers' results (plan 8.11). Every number in the effects table is copied from the causal
output, never from the explanation; the model's words (question context, claims, limitations) are shown only after they passed
the output guards, which allow a number there only if it is exactly one the causal output or the drivers contain (P23).

The comparator is the DPP-4 inhibitor: the engine states each other option's difference against it.

Evidence levels (plan 8.11, P24; diacausal/causal_inference/evidence_level.py): one per option the rules left, with its one-line
reason. The citation count of an option is the number of retrieved passages that name it. An option whose level is Insufficient shows
NO estimate (the legend says so), even when the engine made one: that happens only when the retrieval abstained. Each Insufficient option
gets the abstain notice of section 8.11 (`why`, and the propensity and threshold when the engine abstained on overlap).
"""

from __future__ import annotations

from diacausal.api.schemas import (AbstainNoticeV1, AnswerCardV1, AskRequestV1, CardClaimV1, CausalOutputV1, CitationV1,
                                   EffectRowV1, EligibleOptionsV1, EvidenceBundleV1)
from diacausal.api.schemas.card import EvidenceLevelV1
from diacausal.causal_inference import evidence_level as ev
from diacausal.rag.retrieve.hybrid import WITHHELD

COMPARATOR = "DPP4i"
_STATUS = {"estimate": "ESTIMATED", "insufficient_evidence": "INSUFFICIENT_EVIDENCE", "excluded": "EXCLUDED"}


def patient_summary(request: AskRequestV1, bmi_category: str) -> str:
    p = request.patient
    return f"{p.age} y, {p.sex}, HbA1c {p.hba1c_pct:g}%, eGFR {p.egfr:g}, BMI {p.bmi:g} ({bmi_category})"


def _effects(causal: CausalOutputV1, insufficient: set[str]) -> list[EffectRowV1]:
    versus = {c.first: c.difference for c in causal.comparisons if c.second == COMPARATOR}
    rows = []
    for o in causal.options:
        estimated = o.status == "estimate" and o.arm not in insufficient
        status = "INSUFFICIENT_EVIDENCE" if o.status == "estimate" and not estimated else _STATUS[o.status]
        rows.append(EffectRowV1(
            option=o.arm, status=status, caution=any(s.action == "CAUTION" for s in o.safety),
            hba1c_change=o.effect if estimated else None,
            vs_comparator=versus.get(o.arm) if estimated and o.arm != COMPARATOR else None,
            weight_change_kg=o.secondary.weight_change_kg if estimated and o.secondary else None,
            hypo_risk_pct=o.secondary.hypo_risk_pct if estimated and o.secondary else None,
            cost_label=o.cost.label))
    return rows


def retrieval_abstained(evidence: EvidenceBundleV1 | None) -> bool:
    return evidence is None or evidence.status != "OK"


def evidence_levels(causal: CausalOutputV1, evidence: EvidenceBundleV1 | None, rule: ev.Rule | None = None) -> list[EvidenceLevelV1]:
    """One level per option the rules left (an excluded option is "Not assessed" and has none)."""
    rule = rule or ev.load_rule()
    abstained = retrieval_abstained(evidence)
    texts = [c.text for c in evidence.chunks if c.text != WITHHELD] if evidence else []
    out = []
    for o in causal.options:
        if o.status == "excluded":
            continue
        a = ev.assess(o, citations=ev.count_citations(texts, o), retrieval_abstained=abstained, rule=rule)
        out.append(EvidenceLevelV1(option=o.arm, level=a.level, reason=a.reason))
    return out


def abstain_notices(causal: CausalOutputV1, levels: list[EvidenceLevelV1], abstained: bool, rule: ev.Rule | None = None) -> list[AbstainNoticeV1]:
    """The abstain card of plan 8.11 for every option whose level is Insufficient."""
    rule = rule or ev.load_rule()
    insufficient = {lv.option for lv in levels if lv.level == "Insufficient"}
    out = []
    for o in causal.options:
        if o.arm not in insufficient:
            continue
        by_overlap = o.status != "estimate" and o.confidence is not None
        out.append(AbstainNoticeV1(option=o.arm, why=ev.abstain_why(o, rule, retrieval_abstained=abstained and o.status == "estimate"),
                                   propensity=o.confidence.propensity if by_overlap else None,
                                   threshold=rule.insufficient_propensity_below if by_overlap else None))
    return out


def _claims(reply: dict, evidence: EvidenceBundleV1, labels: dict[str, str], limit: int = 4) -> list[CardClaimV1]:
    claims = []
    for item in (reply or {}).get("sentences", [])[:limit]:
        cites = [CitationV1(chunk_id=evidence.chunks[n - 1].chunk_id, label=labels[evidence.chunks[n - 1].chunk_id])
                 for n in item["cites"]]
        claims.append(CardClaimV1(text=item["text"], citations=cites))
    return claims


def build_card(*, request: AskRequestV1, causal: CausalOutputV1, eligible: EligibleOptionsV1,
               evidence: EvidenceBundleV1, reply: dict | None, labels: dict[str, str], drivers: dict,
               levels: list) -> AnswerCardV1:
    reply = reply or {}
    insufficient = {lv.option for lv in levels if lv.level == "Insufficient"}
    return AnswerCardV1(
        request_id=request.request_id, mode=reply.get("backend", request.mode), question=request.question,
        patient_summary=patient_summary(request, causal.bmi_category), comparator=COMPARATOR,
        claims=_claims(reply, evidence, labels), effects=_effects(causal, insufficient), drivers=drivers, evidence_levels=levels,
        question_context=reply.get("question_context"), limitations=reply.get("limitations"),
        fallback_used=reply.get("fallback") is not None, failed_checks=reply.get("failed_checks", []),
        fallback_reason=reply.get("fallback"), dropped_claims=reply.get("dropped_claims", 0),
        excluded=eligible.excluded, cautions=eligible.caution,
        abstain=abstain_notices(causal, levels, retrieval_abstained(evidence)),
        versions=causal.versions)
