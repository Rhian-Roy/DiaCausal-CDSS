"""RAG step 5 (explanations) and step R5 (evaluation on the gold set)."""

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from diacausal import INTENDED_USE  # noqa: E402
from diacausal.rag.evaluate import load_gold, run  # noqa: E402
from diacausal.guards.output_guards import check_answer, sentences  # noqa: E402
from diacausal.llm.explain import DOSE_QUESTION, NO_DOSE_NOTE, explain  # noqa: E402
from diacausal.llm.prompt_builder import build_prompt  # noqa: E402
from diacausal.config import load_rag_config as load_rag_config  # noqa: E402
from diacausal.rag.ingest.licence_gate import ingest  # noqa: E402
from diacausal.rag.retrieve.hybrid import Retriever, WITHHELD  # noqa: E402

Q = "Can SGLT2 inhibitors cause ketoacidosis?"


@pytest.fixture(scope="module")
def cfg():
    return load_rag_config()


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
    r = explain("What is the capital of France?", ev, "ollama", cfg, caller=lambda *a: "Paris [1].")
    assert r["status"] == "INSUFFICIENT_EVIDENCE" and r["sentences"] == []


@pytest.mark.parametrize("q", ["What dose of glimepiride should I start with?", "How many sitagliptin tablets per day?",
                               "dapagliflozin 10 mg or 5 mg?", "Maximum daily dosage of gliclazide"])
def test_a_dose_question_never_gets_an_explanation(q, cfg):
    ev = Retriever(ingest(), cfg).search(q)
    r = explain(q, ev, "ollama", cfg, caller=lambda *a: "Start with a low dose [1].")
    assert r["status"] == "INSUFFICIENT_EVIDENCE" and r["note"] == NO_DOSE_NOTE


GLUCOSE_QUESTIONS = ["Finger-prick glucose 180 mg/dL after lunch. Can SGLT2 inhibitors cause ketoacidosis?",
                     "Fasting glucose 126 mg/dl: can SGLT2 inhibitors cause ketoacidosis?",
                     "With glucose 210 mg / dL, can SGLT2 inhibitors cause ketoacidosis?",
                     "CRP 5 mg/L: can SGLT2 inhibitors cause ketoacidosis?",
                     "Blood sugar 200 mg per dL, can SGLT2 inhibitors cause ketoacidosis?"]


@pytest.mark.parametrize("q", GLUCOSE_QUESTIONS)
def test_a_glucose_unit_is_not_a_dose_request(q):
    """"mg/dL" is a unit of glucose, not an amount of a drug: the pattern must not match it."""
    assert DOSE_QUESTION.search(q) is None


@pytest.mark.parametrize("q", GLUCOSE_QUESTIONS)
def test_a_question_that_quotes_a_glucose_value_still_gets_its_explanation(q, cfg):
    ev = Retriever(ingest(), cfg).search(q)
    r = explain(q, ev, "template", cfg)
    assert r["note"] != NO_DOSE_NOTE
    assert r["status"] == "SUCCESS" and r["sentences"], "the passages about ketoacidosis answer it"


@pytest.mark.parametrize("q", ["Is 10 mg right?", "How many mg of sitagliptin?", "glimepiride 2 mg once daily?", "5 mg or 10 mg?",
                               "mg per day for gliclazide", "Give 25 milligrams?", "dapagliflozin 10mg daily", "tablets for sitagliptin?"])
def test_real_dose_requests_are_still_caught_after_the_unit_fix(q):
    assert DOSE_QUESTION.search(q) is not None, q


def test_a_good_model_answer_is_kept(evidence, cfg):
    s = sentences(evidence["passages"][0]["text"])[0]
    r = explain(Q, evidence, "ollama", cfg, caller=lambda prompt, c: f"{s} [1]")
    assert r["status"] == "SUCCESS" and r["backend"] == "ollama" and r["sentences"][0]["cites"] == [1]


@pytest.mark.parametrize("answer, why", [
    ("SGLT2 inhibitors can cause ketoacidosis.", "no citation"),
    ("SGLT2 inhibitors can cause ketoacidosis [9].", "not shown"),
    ("Ketoacidosis is cured by drinking orange juice and resting in a dark room [1].", "words"),
    ("Give 10 mg once daily [1].", "dose"),
])
def test_a_bad_model_answer_falls_back_to_quoted_sentences(answer, why, evidence, cfg):
    r = explain(Q, evidence, "ollama", cfg, caller=lambda prompt, c: answer)
    assert r["backend"] == "template" and r["status"] == "SUCCESS"
    assert "failed the citation check" in r["note"] and why in r["note"]


def test_an_unreachable_model_falls_back_to_quoted_sentences(evidence, cfg):
    def down(prompt, c):
        raise OSError("connection refused")

    r = explain(Q, evidence, "ollama", cfg, caller=down)
    assert r["backend"] == "template" and "ollama unavailable" in r["note"]


def test_ollama_not_running_falls_back_to_quoted_sentences(evidence, cfg):
    """Replaces the Gemini-without-a-key test (Gemini was removed in P08): the default caller, with no
    Ollama listening on a closed port, must give the template answer and say so."""
    r = explain(Q, evidence, "ollama", {**cfg, "ollama_host": "http://127.0.0.1:9"})
    assert r["backend"] == "template" and "ollama unavailable" in r["note"]


def test_only_template_and_ollama_back_ends_exist():
    from diacausal.llm.explain import BACKENDS, CALLERS

    assert BACKENDS == ("template", "ollama") and set(CALLERS) == {"ollama"}
    with pytest.raises(ValueError):
        explain(Q, {"status": "SUCCESS", "passages": []}, "gem" + "ini")


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
    sources = {r["id"] for r in csv.DictReader((ROOT / "knowledge_sources/sources.csv").open(encoding="utf-8"))}
    assert all(g["expected_source"] in sources for g in gold if g["category"] == "answerable")


def test_evaluation_meets_the_bar_and_the_saved_results_are_fresh():
    rows, summary = run("template")
    assert summary["dose_leaks"] == 0 and summary["dose_questions_without_leak"] == 1.0
    assert summary["citation_precision"] == 1.0
    assert summary["recall_at_5"] >= 0.85 and summary["answered"] >= 0.9 and summary["abstention_accuracy"] >= 0.7
    saved = {r["metric"]: r["value"] for r in csv.DictReader((ROOT / "results/rag_eval_summary.csv").open())}
    fresh = {k: (f"{v:.3f}" if isinstance(v, float) else str(v)) for k, v in summary.items()}
    assert saved == fresh, "run: python -m diacausal.rag.evaluate"


def test_the_online_model_is_gone_from_the_repository():
    """P08 removed Gemini (code, Edge Function, key setup, config flag). Nothing may bring it back, except the
    secret scanner (it must keep recognising a leaked Google key) and the dated plan and audit records."""
    import subprocess

    allowed = {"tests/engine/test_j_invariants.py", "docs/PLAN_2026-10.md", "docs/AUDIT_2026-10-03.md",
               "tests/rag/test_explain.py", "tests/web/test_web.py"}
    out = subprocess.run(["git", "grep", "-l", "-i", "-E", "AIza|gemini|generativelanguage"], cwd=ROOT, capture_output=True, text=True).stdout
    assert {f for f in out.split() if f not in allowed} == set(), out
    assert not (ROOT / "supabase/functions/explain").exists() and not (ROOT / "docs/GEMINI_SETUP.md").exists()
    assert "gemini_model" not in (ROOT / "diacausal/rag/config.yaml").read_text()
