"""Export the RAG index to the website (web/evidence.json) so the search runs in any browser.

    python -m diacausal_rag.export_web

Plain English: the search needs only a few numbers per passage — how often each word appears
(for BM25) and the passage's TF-IDF vector (for the vector search) — plus the passage text to
show and its citation. We write those to JSON, and web/evidence.js repeats exactly the same steps
as retrieve.py in the visitor's browser. A test (tests/web/test_web.py) proves both give the same
passages in the same order with the same scores.

Passages with dose-like text are withheld HERE, before the file is written: their text never
reaches the website.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from diacausal_engine.recommend import DOSE_PATTERN
from diacausal_rag import INTENDED_USE
from diacausal_rag.explain import DOSE_QUESTION, NO_DOSE_NOTE
from diacausal_rag.ingest import CLEARED, CONFIG, CORPUS, ROOT, SOURCES_CSV, ingest, is_confirmed, load_config, load_sources
from diacausal_rag.retrieve import DOSE, TOKEN, WITHHELD, Retriever, index_text, tokens

WEB = ROOT / "web"


def _sha(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(p.name.encode() + b"\0" + p.read_bytes())
    return h.hexdigest()[:10]


def evidence_dict() -> dict:
    cfg = load_config()
    chunks = ingest()
    sources = load_sources()
    corpus_files = sorted(p for p in CORPUS.iterdir() if p.suffix in (".txt", ".csv"))
    out: dict = {
        "intended_use": INTENDED_USE,
        "config": {k: cfg[k] for k in ("top_k", "rrf_k", "bm25_k1", "bm25_b", "min_bm25_score", "min_query_coverage",
                                        "explain_max_sentences", "explain_min_support")},
        "stop_words": sorted(ENGLISH_STOP_WORDS),
        "bm25_token_pattern": TOKEN.pattern,
        "tfidf_token_pattern": r"(?u)\b\w\w+\b",
        "dose_pattern": DOSE.pattern,
        "withheld_text": WITHHELD,
        "strict_dose_pattern": DOSE_PATTERN.pattern,
        "dose_question_pattern": DOSE_QUESTION.pattern,
        "no_dose_note": NO_DOSE_NOTE,
        "sources": [{"id": r["id"], "title": r["title"], "issuer": r["issuer"], "version": r["version"],
                     "bucket": r["bucket"], "confirmed": is_confirmed(r), "use": r["use_in_diacausal"]}
                    for r in sources.values()],
        "cleared_bucket": CLEARED,
        "versions": {"corpus_sha": _sha(corpus_files) if corpus_files else "empty",
                     "sources_sha": _sha([SOURCES_CSV]), "config_sha": _sha([CONFIG])},
        "chunks": [],
    }
    if not chunks:
        out.update(bm25={"idf": {}, "avgdl": 0.0}, tfidf={"vocabulary": {}, "idf": []})
        return out
    r = Retriever(chunks, cfg)
    vec = r.vectorizer
    matrix = r.matrix.tocsr()
    for i, c in enumerate(chunks):
        row = matrix.getrow(i)
        withheld = bool(DOSE.search(c.text))
        out["chunks"].append({
            "chunk_id": c.chunk_id,
            "text": WITHHELD if withheld else c.text,
            "withheld": withheld,
            "citation": {"source_id": c.source_id, "title": c.title, "version": c.version,
                         "section": c.section, "page": c.page, "licence_bucket": c.licence_bucket},
            "bm25": {"tf": dict(Counter(tokens(index_text(c.text)))), "len": len(r.bm25.docs[i])},
            "tfidf": {str(int(j)): float(v) for j, v in zip(row.indices, row.data)},
        })
    out["bm25"] = {"idf": r.bm25.idf, "avgdl": r.bm25.avgdl}
    out["tfidf"] = {"vocabulary": {t: int(j) for t, j in vec.vocabulary_.items()},
                    "idf": [float(v) for v in vec.idf_], "ngram_range": list(vec.ngram_range),
                    "sublinear_tf": vec.sublinear_tf}
    return out


def export() -> dict:
    data = evidence_dict()
    (WEB / "evidence.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


if __name__ == "__main__":
    d = export()
    print(f"wrote web/evidence.json ({len(d['chunks'])} passages, corpus {d['versions']['corpus_sha']})")
