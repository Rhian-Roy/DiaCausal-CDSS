"""What the stages share while one message moves through the pipeline."""

from dataclasses import dataclass, field

from app.schemas import (
    EstimatesPart,
    EvidencePart,
    OptionResult,
    OptionsPart,
    Part,
    PatientPart,
    ReasonCode,
    ScopeTopic,
    StageName,
    StageResult,
    StageStatus,
    TextPart,
)


@dataclass
class PipelineContext:
    trace_id: str
    parts: list[Part]
    reply_parts: list[Part] = field(default_factory=list)
    blocked_reason: str | None = None  # set by the first stage that blocks
    reason_code: ReasonCode | None = None
    scope_topic: ScopeTopic | None = None
    # Set by clinical_guardrails, read by the stages after it.
    options: list[OptionResult] = field(default_factory=list)  # may be used
    removed_options: list[OptionResult] = field(default_factory=list)  # "do not use"
    options_part: OptionsPart | None = None
    # Set by causal_engine, rag_retrieval and llm_explanation.
    estimates_part: EstimatesPart | None = None
    evidence: dict | None = None  # diacausal_rag search result (passages, status)
    evidence_part: EvidencePart | None = None

    @property
    def text(self) -> str:
        """Everything the clinician typed or dictated (the patient part is not text)."""
        return "\n\n".join(part.text for part in self.parts if isinstance(part, TextPart))

    @property
    def patient(self) -> PatientPart | None:
        """The patient details from the panel, if the page sent them."""
        return next((part for part in self.parts if isinstance(part, PatientPart)), None)


def passed(name: StageName, detail: str) -> StageResult:
    return StageResult(name=name, status=StageStatus.PASSED, detail=detail)


def blocked(
    ctx: PipelineContext,
    name: StageName,
    reason: str,
    code: ReasonCode | None = None,
    topic: ScopeTopic | None = None,
) -> StageResult:
    ctx.blocked_reason = reason
    ctx.reason_code = code
    ctx.scope_topic = topic
    return StageResult(name=name, status=StageStatus.BLOCKED, detail=reason)


def not_built_yet(name: StageName) -> StageResult:
    return StageResult(name=name, status=StageStatus.SKIPPED, detail="Not built yet.")
