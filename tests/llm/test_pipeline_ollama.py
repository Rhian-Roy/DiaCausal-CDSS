"""The model inside /api/v1/ask: used only when BOTH llm.yaml and the request say ollama; every problem falls back to the template."""

import json
import logging

import pytest
from fastapi.testclient import TestClient
from llm_helpers import evidence_lines, good_draft

from diacausal.api.main import create_app
from diacausal.api.schemas import AnswerCardV1
from diacausal.causal_inference.recommend import get_engine
from diacausal.llm.prompt_builder import estimate_tokens
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


def test_the_prompt_is_built_only_when_the_model_will_be_asked(client, fake, monkeypatch):
    """P22: the prompt builder is a real part of the explanation layer, and it does no work for the template."""
    from diacausal.llm import prompt_builder

    def boom(*a, **k):
        raise AssertionError("a prompt was built although the template writes this answer")

    monkeypatch.setattr(prompt_builder, "build_llm_prompt", boom)
    configure(monkeypatch, fake(lambda p: good_draft(p)), "template")
    assert ask(client, "ollama").status_code == 200  # llm.yaml says template
    configure(monkeypatch, fake(lambda p: good_draft(p)), "ollama")
    assert ask(client, "template").status_code == 200  # the request says template
    assert ask(client, "ollama", question="What dose of sitagliptin should I use?").status_code == 422  # a dose question never reaches it


def test_the_prompt_sent_stays_inside_the_budget_with_at_most_five_passages(client, fake, monkeypatch):
    server = fake(lambda p: good_draft(p))
    configure(monkeypatch, server, "ollama")
    assert ask(client, "ollama").status_code == 200
    prompt = server.requests[0]["prompt"]
    assert estimate_tokens(prompt) <= 1900 and 1 <= len(evidence_lines(prompt)) <= 5


def test_a_prompt_that_cannot_be_built_means_no_call_and_the_template_answers(client, fake, monkeypatch):
    from diacausal.llm import prompt_builder

    server = fake(lambda p: good_draft(p))
    configure(monkeypatch, server, "ollama")
    real = prompt_builder.prompt_settings()
    monkeypatch.setattr(prompt_builder, "prompt_settings", lambda *a, **k: {**real, "prompt_budget_tokens": 100})
    r = ask(client, "ollama")
    assert r.status_code == 200 and AnswerCardV1.model_validate(r.json()).mode == "template" and server.requests == []


# ── the seven output checks inside /api/v1/ask (P23) ─────────────────────────────────────────────────────────────
KIDNEY = {**PATIENT, "egfr": 40.0, "ckd": True, "sex": "F", "age": 60}  # rule R01 removes SGLT2i


def tweaked(prompt, claims=1, **over):
    draft = json.loads(good_draft(prompt, claims=claims))
    draft.update(over)
    return json.dumps(draft)


def ask_with(client, patient=PATIENT, question=QUESTION, rid="g1"):
    body = {"schema_version": "1.0", "request_id": rid, "patient": patient, "question": question, "mode": "ollama"}
    return client.post("/api/v1/ask", json=body)


@pytest.mark.parametrize("name,over,patient,checks,reason", [
    ("an invented number", {"limitations": "The estimate is -9.99 points."}, PATIENT, ["numbers"], "GUARD_NUMBERS"),
    ("dose text", {"limitations": "Take it twice daily."}, PATIENT, ["dose_threshold"], "GUARD_DOSE_THRESHOLD"),
    ("a threshold", {"limitations": "It is contraindicated if the kidneys are weak."}, PATIENT, ["dose_threshold"], "GUARD_DOSE_THRESHOLD"),
    ("praise for an excluded drug", {"limitations": "SGLT2 inhibitors are a good choice for this patient."}, KIDNEY, ["excluded_option"], "GUARD_EXCLUDED_OPTION"),
    ("causal wording about a driver", {"limitations": "A higher BMI causes the larger effect."}, PATIENT, ["identifier_causal"], "GUARD_IDENTIFIER_CAUSAL"),
    ("an identifier", {"limitations": "Write to someone@example.com about this."}, PATIENT, ["identifier_causal"], "GUARD_IDENTIFIER_CAUSAL"),
    ("a fake chunk ID", {"evidence_summary": [{"claim": "SGLT2 inhibitors can cause ketoacidosis.", "chunk_ids": ["S99-00-00"]}]}, PATIENT, ["citations"], "GUARD_CITATIONS"),
])
def test_a_bad_draft_gives_a_template_card_that_records_the_failed_checks(client, fake, monkeypatch, name, over, patient, checks, reason):
    configure(monkeypatch, fake(lambda p: tweaked(p, **over)), "ollama")
    r = ask_with(client, patient)
    card = AnswerCardV1.model_validate(r.json())
    assert r.status_code == 200, name
    assert card.mode == "template" and card.fallback_used and card.failed_checks == checks and card.fallback_reason == reason and card.claims
    assert card.question_context is None and card.limitations is None  # nothing the model wrote is on the card


def test_a_good_draft_is_used_and_records_no_fallback(client, fake, monkeypatch):
    configure(monkeypatch, fake(lambda p: tweaked(p, claims=2, limitations="Only the retrieved passages were used.")), "ollama")
    card = AnswerCardV1.model_validate(ask_with(client).json())
    assert card.mode == "ollama" and not card.fallback_used and card.failed_checks == [] and card.fallback_reason is None
    assert card.limitations == "Only the retrieved passages were used." and card.question_context and len(card.claims) == 2


def test_one_bad_claim_is_dropped_and_the_card_keeps_the_rest(client, fake, monkeypatch):
    def reply(prompt):
        draft = json.loads(good_draft(prompt, claims=2))
        draft["evidence_summary"].append({"claim": "An invented claim.", "chunk_ids": ["S99-00-00"]})
        return json.dumps(draft)

    configure(monkeypatch, fake(reply), "ollama")
    card = AnswerCardV1.model_validate(ask_with(client).json())
    assert card.mode == "ollama" and not card.fallback_used and card.dropped_claims == 1 and len(card.claims) == 2


@pytest.mark.parametrize("url,reason", [("http://127.0.0.1:9", "UNREACHABLE")])
def test_a_model_that_cannot_be_reached_records_a_fallback_with_no_failed_check(client, monkeypatch, url, reason):
    real = ollama.load_llm_config()
    monkeypatch.setattr(ollama, "load_llm_config", lambda *a, **k: {**real, "ollama_url": url, "provider": "ollama", "timeout_seconds": 2})
    card = AnswerCardV1.model_validate(ask_with(client).json())
    assert card.mode == "template" and card.fallback_used and card.failed_checks == [] and card.fallback_reason == reason


def test_a_slow_model_records_a_timeout(client, fake, monkeypatch):
    server = fake({"sleep": 1.5, "then": lambda p: good_draft(p)})
    real = ollama.load_llm_config()
    monkeypatch.setattr(ollama, "load_llm_config", lambda *a, **k: {**real, "ollama_url": server.url, "provider": "ollama", "timeout_seconds": 0.4})
    card = AnswerCardV1.model_validate(ask_with(client).json())
    assert card.mode == "template" and card.fallback_used and card.fallback_reason == "TIMEOUT" and card.failed_checks == []


def test_the_trace_names_the_failed_checks_and_never_the_draft(client, fake, monkeypatch, caplog):
    configure(monkeypatch, fake(lambda p: tweaked(p, limitations=f"The estimate is -9.99 points. {CANARY}")), "ollama")
    caplog.set_level(logging.DEBUG)
    ask_with(client, rid="g2")
    logged = " ".join(f"{x.getMessage()} {x.args}" for x in caplog.records)
    assert "[g2] output guards: model draft FALLBACK checks=numbers reason=GUARD_NUMBERS dropped=0" in logged
    assert CANARY not in logged and "-9.99" not in logged


def test_a_blocked_identifier_is_recorded_as_a_block_and_is_not_in_the_log_or_the_card(client, fake, monkeypatch, caplog):
    configure(monkeypatch, fake(lambda p: tweaked(p, limitations="Patient Aadhaar 726018159082 was checked.")), "ollama")
    caplog.set_level(logging.DEBUG)
    r = ask_with(client, rid="g3")
    logged = " ".join(f"{x.getMessage()} {x.args}" for x in caplog.records)
    assert "726018159082" not in r.text and "726018159082" not in logged and "model draft BLOCK" in logged
    assert AnswerCardV1.model_validate(r.json()).mode == "template"


def test_the_template_alone_runs_no_output_checks_on_a_model(client, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("no model was asked, so there is no draft to check")

    monkeypatch.setattr("diacausal.llm.answer.run_output_guards", boom)
    card = AnswerCardV1.model_validate(ask(client, "template").json())
    assert card.mode == "template" and card.fallback_used is False and card.failed_checks == []
