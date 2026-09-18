"""Stage 3 — causal_engine (NOT BUILT YET, returns "skipped").

Will estimate the effect of each second-line option for this patient (CATE) and
rank them. Plug in: causal_engine/cdss.py and causal_engine/estimators.py at the
repo root.
"""

from app.pipeline.context import PipelineContext, not_built_yet
from app.schemas import StageName, StageResult

NAME = StageName.CAUSAL_ENGINE


def run(ctx: PipelineContext) -> StageResult:
    return not_built_yet(NAME)
