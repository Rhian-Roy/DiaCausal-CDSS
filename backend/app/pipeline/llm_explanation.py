"""Stage 5 — llm_explanation (NOT BUILT YET, returns "skipped").

Will turn the ranking, guardrail results and citations into the written answer
(a language model explains; it does not decide). When built, it sets
`ctx.reply_parts`. Until then the runner puts in a fixed dummy reply.
"""

from app.pipeline.context import PipelineContext, not_built_yet
from app.schemas import StageName, StageResult

NAME = StageName.LLM_EXPLANATION


def run(ctx: PipelineContext) -> StageResult:
    return not_built_yet(NAME)
