"""Stage 2 — clinical_guardrails (NOT BUILT YET, returns "skipped").

Will apply hard safety rules that override any statistical estimate, e.g.
eGFR thresholds and contraindications (type 1 diabetes, past ketoacidosis).
Plug in: causal_engine/guardrails.py at the repo root.
"""

from app.pipeline.context import PipelineContext, not_built_yet
from app.schemas import StageName, StageResult

NAME = StageName.CLINICAL_GUARDRAILS


def run(ctx: PipelineContext) -> StageResult:
    return not_built_yet(NAME)
