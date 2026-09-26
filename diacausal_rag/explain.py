"""Explanation writer (RAG step 5): answer a question ONLY from the retrieved passages, with citations.

    python -m diacausal_rag.explain "Can SGLT2 inhibitors cause ketoacidosis?"                 # template
    python -m diacausal_rag.explain "..." --backend ollama    # local model (laptop / hospital, offline)
    GEMINI_API_KEY=... python -m diacausal_rag.explain "..." --backend gemini    # free online tier

Three interchangeable back-ends, one rule:
    template  (default, offline) quotes the passage sentences that share the most words with the
              question, each with its passage number. It cannot invent anything.
    gemini    Google's free Gemini API. Receives ONLY the question and the passages, never patient values.
    ollama    a small model running on this computer; nothing leaves the machine.

Whatever a model writes goes through check_answer(): every sentence must cite a passage that was
shown, most of its words must appear in the passages it cites, and it must not contain a dose. If
any sentence fails, or the model is unreachable, the answer falls back to the template, and the
reply says so. If retrieval found nothing, the answer is INSUFFICIENT_EVIDENCE: nothing is written.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path

from diacausal_engine.recommend import DOSE_PATTERN
from diacausal_rag import INTENDED_USE
from diacausal_rag.ingest import load_config
from diacausal_rag.retrieve import WITHHELD, tokens

PROMPT = (Path(__file__).resolve().parent / "prompt.v1.txt").read_text(encoding="utf-8")
BACKENDS = ("template", "gemini", "ollama")
_SPLIT = re.compile(r"(?:(?<=[.!?])|(?<=\]))\s+(?=[A-Z0-9\"“(•-])")
# The checker splits a model's answer after every citation group, and after .!? before a capital.
_ANSWER_SPLIT = re.compile(r"(?<=\])\s+|(?<=[.!?])\s+(?=[A-Z0-9\"“(•-])")
_CITES = re.compile(r"\s*((?:\[\d+\]\s*)+)[.!?]?\s*$")
_BULLET = re.compile(r"^[-•]\s*")
# A question that asks for a dose gets no explanation at all (doses come only from the drug label).
DOSE_QUESTION = re.compile(r"\b(doses?|dosage|dosing|milligrams?|mg|tablets?|titrat\w*|how much \w+ (should|can|to) (i|we|he|she|they) (give|take|start))\b", re.I)
NO_DOSE_NOTE = "DiaCausal never gives doses. Doses come only from the official drug label and the treating clinician."


def sentences(text: str) -> list[str]:
    """Split passage text into sentences; bullet marks removed."""
    parts = []
    for line in re.split(r"\s+(?=[•]\s)|\s+-\s(?=[A-Z])", text):
        for s in _SPLIT.split(line.strip()):
            s = _BULLET.sub("", s).strip()
            if len(s) > 1:
                parts.append(s)
    return parts


def _content(text: str) -> set[str]:
    return set(tokens(text))


def _usable(passages: list[dict]) -> list[tuple[int, dict]]:
    return [(n, p) for n, p in enumerate(passages, start=1) if p["text"] != WITHHELD]


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
    cfg = cfg or load_config()
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


def check_answer(text: str, passages: list[dict], min_support: float) -> tuple[list[dict], list[str]]:
    """Parse a model's answer into cited sentences and list every problem (empty list = it passes)."""
    problems: list[str] = []
    if DOSE_PATTERN.search(text):
        problems.append("the answer contains dose-like text")
    usable = dict(_usable(passages))
    items = []
    for s in _ANSWER_SPLIT.split(text.strip()):
        s = s.strip()
        if not s:
            continue
        m = _CITES.search(s)
        if not m:
            problems.append(f"a sentence has no citation: {s[:60]!r}")
            continue
        cites = sorted({int(x) for x in re.findall(r"\d+", m.group(1))})
        body = s[:m.start()].rstrip(" .") + "."
        missing = [c for c in cites if c not in usable]
        if missing:
            problems.append(f"cites passage(s) {missing} that were not shown")
            continue
        words = _content(body)
        support = set().union(*(_content(usable[c]["text"]) for c in cites))
        share = len(words & support) / len(words) if words else 0.0
        if share < min_support:
            problems.append(f"only {share:.0%} of a sentence's words are in the passages it cites: {body[:60]!r}")
            continue
        items.append({"text": body, "cites": cites})
    if not items and not problems:
        problems.append("empty answer")
    return items, problems


def build_prompt(question: str, passages: list[dict], max_sentences: int) -> str:
    numbered = "\n\n".join(f"[{n}] ({p['citation']['source_id']}, {p['citation']['section']}) {p['text']}"
                           for n, p in _usable(passages))
    return (PROMPT.replace("{max_sentences}", str(max_sentences))
            .replace("{question}", re.sub(r"[{}]", "", question)).replace("{passages}", numbered))


def _post(url: str, body: dict, headers: dict, timeout: float = 60) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def call_gemini(prompt: str, cfg: dict) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['gemini_model']}:generateContent"
    out = _post(url, {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0}},
                {"x-goog-api-key": key})
    return out["candidates"][0]["content"]["parts"][0]["text"]


def call_ollama(prompt: str, cfg: dict) -> str:
    out = _post(f"{cfg['ollama_host']}/api/generate",
                {"model": cfg["ollama_model"], "prompt": prompt, "stream": False, "options": {"temperature": 0}}, {}, 180)
    return out["response"]


CALLERS = {"gemini": call_gemini, "ollama": call_ollama}


def explain(question: str, evidence: dict, backend: str = "template", cfg: dict | None = None, caller=None,
            idf: dict[str, float] | None = None) -> dict:
    """One question + its retrieved evidence -> a cited explanation (or INSUFFICIENT_EVIDENCE)."""
    cfg = cfg or load_config()
    if backend not in BACKENDS:
        raise ValueError(f"backend must be one of {BACKENDS}")
    if DOSE_QUESTION.search(question):
        return _reply(question, backend, "INSUFFICIENT_EVIDENCE", [], NO_DOSE_NOTE)
    if backend == "template" or evidence.get("status") != "SUCCESS" or not _usable(evidence["passages"]):
        return template(question, evidence, cfg, idf)
    try:
        raw = (caller or CALLERS[backend])(build_prompt(question, evidence["passages"], int(cfg["explain_max_sentences"])), cfg)
    except Exception as e:  # unreachable, no key, quota: the template still answers
        fallback = template(question, evidence, cfg, idf)
        fallback["note"] = f"{backend} unavailable ({type(e).__name__}); showing quoted sentences instead"
        return fallback
    if raw.strip() == "INSUFFICIENT_EVIDENCE":
        return _reply(question, backend, "INSUFFICIENT_EVIDENCE", [], "the model found no answer in the passages")
    items, problems = check_answer(raw, evidence["passages"], float(cfg["explain_min_support"]))
    if problems:
        fallback = template(question, evidence, cfg, idf)
        fallback["note"] = f"{backend} answer failed the citation check ({problems[0]}); showing quoted sentences instead"
        return fallback
    return _reply(question, backend, "SUCCESS", items[: int(cfg["explain_max_sentences"])])


def render(reply: dict) -> str:
    if reply["status"] != "SUCCESS":
        return f"INSUFFICIENT EVIDENCE: {reply['note']}"
    quote = reply["backend"] == "template"
    lines = [(f"“{s['text']}”" if quote else s["text"]) + " " + "".join(f"[{c}]" for c in s["cites"]) for s in reply["sentences"]]
    return "\n".join(lines + ([f"({reply['note']})"] if reply["note"] else []))


def main(argv: list[str] | None = None) -> None:
    from diacausal_rag.ingest import ingest
    from diacausal_rag.retrieve import Retriever

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question")
    ap.add_argument("--backend", choices=BACKENDS, default="template")
    a = ap.parse_args(argv)
    retriever = Retriever(ingest())
    evidence = retriever.search(a.question)
    reply = explain(a.question, evidence, a.backend, idf=retriever.bm25.idf)
    print(render(reply))
    for n, p in enumerate(evidence["passages"], start=1):
        c = p["citation"]
        print(f"  [{n}] {c['source_id']} {c['title'][:70]} — {c['section']}, page {c['page']}")
    print(INTENDED_USE)


if __name__ == "__main__":
    main()
