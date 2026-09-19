"""Stage 1 — backend_guard (runs today).

Never trust the browser: repeat every check on the server, which has the final say.
- the message must contain visible text (not empty, not only spaces)
- no patient identifiers (Aadhaar, phone, PAN, email, ABHA)      -> reason_code "identifier"
- no foul language (the medical allowlist wins)                  -> "language"
- not an emergency (no treatment content is ever given for one)  -> "emergency"
- inside scope: adult type 2 diabetes, already on metformin      -> "out_of_scope"

The rules are shared with the browser: shared/guard_rules/rules.v1.json (see blocklist.py).
Part types and the 8000-character limit are already enforced by the request
schema (app/schemas.py) before this stage runs.
"""

from app.pipeline import blocklist
from app.pipeline.context import PipelineContext, blocked, passed
from app.schemas import ReasonCode, StageName, StageResult
from app.tracing import log

NAME = StageName.BACKEND_GUARD

TOPIC_NAMES = {
    "type_1": "type 1 diabetes",
    "pregnancy": "pregnancy",
    "under_18": "a patient under 18",
    "dka_hhs": "ketoacidosis or a hyperosmolar state",
    "insulin_start": "starting insulin",
}


def run(ctx: PipelineContext) -> StageResult:
    # The version only — never the text or the word that matched.
    log.info("guard rules version %s", blocklist.RULES_VERSION)
    if not ctx.text.strip():
        return blocked(ctx, NAME, "The message is empty.")

    verdict = blocklist.check(ctx.text)
    if verdict == "block:identifier":
        return blocked(
            ctx, NAME, "Please remove patient identifiers (Aadhaar, phone, PAN, email) and ask again.",
            ReasonCode.IDENTIFIER,
        )
    if verdict == "block:language":
        # Say *that* it was blocked, not *which* word: the reply must not repeat it.
        return blocked(ctx, NAME, "The message contains language that is not allowed.", ReasonCode.LANGUAGE)
    if verdict == "emergency":
        return blocked(
            ctx, NAME, "This may be an emergency. Follow your emergency protocol.", ReasonCode.EMERGENCY
        )
    if verdict.startswith("out_of_scope:"):
        topic = verdict.split(":", 1)[1]
        return blocked(
            ctx, NAME,
            "Out of scope: DiaCausal covers adults with type 2 diabetes already on metformin. "
            f"This question is about {TOPIC_NAMES[topic]}.",
            ReasonCode.OUT_OF_SCOPE, topic,  # type: ignore[arg-type]
        )
    return passed(NAME, "Message has text, no identifiers, no blocked words, no emergency, in scope.")
