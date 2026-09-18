"""Stage 6 — output_guard (runs today).

Checks the reply before it leaves the server.
- there is a reply with visible text
- it contains no word from the blocklist

Later: e.g. withhold any dose that has no guideline citation.
"""

from app.pipeline import blocklist
from app.pipeline.context import PipelineContext, blocked, passed
from app.schemas import StageName, StageResult

NAME = StageName.OUTPUT_GUARD


def run(ctx: PipelineContext) -> StageResult:
    reply_text = "\n\n".join(part.text for part in ctx.reply_parts)
    if not reply_text.strip():
        return blocked(ctx, NAME, "The reply was empty, so it was withheld.")
    if blocklist.find_blocked_term(reply_text):
        return blocked(ctx, NAME, "The reply did not pass the output check, so it was withheld.")
    return passed(NAME, "Reply has text and no blocked words.")
