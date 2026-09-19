"""What the stages share while one message moves through the pipeline."""

from dataclasses import dataclass, field

from app.schemas import Part, ReasonCode, ScopeTopic, StageName, StageResult, StageStatus


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
        return "\n\n".join(part.text for part in self.parts)


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
