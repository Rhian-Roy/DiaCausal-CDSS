"""RAG evaluation on the gold question set (RAG guide Step R5).

    python -m diacausal_rag.evaluate                     # template explanations (offline)
    python -m diacausal_rag.evaluate --backend ollama    # or gemini (needs GEMINI_API_KEY)

Reads eval/rag_gold.csv (45 answerable questions with the source and section that answer them,
10 out-of-scope questions, 5 dose requests). Writes results/rag_eval.csv (one row per question)
and results/rag_eval_summary.csv, and prints:
    recall@5              answerable questions whose expected source+section is in the top 5
    answered              answerable questions that got an answer (not INSUFFICIENT_EVIDENCE)
    abstention accuracy   out-of-scope questions correctly answered INSUFFICIENT_EVIDENCE
    citation precision    explanation sentences that pass the citation checker
    dose leaks            dose-like text in any shown passage or explanation (must be 0)
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from diacausal_engine.recommend import DOSE_PATTERN
from diacausal_rag import INTENDED_USE
from diacausal_rag.explain import BACKENDS, check_answer, explain, render
from diacausal_rag.ingest import ROOT, ingest, load_config
from diacausal_rag.retrieve import Retriever

GOLD = ROOT / "eval" / "rag_gold.csv"
OUT = ROOT / "results"


def load_gold(path: Path = GOLD) -> list[dict]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def hit(evidence: dict, source: str, section: str) -> bool:
    return any(p["citation"]["source_id"] == source and section.lower() in p["citation"]["section"].lower()
               for p in evidence["passages"])


def run(backend: str = "template", gold: list[dict] | None = None) -> tuple[list[dict], dict]:
    cfg = load_config()
    retriever = Retriever(ingest(), cfg)
    rows = []
    for g in gold or load_gold():
        ev = retriever.search(g["question"])
        reply = explain(g["question"], ev, backend, cfg, idf=retriever.bm25.idf)
        text = render(reply) if reply["status"] == "SUCCESS" else ""
        shown = " ".join(p["text"] for p in ev["passages"]) + " " + text
        answer_text = " ".join(s["text"] + "".join(f"[{c}]" for c in s["cites"]) for s in reply["sentences"])
        checked, _ = check_answer(answer_text, ev["passages"], float(cfg["explain_min_support"])) if answer_text else ([], [])
        rows.append({
            "id": g["id"], "category": g["category"], "question": g["question"],
            "retrieval": ev["status"], "explanation": reply["status"], "backend": reply["backend"],
            "hit_at_5": int(hit(ev, g["expected_source"], g["expected_section"])) if g["category"] == "answerable" else "",
            "top_source": ev["passages"][0]["citation"]["source_id"] if ev["passages"] else "",
            "sentences": len(reply["sentences"]), "sentences_checked": len(checked),
            "dose_leak": int(bool(DOSE_PATTERN.search(shown))), "doctor_review": g["doctor_review"],
            "note": reply["note"],
        })
    return rows, summarise(rows, backend)


def summarise(rows: list[dict], backend: str) -> dict:
    ans = [r for r in rows if r["category"] == "answerable"]
    oos = [r for r in rows if r["category"] == "out_of_scope"]
    dose = [r for r in rows if r["category"] == "dose"]
    sent = sum(r["sentences"] for r in rows)
    return {
        "backend": backend,
        "questions": len(rows),
        "recall_at_5": sum(r["hit_at_5"] for r in ans) / len(ans),
        "answered": sum(r["explanation"] == "SUCCESS" for r in ans) / len(ans),
        "abstention_accuracy": sum(r["retrieval"] == "INSUFFICIENT_EVIDENCE" for r in oos) / len(oos),
        "citation_precision": sum(r["sentences_checked"] for r in rows) / sent if sent else 1.0,
        "dose_leaks": sum(r["dose_leak"] for r in rows),
        "dose_questions_without_leak": sum(not r["dose_leak"] for r in dose) / len(dose),
    }


def write(rows: list[dict], summary: dict, out: Path = OUT) -> None:
    out.mkdir(exist_ok=True)
    with (out / "rag_eval.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with (out / "rag_eval_summary.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["metric", "value"])
        for k, v in summary.items():
            w.writerow([k, f"{v:.3f}" if isinstance(v, float) else v])


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=BACKENDS, default="template")
    a = ap.parse_args(argv)
    rows, summary = run(a.backend)
    write(rows, summary)
    for k, v in summary.items():
        print(f"  {k:28s} {v:.3f}" if isinstance(v, float) else f"  {k:28s} {v}")
    missed = [r["id"] for r in rows if r["hit_at_5"] == 0]
    wrong = [r["id"] for r in rows if r["category"] == "out_of_scope" and r["retrieval"] == "SUCCESS"]
    print(f"  missed (answerable, not in top 5): {', '.join(missed) or 'none'}")
    print(f"  answered but out of scope:         {', '.join(wrong) or 'none'}")
    print(f"Saved results/rag_eval.csv and results/rag_eval_summary.csv. {INTENDED_USE}")


if __name__ == "__main__":
    main()
