"""Template provider: the offline answer that quotes the best-matching passage sentences (split out of explain.py).

It cannot invent anything: every sentence is copied from a passage and carries that passage's number.
`_reply` builds the structured reply every provider returns; llm/explain.py imports it from here.
"""

from __future__ import annotations

import re

from diacausal import INTENDED_USE
from diacausal.causal_inference.recommend import DOSE_PATTERN
from diacausal.config import load_rag_config
from diacausal.guards.output_guards import _content, _usable, sentences


def _reply(question: str, backend: str, status: str, items: list[dict], note: str = "") -> dict:
    return {"status": status, "question": question, "backend": backend, "sentences": items,
            "note": note, "intended_use": INTENDED_USE}


def _weighted_overlap(q: set[str], words: set[str], idf: dict[str, float]) -> float:
    """Share of the question's words found in a sentence, each word weighted by its IDF (rare words
    such as "ketoacidosis" count more than "cause"). Words the corpus never uses get the highest weight.
    Summed in sorted order so the browser mirror gets the same floating-point result."""
    top = max(idf.values(), default=1.0)
    weight = {t: idf.get(t, top) for t in q}
    total = sum(weight[t] for t in sorted(q))
    return sum(weight[t] for t in sorted(q & words)) / total if total else 0.0


def template(question: str, evidence: dict, cfg: dict | None = None, idf: dict[str, float] | None = None) -> dict:
    """Extractive answer: the best-matching sentences, quoted exactly, each with its passage number.
    idf: the retriever's BM25 IDF table (retriever.bm25.idf); without it every word counts the same."""
    cfg = cfg or load_rag_config()
    if evidence.get("status") != "SUCCESS":
        return _reply(question, "template", "INSUFFICIENT_EVIDENCE", [], evidence.get("reason", ""))
    q = _content(question)
    scored = []
    for n, p in _usable(evidence["passages"]):
        for k, s in enumerate(sentences(p["text"])):
            if DOSE_PATTERN.search(s) or not q or not re.match(r"[A-Z0-9\"“(\[]", s) or not re.search(r"[.!?:)\]”\"]$", s):
                continue  # a dose, or a fragment cut off at a passage edge
            overlap = _weighted_overlap(q, _content(s), idf) if idf else len(q & _content(s)) / len(q)
            if overlap > 0:
                scored.append((-overlap, n, k, s))
    scored.sort()
    items, per = [], {}
    for _, n, _, s in scored:
        if per.get(n, 0) >= 2:
            continue
        per[n] = per.get(n, 0) + 1
        items.append({"text": s, "cites": [n]})
        if len(items) >= int(cfg["explain_max_sentences"]):
            break
    if not items:
        return _reply(question, "template", "INSUFFICIENT_EVIDENCE", [],
                      "the passages found do not contain a sentence about this question")
    return _reply(question, "template", "SUCCESS", items)
