"""The shared guard rules (shared/guard_rules/) on the server: every example case,
the same answer as reference_guard.py, and the right notice code from the API."""

import importlib.util
import json
import logging

import pytest

from app.pipeline import blocklist
from app.pipeline.blocklist import RULES_FILE

EXAMPLES = json.loads((RULES_FILE.parent / "examples.v1.json").read_text(encoding="utf-8"))["cases"]


def _reference():
    spec = importlib.util.spec_from_file_location("reference_guard", RULES_FILE.parent / "reference_guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REFERENCE = _reference()


def test_there_are_47_example_cases():
    assert len(EXAMPLES) == 47


@pytest.mark.parametrize("case", EXAMPLES, ids=[c["id"] for c in EXAMPLES])
def test_every_example_case(case):
    assert blocklist.check(case["text"]) == case["expect"]


@pytest.mark.parametrize("case", EXAMPLES, ids=[c["id"] for c in EXAMPLES])
def test_same_answer_as_the_reference_guard(case):
    assert blocklist.check(case["text"]) == REFERENCE.check(case["text"])


@pytest.mark.parametrize(
    "text",
    [
        "History of anal fissure, HbA1c 8%",
        "not pregnant, HbA1c 8.1%",
        "History of seizures as a child",
        "sugar 38 mg/dL two years ago, now stable",
        "past DKA in 2019, now on metformin",
        "no seizure today",
    ],
)
def test_extra_cases_agree_with_the_reference(text):
    assert blocklist.check(text) == REFERENCE.check(text)


def test_devanagari_word_stays_whole():
    assert blocklist.words("मधुमेह रोगी") == ["मधुमेह", "रोगी"]


def test_apostrophe_keeps_a_word_whole():
    assert blocklist.words("Fournier's gangrene") == ["fournier's", "gangrene"]


def test_whole_words_only():
    assert blocklist.check("Please assess renal function") == "pass"
    assert blocklist.check("you ASS.") == "block:language"


def test_medical_allowlist_wins(monkeypatch):
    monkeypatch.setattr(blocklist, "BLOCKED_TERMS", blocklist.BLOCKED_TERMS | {"urine"})
    assert blocklist.find_blocked_term("urine ketones positive") is None


def test_rules_file_is_the_one_in_shared():
    assert RULES_FILE.parts[-3:] == ("shared", "guard_rules", "rules.v1.json")
    assert blocklist.RULES_VERSION == blocklist.RULES["version"]


# ── through the API ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "code", "topic"),
    [
        ("Patient Aadhaar 726018159082, HbA1c 8.4%", "identifier", None),
        ("what bullshit answer is this", "language", None),
        ("CBG 45 mg/dL, sweating", "emergency", None),
        ("She is pregnant, 28 weeks, on metformin", "out_of_scope", "pregnancy"),
        ("Should I start insulin instead?", "out_of_scope", "insulin_start"),
    ],
)
def test_api_blocks_with_the_reason_code(client, chat_body, text, code, topic):
    reply = client.post("/api/v1/chat", json=chat_body(text)).json()

    assert reply["outcome"] == "blocked"
    assert reply["reason_code"] == code
    assert reply["scope_topic"] == topic
    assert reply["parts"] == []
    assert reply["stages"][0]["status"] == "blocked"
    assert all(stage["status"] == "skipped" for stage in reply["stages"][1:])


def test_emergency_reply_has_no_treatment_content(client, chat_body):
    reply = client.post("/api/v1/chat", json=chat_body("Patient unconscious in OPD, sugar 38")).json()

    assert reply["parts"] == []
    assert reply["blocked_reason"] == "This may be an emergency. Follow your emergency protocol."


def test_out_of_scope_reply_names_the_reason(client, chat_body):
    reply = client.post("/api/v1/chat", json=chat_body("Type 1 diabetes, 24 y")).json()

    assert "type 1 diabetes" in reply["blocked_reason"]


def test_a_passing_message_has_no_reason_code(client, chat_body):
    reply = client.post("/api/v1/chat", json=chat_body("HbA1c 8.4% on metformin, eGFR 62")).json()

    assert reply["outcome"] == "answered"
    assert reply["reason_code"] is None


def test_matched_word_is_never_echoed_or_logged(client, chat_body, caplog):
    caplog.set_level(logging.INFO, logger="diacausal")
    reply = client.post("/api/v1/chat", json=chat_body("what bullshit answer is this")).json()

    assert "bullshit" not in json.dumps(reply)
    assert "bullshit" not in caplog.text


def test_identifier_is_never_echoed_or_logged(client, chat_body, caplog):
    caplog.set_level(logging.INFO, logger="diacausal")
    reply = client.post("/api/v1/chat", json=chat_body("Mobile 9876543210, HbA1c 9%")).json()

    assert "9876543210" not in json.dumps(reply)
    assert "9876543210" not in caplog.text


def test_rules_version_is_logged_with_the_trace_id(client, chat_body, caplog):
    caplog.set_level(logging.INFO, logger="diacausal")
    client.post("/api/v1/chat", json=chat_body())

    lines = [r for r in caplog.records if r.getMessage() == f"guard rules version {blocklist.RULES_VERSION}"]
    assert len(lines) == 1 and lines[0].trace_id == "abc12345"
