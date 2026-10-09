"""The model inside /api/v1/ask: used only when BOTH llm.yaml and the request say ollama; every problem falls back to the template."""

import json
import logging

import pytest
from fastapi.testclient import TestClient
from llm_helpers import evidence_lines, good_draft

from diacausal.api.main import create_app
from diacausal.api.schemas import AnswerCardV1
from diacausal.causal_inference.recommend import get_engine
from diacausal.llm.providers import ollama

PATIENT = dict(age=52, sex="M", duration_years=5.0, hba1c_pct=8.4, egfr=88.0, bmi=27.0, ascvd=False, heart_failure=False, ckd=False, past_hypo=False,
               past_dka=False, past_pancreatitis=False, type1=False, on_metformin=True)
QUESTION = "Can SGLT2 inhibitors cause ketoacidosis?"
CANARY = "ZEBRA-CANARY-7731"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("diacausal.causal_inference.recommend.AUDIT_PATH", tmp_path / "audit.jsonl")
    with TestClient(create_app(get_engine())) as c:
        yield c


def ask(client, mode, rid="m1", question=QUESTION):
    return client.post("/api/v1/ask", json={"schema_version": "1.0", "request_id": rid, "patient": PATIENT, "question": question, "mode": mode})


def configure(monkeypatch, server, provider):
    real = ollama.load_llm_config()
    monkeypatch.setattr(ollama, "load_llm_config", lambda *a, **k: {**real, "ollama_url": server.url, "provider": provider})


def test_with_the_default_provider_a_request_for_the_model_never_reaches_the_server(client, fake, monkeypatch):
    server = fake(lambda p: good_draft(p))
    configure(monkeypatch, server, "template")
    r = ask(client, "ollama")
    assert r.status_code == 200 and AnswerCardV1.model_validate(r.json()).mode == "template" and server.requests == []


def test_with_the_model_switched_on_but_not_asked_for_the_server_is_not_called(client, fake, monkeypatch):
    server = fake(lambda p: good_draft(p))
    configure(monkeypatch, server, "ollama")
    assert AnswerCardV1.model_validate(ask(client, "template").json()).mode == "template" and server.requests == []


def test_when_both_say_ollama_the_model_writes_the_claims_and_the_numbers_still_come_from_the_causal_output(client, fake, monkeypatch):
    server = fake(lambda p: good_draft(p, claims=2))
    configure(monkeypatch, server, "ollama")
    card = AnswerCardV1.model_validate(ask(client, "ollama").json())
    assert len(server.requests) == 1 and card.mode == "ollama" and card.claims and all(c.citations for c in card.claims)
    prompt = server.requests[0]["prompt"]
    assert "CAUSAL_OUTPUT:" in prompt and "EXCLUDED_BY_RULES: none" in prompt and QUESTION in prompt
    assert all(e.hba1c_change is not None for e in card.effects if e.status == "ESTIMATED")  # the effects table is from the engine, not the model


def test_the_prompt_sent_to_the_model_holds_no_patient_identifier_and_the_excluded_options_with_their_rule(client, fake, monkeypatch):
    server = fake(lambda p: good_draft(p))
    configure(monkeypatch, server, "ollama")
    body = {"schema_version": "1.0", "request_id": "m2", "question": "Is a DPP-4 inhibitor safe?", "mode": "ollama",
            "patient": {**PATIENT, "egfr": 40.0, "ckd": True, "sex": "F", "age": 60}}
    assert client.post("/api/v1/ask", json=body).status_code == 200
    prompt = server.requests[0]["prompt"]
    assert "SGLT2i (R01)" in prompt and "60 y, F" in prompt and "request_id" not in prompt and "m2" not in prompt


@pytest.mark.parametrize("spec", [{"status": 500}, {"raw": b"nonsense"}, {"text": "not json"}, {"text": "{}"}])
def test_any_failure_still_gives_a_valid_card_written_by_the_template(client, fake, monkeypatch, spec):
    configure(monkeypatch, fake(spec), "ollama")
    r = ask(client, "ollama")
    card = AnswerCardV1.model_validate(r.json())
    assert r.status_code == 200 and card.mode == "template" and card.claims


def test_a_model_that_is_not_running_gives_a_template_card(client, monkeypatch):
    real = ollama.load_llm_config()
    monkeypatch.setattr(ollama, "load_llm_config", lambda *a, **k: {**real, "ollama_url": "http://127.0.0.1:9", "provider": "ollama", "timeout_seconds": 2})
    assert AnswerCardV1.model_validate(ask(client, "ollama").json()).mode == "template"


def test_a_dose_question_never_reaches_the_model(client, fake, monkeypatch):
    server = fake(lambda p: good_draft(p))
    configure(monkeypatch, server, "ollama")
    assert ask(client, "ollama", question="What dose of sitagliptin should I use?").status_code == 422 and server.requests == []


def test_a_question_without_evidence_never_reaches_the_model(client, fake, monkeypatch):
    server = fake(lambda p: good_draft(p))
    configure(monkeypatch, server, "ollama")
    ask(client, "ollama", question="zebra-test")
    assert server.requests == []


def test_nothing_the_model_wrote_is_logged_or_audited(client, fake, monkeypatch, caplog, tmp_path):
    bad = json.dumps({"question_context": CANARY, "evidence_summary": [{"claim": CANARY, "chunk_ids": ["S99-00-00"]}], "limitations": CANARY})
    configure(monkeypatch, fake(lambda p: bad), "ollama")
    caplog.set_level(logging.DEBUG)
    r = ask(client, "ollama", rid="m3")
    logged = " ".join(f"{x.getMessage()} {x.args}" for x in caplog.records)
    assert CANARY not in r.text and CANARY not in logged and CANARY not in (tmp_path / "audit.jsonl").read_text()
    assert "[m3] passed explanation layer" in logged


def test_the_evidence_lines_of_the_prompt_are_exactly_the_passages_the_card_can_cite(client, fake, monkeypatch):
    server = fake(lambda p: good_draft(p, claims=3))
    configure(monkeypatch, server, "ollama")
    card = AnswerCardV1.model_validate(ask(client, "ollama").json())
    shown = {cid for cid, _ in evidence_lines(server.requests[0]["prompt"])}
    assert {c.chunk_id for claim in card.claims for c in claim.citations} <= shown
