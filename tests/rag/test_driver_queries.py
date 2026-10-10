"""P26: each comparison's top driver joins the retrieval as an extra keyword query (knowledge_sources/driver_terms.csv) that only
REORDERS what the question found: it never changes which passages are candidates, and never whether the search abstains."""

import csv
import re
from pathlib import Path

import pytest

from diacausal.rag.ingest.licence_gate import ingest
from diacausal.rag.retrieve import query_processing as qp
from diacausal.rag.retrieve.hybrid import Retriever

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "knowledge_sources" / "corpus"


@pytest.fixture(scope="module")
def retriever():
    return Retriever(ingest())


def test_every_driver_term_is_in_the_corpus_file_its_row_cites():
    rows = list(csv.DictReader((ROOT / "knowledge_sources/driver_terms.csv").open(encoding="utf-8")))
    assert {r["feature"] for r in rows} >= {"egfr", "hba1c", "duration_years"}  # at least the true modifiers of the synthetic cohort
    for r in rows:
        assert r["status"] == "IN-CORPUS", r
        texts = " ".join((CORPUS / f).read_text(encoding="utf-8").lower() for f in re.findall(r"[\w.]+\.txt", r["source"]))
        for term in r["terms"].split(";"):
            assert term.strip() in texts, (r["feature"], term)


def test_add_drivers_is_deterministic_dedups_and_ignores_unknown_features():
    plan = qp.process("Is metformin safe?")
    out = qp.add_drivers(plan, ["egfr", "hba1c", "egfr", "no_such_feature"])
    assert out.driver_queries == ("kidney function renal impairment egfr", "hba1c glycaemic control")
    assert out == qp.add_drivers(plan, ["egfr", "hba1c", "egfr", "no_such_feature"])
    assert out.sub_queries == plan.sub_queries and out.original == plan.original  # the question itself is unchanged
    assert qp.add_drivers(plan, []).driver_queries == ()


@pytest.mark.parametrize("question", ["Can metformin be used with reduced kidney function?", "Can SGLT2 inhibitors cause ketoacidosis?",
                                      "Do DPP-4 inhibitors cause joint pain?", "Is saxagliptin linked to heart failure?"])
def test_drivers_change_only_the_order_of_the_questions_own_passages(retriever, question):
    plain = retriever.search(question, qp.process(question))
    with_drivers = retriever.search(question, qp.add_drivers(qp.process(question), ["egfr", "hba1c"]))
    assert plain["status"] == with_drivers["status"]
    if plain["status"] == "SUCCESS":
        # same candidate pool: every passage shown with drivers is one the question alone could reach (bm25 or vector > 0)
        assert all(p["scores"]["bm25"] > 0 or p["scores"]["vector"] > 0 for p in with_drivers["passages"])


def test_drivers_never_rescue_a_question_the_corpus_cannot_answer(retriever):
    r = retriever.search("zebra-test", qp.add_drivers(qp.process("zebra-test"), ["egfr", "hba1c", "duration_years"]))
    assert r["status"] == "INSUFFICIENT_EVIDENCE"


def test_a_kidney_driver_moves_kidney_passages_up(retriever):
    q = "Can metformin be used in older adults?"
    rank = lambda r: next((i for i, p in enumerate(r["passages"]) if "kidney" in p["text"].lower()), 99)  # noqa: E731
    plain = retriever.search(q, qp.process(q))
    with_driver = retriever.search(q, qp.add_drivers(qp.process(q), ["egfr"]))
    assert rank(with_driver) <= rank(plain)


def test_the_pipeline_adds_the_top_driver_of_each_comparison(monkeypatch):
    from fastapi.testclient import TestClient

    from diacausal.api.main import create_app
    from diacausal.causal_inference.recommend import get_engine
    from diacausal.orchestrator import layers

    seen = {}
    real = layers.query_processing_part

    def spy(ctx, question):
        plan = real(ctx, question)
        seen["queries"], seen["drivers"] = plan.driver_queries, {o: [d.feature for d in rows] for o, rows in ctx.drivers.items()}
        return plan

    monkeypatch.setattr(layers, "query_processing_part", spy)
    monkeypatch.setattr("diacausal.causal_inference.recommend.AUDIT_PATH", Path(__import__("tempfile").mkdtemp()) / "a.jsonl")
    patient = dict(age=52, sex="M", duration_years=5.0, hba1c_pct=8.4, egfr=88.0, bmi=27.0, ascvd=False, heart_failure=False, ckd=False,
                   past_hypo=False, past_dka=False, past_pancreatitis=False, type1=False, on_metformin=True)
    with TestClient(create_app(get_engine())) as c:
        r = c.post("/api/v1/ask", json={"schema_version": "1.0", "request_id": "q26", "patient": patient,
                                        "question": "Can SGLT2 inhibitors cause ketoacidosis?"})
    assert r.status_code == 200
    terms = qp.load_driver_terms()
    expected = tuple(dict.fromkeys(qp.normalise(" ".join(terms[rows[0]])) for rows in seen["drivers"].values() if rows))
    assert seen["queries"] == expected and len(expected) >= 1
