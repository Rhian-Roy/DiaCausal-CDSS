"""Knowledge retrieval: hybrid search + reciprocal rank fusion + structured evidence JSON.

    BM25       keyword search (exact words matter: "eGFR", "pancreatitis")
    vector     TF-IDF cosine similarity — a PLACEHOLDER for the medical embedding model we
               choose in October; it lets the fusion step run end to end today
    RRF        reciprocal rank fusion: score = sum over retrievers of 1 / (k + rank)
    reranker   a slot (identity today); a cross-encoder goes here in October
    output     {"status": "SUCCESS" | "INSUFFICIENT_EVIDENCE", "passages": [...with citations]}

Passages with dose-like text are withheld: doses come only from the drug label, never from RAG.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from diacausal_rag import INTENDED_USE
from diacausal_rag.ingest import Chunk, load_config

TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
DOSE = re.compile(r"\b\d+(\.\d+)?\s*(mg|mcg|µg)\b|\b(once|twice)\s+daily\b|\bmg\s*/\s*day\b", re.I)
WITHHELD = "[Passage withheld: it contains dosing text. Doses come only from the official drug label.]"


def tokens(text: str) -> list[str]:
    """Lower-case words without common English stop words ("the", "is", "of" carry no evidence)."""
    return [t for t in TOKEN.findall(text.lower()) if t not in ENGLISH_STOP_WORDS]


class BM25:
    def __init__(self, docs: list[str], k1: float, b: float):
        self.docs = [tokens(d) for d in docs]
        self.k1, self.b = k1, b
        self.avgdl = sum(map(len, self.docs)) / max(len(self.docs), 1)
        df = Counter(t for d in self.docs for t in set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [Counter(d) for d in self.docs]

    def scores(self, query: str) -> list[float]:
        q = tokens(query)
        out = []
        for tf, d in zip(self.tf, self.docs):
            s = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(d) / self.avgdl))
            out.append(s)
        return out


def rrf(rankings: list[list[int]], k: int) -> dict[int, float]:
    """Reciprocal rank fusion of several ranked lists of chunk indices (best first)."""
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (k + rank)
    return fused


class Retriever:
    def __init__(self, chunks: list[Chunk], config: dict | None = None):
        self.cfg = config or load_config()
        self.chunks = chunks
        if not chunks:
            return
        texts = [c.text for c in chunks]
        self.bm25 = BM25(texts, self.cfg["bm25_k1"], self.cfg["bm25_b"])
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
        self.matrix = self.vectorizer.fit_transform(texts)

    def rerank(self, question: str, candidates: list[int]) -> list[int]:
        """Slot for a cross-encoder reranker (October). Identity today."""
        return candidates

    def search(self, question: str) -> dict:
        k = int(self.cfg["top_k"])
        if not self.chunks:
            return self._abstain(question, "the index is empty (no licence-cleared documents ingested yet)")
        bm = self.bm25.scores(question)
        vec = cosine_similarity(self.vectorizer.transform([question]), self.matrix)[0]
        by_bm = sorted(range(len(bm)), key=lambda i: -bm[i])
        by_vec = sorted(range(len(vec)), key=lambda i: -vec[i])
        fused = rrf([by_bm, by_vec], int(self.cfg["rrf_k"]))
        best = self.rerank(question, sorted(fused, key=lambda i: -fused[i]))[:k]
        if max(bm) < self.cfg["min_bm25_score"]:
            return self._abstain(question, "no approved passage matches this question well enough")
        passages = []
        for i in best:
            c = self.chunks[i]
            passages.append({
                "text": WITHHELD if DOSE.search(c.text) else c.text,
                "citation": {"source_id": c.source_id, "title": c.title, "version": c.version,
                             "section": c.section, "page": c.page, "licence_bucket": c.licence_bucket},
                "scores": {"bm25": round(bm[i], 4), "vector": round(float(vec[i]), 4), "rrf": round(fused[i], 5)},
            })
        return {"status": "SUCCESS", "question": question, "passages": passages, "intended_use": INTENDED_USE}

    def _abstain(self, question: str, reason: str) -> dict:
        return {"status": "INSUFFICIENT_EVIDENCE", "question": question, "reason": reason,
                "passages": [], "intended_use": INTENDED_USE}
