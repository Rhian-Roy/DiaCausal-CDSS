"""Runs the six stages in order and builds the response.

    backend_guard -> clinical_guardrails -> causal_engine -> rag_retrieval
                  -> llm_explanation -> [dummy reply] -> output_guard

Once a stage blocks the message, every later stage is reported as "skipped".
"""

from app.pipeline import (
    backend_guard,
    causal_engine,
    clinical_guardrails,
    llm_explanation,
    output_guard,
    rag_retrieval,
)
import time

from app.pipeline.context import PipelineContext
from app.schemas import ChatRequest, ChatResponse, Outcome, StageResult, StageStatus, TextPart
from app.tracing import log

STAGES_BEFORE_REPLY = [backend_guard, clinical_guardrails, causal_engine, rag_retrieval, llm_explanation]
STAGES_AFTER_REPLY = [output_guard]
STAGE_ORDER = [stage.NAME for stage in STAGES_BEFORE_REPLY + STAGES_AFTER_REPLY]


def dummy_reply(ctx: PipelineContext) -> TextPart:
    characters = sum(len(part.text) for part in ctx.parts)
    return TextPart(
        type="text",
        text=(
            f"Dummy reply from the DiaCausal backend. Your message ({characters} characters) "
            f"arrived safely with trace ID {ctx.trace_id}. No clinical analysis ran: the "
            "clinical guardrails, causal engine, guideline retrieval and explanation stages "
            "are not built yet."
        ),
    )


def _run(stage, ctx: PipelineContext) -> StageResult:
    started = time.perf_counter()
    if ctx.blocked_reason is not None:
        result = StageResult(
            name=stage.NAME,
            status=StageStatus.SKIPPED,
            detail="Not run: an earlier stage blocked the message.",
        )
    else:
        result = stage.run(ctx)
    # Measured here, once, so no stage can forget to time itself or report a wrong number.
    result.duration_ms = round((time.perf_counter() - started) * 1000, 1)

    if result.status is StageStatus.BLOCKED:
        log.warning("%s: blocked in %.1f ms (%s)", result.name, result.duration_ms, result.detail)
    else:
        log.info("%s: %s in %.1f ms", result.name, result.status, result.duration_ms)
    return result


def run_pipeline(request: ChatRequest) -> ChatResponse:
    ctx = PipelineContext(trace_id=request.client_trace_id, parts=request.parts)

    results = [_run(stage, ctx) for stage in STAGES_BEFORE_REPLY]
    if ctx.blocked_reason is None and not ctx.reply_parts:
        # llm_explanation is not built yet, so nothing wrote a reply: use a fixed one.
        ctx.reply_parts = [dummy_reply(ctx)]
    results += [_run(stage, ctx) for stage in STAGES_AFTER_REPLY]

    is_blocked = ctx.blocked_reason is not None
    return ChatResponse(
        trace_id=ctx.trace_id,
        outcome=Outcome.BLOCKED if is_blocked else Outcome.ANSWERED,
        parts=[] if is_blocked else ctx.reply_parts,
        blocked_reason=ctx.blocked_reason,
        reason_code=ctx.reason_code,
        scope_topic=ctx.scope_topic,
        stages=results,
    )
