"""AnswerCardV1: what the screen shows (plan 8.11), in order: question and patient, cited evidence (at most 4
claims), the effects table, drivers, evidence level, excluded options with rule ID and source, abstain notices,
the intended-use sentence. Every number comes from CausalOutputV1."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from diacausal.api.schemas.base import OptionName, V1
from diacausal.api.schemas.causal import DriverV1
from diacausal.api.schemas.guards import RuleHitV1
from diacausal.api.schemas.llm import OutputCheckId
from diacausal import INTENDED_USE
from diacausal.causal_inference.schemas import Interval, Versions

EvidenceLevel = Literal["Moderate", "Low", "Insufficient"]  # never "High" on synthetic data


class CitationV1(V1):
    chunk_id: str
    label: str = Field(description="e.g. 'WHO 2018, p.12'")


class CardClaimV1(V1):
    text: str
    citations: list[CitationV1] = Field(min_length=1)


class EffectRowV1(V1):
    option: OptionName
    status: Literal["ESTIMATED", "INSUFFICIENT_EVIDENCE", "EXCLUDED"]
    caution: bool = Field(default=False, description="a 'check first' rule fired for this option")
    hba1c_change: Interval | None = Field(default=None, description="6-month change, percentage points, with its 95% interval")
    vs_comparator: Interval | None = Field(default=None, description="null for the comparator itself")
    weight_change_kg: Interval | None = None
    hypo_risk_pct: Interval | None = None
    cost_label: str = Field(description="'price unavailable' until a verified price exists")

    @model_validator(mode="after")
    def _only_estimated_options_carry_numbers(self):
        numbers = (self.hba1c_change, self.vs_comparator, self.weight_change_kg, self.hypo_risk_pct)
        if self.status == "ESTIMATED" and self.hba1c_change is None:
            raise ValueError("an ESTIMATED option needs hba1c_change (with its 95% interval)")
        if self.status != "ESTIMATED" and any(n is not None for n in numbers):
            raise ValueError("an excluded or insufficient-evidence option never shows an estimate")
        return self


class EvidenceLevelV1(V1):
    option: OptionName
    level: EvidenceLevel
    reason: str = Field(description="the one-line reason, from the TEAM-SET rule in params.yaml")


class AbstainNoticeV1(V1):
    option: OptionName
    why: str
    propensity: float | None = None
    threshold: float | None = None


class AnswerCardV1(V1):
    request_id: str
    mode: Literal["template", "ollama"]
    question: str
    patient_summary: str
    comparator: OptionName
    claims: list[CardClaimV1] = Field(max_length=4)
    question_context: str | None = Field(default=None, description="one sentence from the local model, only when it passed the output guards")
    limitations: str | None = Field(default=None, description="one or two sentences from the local model, only when it passed the output guards")
    effects: list[EffectRowV1] = Field(min_length=1, max_length=3)
    drivers: dict[OptionName, list[DriverV1]] = {}
    evidence_levels: list[EvidenceLevelV1]
    excluded: list[RuleHitV1]
    abstain: list[AbstainNoticeV1] = []
    fallback_used: bool = Field(default=False, description="true when the local model was asked and the template answered instead")
    failed_checks: list[OutputCheckId] = Field(default=[], description="the output checks (plan 8.10) the model's draft failed; empty on a timeout or when the model was not used")
    fallback_reason: str | None = Field(default=None, description="a CODE (TIMEOUT, UNREACHABLE, INVALID_JSON, GUARD_NUMBERS, ...), never text from the model")
    dropped_claims: int = Field(default=0, ge=0, description="claims of the model's draft the citation check dropped (the rest were kept)")
    versions: Versions
    decision: str = "Decision support only. The clinician decides."
    intended_use: str = INTENDED_USE

    @field_validator("intended_use")
    @classmethod
    def _intended_use_verbatim(cls, v: str) -> str:
        if v != INTENDED_USE:
            raise ValueError("intended_use must be the exact intended-use sentence")
        return v

    @field_validator("decision")
    @classmethod
    def _clinician_decides(cls, v: str) -> str:
        if not v.endswith("The clinician decides."):
            raise ValueError('every answer ends "The clinician decides."')
        return v

    @model_validator(mode="after")
    def _consistent(self):
        if (self.failed_checks or self.fallback_reason) and not self.fallback_used:
            raise ValueError("failed checks or a fallback reason mean fallback_used is true")
        removed = {h.option for h in self.excluded}
        for row in self.effects:
            if row.option in removed and row.status != "EXCLUDED":
                raise ValueError(f"{row.option} was removed by a rule, so it must be EXCLUDED, never estimated")
        if set(self.drivers) & removed:
            raise ValueError("drivers for an excluded option")
        return self
