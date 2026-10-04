"""Explanation writer (RAG step 5): answer a question ONLY from the retrieved passages, with citations.

    python -m diacausal.llm.explain "Can SGLT2 inhibitors cause ketoacidosis?"                 # template
    python -m diacausal.llm.explain "..." --backend ollama    # local model (laptop / hospital, offline)

Two interchangeable back-ends, one rule:
    template  (default, offline) quotes the passage sentences that share the most words with the
              question, each with its passage number. It cannot invent anything.
    ollama    a small model running on this computer; nothing leaves the machine.

Whatever a model writes goes through check_answer(): every sentence must cite a passage that was
shown, most of its words must appear in the passages it cites, and it must not contain a dose. If
any sentence fails, or the model is unreachable, the answer falls back to the template, and the
reply says so. If retrieval found nothing, the answer is INSUFFICIENT_EVIDENCE: nothing is written.
"""

from __future__ import annotations

import argparse
import re

from diacausal import INTENDED_USE
from diacausal.config import load_rag_config
from diacausal.guards.output_guards import _usable, check_answer
from diacausal.llm.prompt_builder import build_prompt
from diacausal.llm.providers.ollama import call_ollama
from diacausal.llm.providers.template import _reply, template

BACKENDS = ("template", "ollama")
# A question that asks for a dose gets no explanation at all (doses come only from the drug label).
# "mg" is a dose, but "mg/dL" (and "mg/L", "mg per dL") is a unit of glucose or another lab value, so `mg` is not matched
# when a "per volume" unit follows it; "10mg" (no space) is matched as a dose. The same pattern runs in the browser
# (web/explain.js builds a RegExp from the string in web/evidence.json), so keep it to features both engines share.
_PER_VOLUME = r"(?!\s*(?:/|per)\s*(?:d?l|ml)\b)"
DOSE_QUESTION = re.compile(
    r"\b(doses?|dosage|dosing|milligrams?|mg" + _PER_VOLUME + r"|\d+(?:\.\d+)?\s*mg" + _PER_VOLUME
    + r"|tablets?|titrat\w*|how much \w+ (should|can|to) (i|we|he|she|they) (give|take|start))\b", re.I)
NO_DOSE_NOTE = "DiaCausal never gives doses. Doses come only from the official drug label and the treating clinician."

CALLERS = {"ollama": call_ollama}


def explain(question: str, evidence: dict, backend: str = "template", cfg: dict | None = None, caller=None,
            idf: dict[str, float] | None = None) -> dict:
    """One question + its retrieved evidence -> a cited explanation (or INSUFFICIENT_EVIDENCE)."""
    cfg = cfg or load_rag_config()
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
    from diacausal.rag.ingest.licence_gate import ingest
    from diacausal.rag.retrieve.hybrid import Retriever

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
