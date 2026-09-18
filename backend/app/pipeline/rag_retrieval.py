"""Stage 4 — rag_retrieval (NOT BUILT YET, returns "skipped").

Will fetch the guideline passages (ADA / IDF PDFs in RAG/) that support the
answer, with page-level citations. Plug in: causal_engine/rag_lite.py at the
repo root.
"""

from app.pipeline.context import PipelineContext, not_built_yet
from app.schemas import StageName, StageResult

NAME = StageName.RAG_RETRIEVAL


def run(ctx: PipelineContext) -> StageResult:
    return not_built_yet(NAME)
