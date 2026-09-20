"""What the stages share while one message moves through the pipeline."""

from dataclasses import dataclass, field

from app.schemas import Part, PatientPart, ReasonCode, ScopeTopic, StageName, StageResult, StageStatus, TextPart


@dataclass
class PipelineContext:
    trace_id: str
    parts: list[Part]
    reply_parts: list[Part] = field(default_factory=list)
    blocked_reason: str | None = None  # set by the first stage that blocks
    reason_code: ReasonCode | None = None
    scope_topic: ScopeTopic | None = None

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
