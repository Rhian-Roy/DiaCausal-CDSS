"""Stage 4 — rag_retrieval (runs today).

Finds the passages of licence-cleared documents (WHO 2018 and US FDA safety communications,
RAG/sources.csv) that answer the clinician's question, with diacausal_rag.retrieve: BM25 +
TF-IDF, fused by reciprocal rank fusion. When the question's words are not covered well
enough it abstains ("insufficient evidence") instead of returning loosely related text.
Passages containing dosing text are withheld. The question text is never logged.
"""

from __future__ import annotations

from app import engines
from app.pipeline.context import PipelineContext, passed
from app.schemas import StageName, StageResult, StageStatus
from app.tracing import log

NAME = StageName.RAG_RETRIEVAL


def run(ctx: PipelineContext) -> StageResult:
    question = ctx.text.strip()
    if not question:
        return StageResult(name=NAME, status=StageStatus.SKIPPED, detail="No question text to search for.")
    ctx.evidence = engines.retriever().search(question)
    if ctx.evidence["status"] != "SUCCESS":
        log.info("rag_retrieval: abstained")
        return passed(NAME, "No approved passage covers this question: insufficient evidence.")
    n = len(ctx.evidence["passages"])
    log.info("rag_retrieval: %d passages", n)
    return passed(NAME, f"{n} cited passages from licence-cleared sources.")
