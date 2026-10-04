"""Hybrid search: BM25 + TF-IDF + reciprocal rank fusion + structured evidence JSON (split out of retrieve.py).

    BM25       keyword search (diacausal.rag.index.bm25)
    vector     TF-IDF cosine similarity (diacausal.rag.index.tfidf), a placeholder for the October embedding model
    RRF        reciprocal rank fusion: score = sum over retrievers of 1 / (k + rank)
    reranker   a slot (diacausal.rag.retrieve.rerank), identity today
    output     {"status": "SUCCESS" | "INSUFFICIENT_EVIDENCE", "passages": [...with citations]}

Passages with dose-like text are withheld: doses come only from the drug label, never from RAG.
"""

from __future__ import annotations

import re

from diacausal import INTENDED_USE
from diacausal.config import load_rag_config
from diacausal.rag.index import tfidf
from diacausal.rag.index.bm25 import BM25, TOKEN, tokens  # noqa: F401  (TOKEN is re-exported for export_web)
from diacausal.rag.ingest.chunking import Chunk
from diacausal.rag.retrieve.query_processing import QueryPlan
from diacausal.rag.retrieve.rerank import rerank as rerank_slot

DOSE = re.compile(r"\b\d+(\.\d+)?\s*(mg|mcg|µg)\b|\b(once|twice)\s+daily\b|\bmg\s*/\s*day\b", re.I)
WITHHELD = "[Passage withheld: it contains dosing text. Doses come only from the official drug label.]"


def index_text(text: str) -> str:
    """The text that is searched: dose-like phrases removed, so no dose ever enters the index."""
    return DOSE.sub(" ", text)


def rrf(rankings: list[list[int]], k: int) -> dict[int, float]:
    """Reciprocal rank fusion of several ranked lists of chunk indices (best first)."""
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (k + rank)
    return fused


class Retriever:
    def __init__(self, chunks: list[Chunk], config: dict | None = None):
        self.cfg = config or load_rag_config()
        self.chunks = chunks
        if not chunks:
            return
        texts = [index_text(c.text) for c in chunks]
        self.bm25 = BM25(texts, self.cfg["bm25_k1"], self.cfg["bm25_b"])
        self.vectorizer, self.matrix = tfidf.build(texts)

    def rerank(self, question: str, candidates: list[int]) -> list[int]:
        """Slot for a cross-encoder reranker (October). Identity today."""
        return rerank_slot(question, candidates)

    def search(self, question: str, plan: QueryPlan | None = None) -> dict:
        """Hybrid search. With a `plan` (diacausal.rag.retrieve.query_processing) the KEYWORD search (BM25) runs once per
        expanded sub-query; the vector search ALWAYS uses `question` as asked. Without a plan this is exactly the
        search of one question (the browser's web/evidence.js mirrors this case)."""
        k = int(self.cfg["top_k"])
        if not self.chunks:
            return self._abstain(question, "the index is empty (no licence-cleared documents ingested yet)")
        queries = list(plan.sub_queries) if plan else [question]
        per_query = [self.bm25.scores(q) for q in queries]
        bm = [max(column) for column in zip(*per_query)]  # a passage's keyword score: its best sub-query
        vec = tfidf.similarities(self.vectorizer, self.matrix, question)  # the original question, never the expansion
        by_bm = [sorted(range(len(scores)), key=lambda i: -scores[i]) for scores in per_query]
        by_vec = sorted(range(len(vec)), key=lambda i: -vec[i])
        fused = rrf([*by_bm, by_vec], int(self.cfg["rrf_k"]))
        # passages that match neither search (both scores 0) are never shown just to fill the top k
        ranked = [i for i in sorted(fused, key=lambda i: -fused[i]) if bm[i] > 0 or vec[i] > 0]
        best = self.rerank(question, ranked)[:k]
        if max(bm) < self.cfg["min_bm25_score"]:
            return self._abstain(question, "no approved passage matches this question well enough")
        q = set(tokens(question))
        shown = set().union(*(self.bm25.tf[i].keys() for i in best))
        equivalents = plan.equivalents if plan else {}
        # a question word is covered if it, or a word its expansion added, is in the passages ("DKA" by "ketoacidosis")
        found = {w for w in q if w in shown or any(e in shown for e in equivalents.get(w, ()))}
        if q and len(found) / len(q) < self.cfg.get("min_query_coverage", 0.0):
            return self._abstain(question, "the passages found cover too few of the question's words")
        passages = []
        for i in best:
            c = self.chunks[i]
            passages.append({
                "chunk_id": c.chunk_id,
                "text": WITHHELD if DOSE.search(c.text) else c.text,
                "citation": {"source_id": c.source_id, "title": c.title, "version": c.version,
                             "section": c.section, "page": c.page, "licence_bucket": c.licence_bucket},
                "scores": {"bm25": round(bm[i], 4), "vector": round(float(vec[i]), 4), "rrf": round(fused[i], 5)},
            })
        return {"status": "SUCCESS", "question": question, "passages": passages, "intended_use": INTENDED_USE}

    def _abstain(self, question: str, reason: str) -> dict:
        return {"status": "INSUFFICIENT_EVIDENCE", "question": question, "reason": reason,
                "passages": [], "intended_use": INTENDED_USE}
