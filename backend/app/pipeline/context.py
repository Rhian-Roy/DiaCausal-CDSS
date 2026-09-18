"""What the stages share while one message moves through the pipeline."""

from dataclasses import dataclass, field

from app.schemas import Part, StageName, StageResult, StageStatus


@dataclass
class PipelineContext:
    trace_id: str
    parts: list[Part]
    reply_parts: list[Part] = field(default_factory=list)
    blocked_reason: str | None = None  # set by the first stage that blocks

    @property
    def text(self) -> str:
        return "\n\n".join(part.text for part in self.parts)


def passed(name: StageName, detail: str) -> StageResult:
    return StageResult(name=name, status=StageStatus.PASSED, detail=detail)


def blocked(ctx: PipelineContext, name: StageName, reason: str) -> StageResult:
    ctx.blocked_reason = reason
    return StageResult(name=name, status=StageStatus.BLOCKED, detail=reason)


def not_built_yet(name: StageName) -> StageResult:
    return StageResult(name=name, status=StageStatus.SKIPPED, detail="Not built yet.")
