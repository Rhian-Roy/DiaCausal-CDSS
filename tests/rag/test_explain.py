"""RAG step 5 (explanations) and step R5 (evaluation on the gold set)."""

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from diacausal_rag import INTENDED_USE  # noqa: E402
from diacausal_rag.evaluate import load_gold, run  # noqa: E402
from diacausal_rag.explain import NO_DOSE_NOTE, build_prompt, check_answer, explain, sentences  # noqa: E402
from diacausal_rag.ingest import ingest, load_config  # noqa: E402
from diacausal_rag.retrieve import WITHHELD, Retriever  # noqa: E402

Q = "Can SGLT2 inhibitors cause ketoacidosis?"


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def evidence(cfg):
    return Retriever(ingest(), cfg).search(Q)


def test_template_quotes_passage_sentences_exactly_with_their_numbers(evidence, cfg):
    r = explain(Q, evidence, "template", cfg)
    assert r["status"] == "SUCCESS" and r["backend"] == "template" and r["intended_use"] == INTENDED_USE
    assert 0 < len(r["sentences"]) <= cfg["explain_max_sentences"]
    for s in r["sentences"]:
        (n,) = s["cites"]
        assert s["text"] in sentences(evidence["passages"][n - 1]["text"])
    assert any("ketoacidosis" in s["text"].lower() for s in r["sentences"])


def test_the_template_answer_passes_its_own_citation_check(evidence, cfg):
    r = explain(Q, evidence, "template", cfg)
    text = " ".join(s["text"] + f" [{s['cites'][0]}]" for s in r["sentences"])
    items, problems = check_answer(text, evidence["passages"], cfg["explain_min_support"])
    assert problems == [] and len(items) == len(r["sentences"])


def test_no_evidence_means_no_explanation(cfg):
    ev = Retriever(ingest(), cfg).search("What is the capital of France?")
    r = explain("What is the capital of France?", ev, "gemini", cfg, caller=lambda *a: "Paris [1].")
    assert r["status"] == "INSUFFICIENT_EVIDENCE" and r["sentences"] == []


@pytest.mark.parametrize("q", ["What dose of glimepiride should I start with?", "How many sitagliptin tablets per day?",
                               "dapagliflozin 10 mg or 5 mg?", "Maximum daily dosage of gliclazide"])
def test_a_dose_question_never_gets_an_explanation(q, cfg):
    ev = Retriever(ingest(), cfg).search(q)
    r = explain(q, ev, "gemini", cfg, caller=lambda *a: "Start with a low dose [1].")
    assert r["status"] == "INSUFFICIENT_EVIDENCE" and r["note"] == NO_DOSE_NOTE


def test_a_good_model_answer_is_kept(evidence, cfg):
    s = sentences(evidence["passages"][0]["text"])[0]
    r = explain(Q, evidence, "gemini", cfg, caller=lambda prompt, c: f"{s} [1]")
    assert r["status"] == "SUCCESS" and r["backend"] == "gemini" and r["sentences"][0]["cites"] == [1]


@pytest.mark.parametrize("answer, why", [
    ("SGLT2 inhibitors can cause ketoacidosis.", "no citation"),
    ("SGLT2 inhibitors can cause ketoacidosis [9].", "not shown"),
    ("Ketoacidosis is cured by drinking orange juice and resting in a dark room [1].", "words"),
    ("Give 10 mg once daily [1].", "dose"),
])
def test_a_bad_model_answer_falls_back_to_quoted_sentences(answer, why, evidence, cfg):
    r = explain(Q, evidence, "gemini", cfg, caller=lambda prompt, c: answer)
    assert r["backend"] == "template" and r["status"] == "SUCCESS"
    assert "failed the citation check" in r["note"] and why in r["note"]


def test_an_unreachable_model_falls_back_to_quoted_sentences(evidence, cfg):
    def down(prompt, c):
        raise OSError("connection refused")

    r = explain(Q, evidence, "ollama", cfg, caller=down)
    assert r["backend"] == "template" and "ollama unavailable" in r["note"]


def test_gemini_without_a_key_falls_back(evidence, cfg, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = explain(Q, evidence, "gemini", cfg)
    assert r["backend"] == "template" and "gemini unavailable" in r["note"]


def test_the_prompt_holds_only_the_question_and_the_passages(evidence):
    p = build_prompt(Q, evidence["passages"], 4)
    assert Q in p and INTENDED_USE in p and "Use ONLY the numbered passages" in p
    for word in ("age", "egfr", "hba1c", "bmi", "patient_id"):
        assert f"{word}:" not in p.lower()  # no patient fields, ever
    assert WITHHELD not in p  # withheld passages are never sent to a model


def test_gold_set_is_well_formed():
    gold = load_gold()
    assert len(gold) == 60 and len({g["id"] for g in gold}) == 60
    cats = [g["category"] for g in gold]
    assert cats.count("answerable") == 45 and cats.count("out_of_scope") == 10 and cats.count("dose") == 5
    assert sum(g["doctor_review"] == "yes" for g in gold) == 20
    sources = {r["id"] for r in csv.DictReader((ROOT / "RAG/sources.csv").open(encoding="utf-8"))}
    assert all(g["expected_source"] in sources for g in gold if g["category"] == "answerable")


def test_evaluation_meets_the_bar_and_the_saved_results_are_fresh():
    rows, summary = run("template")
    assert summary["dose_leaks"] == 0 and summary["dose_questions_without_leak"] == 1.0
    assert summary["citation_precision"] == 1.0
    assert summary["recall_at_5"] >= 0.85 and summary["answered"] >= 0.9 and summary["abstention_accuracy"] >= 0.7
    saved = {r["metric"]: r["value"] for r in csv.DictReader((ROOT / "results/rag_eval_summary.csv").open())}
    fresh = {k: (f"{v:.3f}" if isinstance(v, float) else str(v)) for k, v in summary.items()}
    assert saved == fresh, "run: python -m diacausal_rag.evaluate"


def test_the_online_function_uses_exactly_the_same_prompt_and_rules():
    """supabase/functions/explain/index.ts embeds prompt.v1.txt verbatim and keeps the safety checks."""
    ts = (ROOT / "supabase/functions/explain/index.ts").read_text(encoding="utf-8")
    embedded = ts.split("const PROMPT = `", 1)[1].split("`;", 1)[0]
    assert embedded == (ROOT / "diacausal_rag/prompt.v1.txt").read_text(encoding="utf-8")
    for must in ('claims(jwt).aal !== "aal2"', "profile?.approved", "GEMINI_API_KEY", "dose_question_pattern",
                 "c.withheld", "MAX_PASSAGES = 5", "`[${i + 1}] (${c.citation.source_id}, ${c.citation.section}) ${c.text}`"):
        assert must in ts, must
    assert "console.log" not in ts  # the question is never logged
    assert "AIza" not in ts  # no key in the code
