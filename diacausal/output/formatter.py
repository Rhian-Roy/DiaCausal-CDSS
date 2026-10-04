"""Assemble AnswerCardV1 from the layers' results (plan 8.11). Every number on the card is copied from the causal
output, never from the explanation. P23 extends this file (parser for model answers, wording rules).

The comparator is the DPP-4 inhibitor: the engine states each other option's difference against it.
"""

from __future__ import annotations

from diacausal.api.schemas import (AbstainNoticeV1, AnswerCardV1, AskRequestV1, CardClaimV1, CausalOutputV1, CitationV1,
                                   EffectRowV1, EligibleOptionsV1, EvidenceBundleV1)

COMPARATOR = "DPP4i"
_STATUS = {"estimate": "ESTIMATED", "insufficient_evidence": "INSUFFICIENT_EVIDENCE", "excluded": "EXCLUDED"}


def patient_summary(request: AskRequestV1, bmi_category: str) -> str:
    p = request.patient
    return f"{p.age} y, {p.sex}, HbA1c {p.hba1c_pct:g}%, eGFR {p.egfr:g}, BMI {p.bmi:g} ({bmi_category})"


def _effects(causal: CausalOutputV1) -> list[EffectRowV1]:
    versus = {c.first: c.difference for c in causal.comparisons if c.second == COMPARATOR}
    rows = []
    for o in causal.options:
        estimated = o.status == "estimate"
        rows.append(EffectRowV1(
            option=o.arm, status=_STATUS[o.status], caution=any(s.action == "CAUTION" for s in o.safety),
            hba1c_change=o.effect if estimated else None,
            vs_comparator=versus.get(o.arm) if estimated and o.arm != COMPARATOR else None,
            weight_change_kg=o.secondary.weight_change_kg if estimated and o.secondary else None,
            hypo_risk_pct=o.secondary.hypo_risk_pct if estimated and o.secondary else None,
            cost_label=o.cost.label))
    return rows


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
    return AnswerCardV1(
        request_id=request.request_id, mode=(reply or {}).get("backend", request.mode), question=request.question,
        patient_summary=patient_summary(request, causal.bmi_category), comparator=COMPARATOR,
        claims=_claims(reply, evidence, labels), effects=_effects(causal), drivers=drivers, evidence_levels=levels,
        excluded=eligible.excluded,
        abstain=[AbstainNoticeV1(option=o.arm, why=o.insufficient_reason or "insufficient evidence")
                 for o in causal.options if o.status == "insufficient_evidence"],
        versions=causal.versions)
