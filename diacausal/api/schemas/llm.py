"""LLMRequestV1, AnswerDraftV1 and GuardedDraftV1 (plan 8.8 to 8.10). The model only rephrases retrieved
evidence and copies numbers; every number on the final card comes from CausalOutputV1, never from the model."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from diacausal.api.schemas.base import OptionName, V1
from diacausal.api.schemas.causal import CausalOutputV1, DriverV1
from diacausal.api.schemas.evidence import EvidenceBundleV1
from diacausal.api.schemas.guards import RuleHitV1


class LLMRequestV1(V1):
    """What the prompt builder hands to a provider (the fields of the 8.9 template). Temperature 0 and a
    4,096-token context are provider settings, not part of this contract."""

    request_id: str
    mode: Literal["template", "ollama"]
    question: str = Field(min_length=1, max_length=300)
    patient_summary: str = Field(description="e.g. '52 y, M, HbA1c 8.6%, eGFR 72, BMI 27.1 (overweight)'")
    excluded_by_rules: list[RuleHitV1]
    causal_output: CausalOutputV1
    drivers: dict[OptionName, list[DriverV1]]
    evidence: EvidenceBundleV1
    max_claims: int = Field(default=4, ge=1, le=4)

    @model_validator(mode="after")
    def _no_excluded_option_in_drivers(self):
        removed = {h.option for h in self.excluded_by_rules}
        bad = removed & set(self.drivers)
        if bad:
            raise ValueError(f"drivers given for an option the rules removed: {sorted(bad)}")
        return self


class ClaimV1(V1):
    claim: str
    chunk_ids: list[str] = Field(description="the retrieved passages that support the claim; an uncited claim is dropped by the output guards")


class AnswerDraftV1(V1):
    """What the LLM may return (and nothing else)."""

    question_context: str
    evidence_summary: list[ClaimV1]
    limitations: str
    insufficient: bool = False
    insufficient_reason: str | None = Field(default=None, description="one sentence, when insufficient is true")


OutputCheckId = Literal["parse", "citations", "numbers", "dose_threshold", "excluded_option", "insufficient_wording", "identifier_causal"]


class OutputCheckV1(V1):
    id: OutputCheckId
    result: Literal["PASS", "FAIL"]


class GuardedDraftV1(V1):
    """The output guards' verdict (plan 8.10). FALLBACK = use the template wording instead; ABSTAIN = no claim
    survived; BLOCK = an identifier or causal wording about a driver."""

    status: Literal["PASS", "FALLBACK", "ABSTAIN", "BLOCK"]
    checks: list[OutputCheckV1]
    draft: AnswerDraftV1 | None = Field(default=None, description="the kept claims; null on FALLBACK, ABSTAIN or BLOCK")
    dropped_claims: int = Field(default=0, ge=0)
    fallback_reason: str | None = None

    @model_validator(mode="after")
    def _draft_only_when_passed(self):
        if self.status == "PASS" and self.draft is None:
            raise ValueError("a PASS needs the kept draft")
        if self.status != "PASS" and self.draft is not None:
            raise ValueError("only a PASS carries a draft")
        return self
