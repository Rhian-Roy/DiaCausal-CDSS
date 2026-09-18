"""Stage 1 — backend_guard (runs today).

Never trust the browser: repeat the essential checks on the server.
- the message must contain visible text (not empty, not only spaces)
- it must not contain a word from the blocklist

Part types and the 8000-character limit are already enforced by the request
schema (app/schemas.py) before this stage runs.
"""

from app.pipeline import blocklist
from app.pipeline.context import PipelineContext, blocked, passed
from app.schemas import StageName, StageResult

NAME = StageName.BACKEND_GUARD


def run(ctx: PipelineContext) -> StageResult:
    if not ctx.text.strip():
        return blocked(ctx, NAME, "The message is empty.")
    if blocklist.find_blocked_term(ctx.text):
        # Say *that* it was blocked, not *which* word: the reply must not repeat it.
        return blocked(ctx, NAME, "The message contains language that is not allowed.")
    return passed(NAME, "Message has text and no blocked words.")
