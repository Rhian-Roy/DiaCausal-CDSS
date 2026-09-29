"""Stage 6 — output_guard (runs today).

Checks the reply before it leaves the server.
- there is a reply with visible text
- it contains no word from the blocklist
- it contains no drug dose anywhere (text, evidence sentences, passages): doses come
  only from the drug label and the treating clinician
"""

from app.pipeline import blocklist
from app.pipeline.context import PipelineContext, blocked, passed
from app import engines
from app.schemas import EvidencePart, StageName, StageResult, TextPart

NAME = StageName.OUTPUT_GUARD


def run(ctx: PipelineContext) -> StageResult:
    reply_text = "\n\n".join(part.text for part in ctx.reply_parts if isinstance(part, TextPart))
    if not reply_text.strip():
        return blocked(ctx, NAME, "The reply was empty, so it was withheld.")
    if blocklist.find_blocked_term(reply_text):
        return blocked(ctx, NAME, "The reply did not pass the output check, so it was withheld.")
    evidence_text = " ".join(
        [s.text for p in ctx.reply_parts if isinstance(p, EvidencePart) for s in p.sentences]
        + [q.text for p in ctx.reply_parts if isinstance(p, EvidencePart) for q in p.passages]
    )
    if engines.dose_pattern().search(reply_text + " " + evidence_text):
        return blocked(ctx, NAME, "The reply contained dose-like text, so it was withheld. Doses come only from the drug label.")
    return passed(NAME, "Reply has text, no blocked words and no doses.")
