"""The backend log carries the browser's trace ID and never the message text."""

import logging
import re

import pytest

from app.pipeline.blocklist import RULES_VERSION
from app.tracing import log
from conftest import TRACE


@pytest.fixture
def app_logs(caplog):
    caplog.set_level(logging.INFO, logger="diacausal")
    return caplog


def test_app_logger_is_set_to_print_info_lines(client):
    # The other tests use caplog.set_level, which would hide a missing log.setLevel(INFO)
    # in tracing.py; without it the uvicorn terminal would show no [trace-id] lines at all.
    assert log.getEffectiveLevel() == logging.INFO


def test_every_log_line_for_a_request_carries_its_trace_id(client, chat_body, app_logs):
    client.post("/api/v1/chat", json=chat_body())

    records = [r for r in app_logs.records if r.name == "diacausal"]
    assert records, "expected the request to be logged"
    assert {r.trace_id for r in records} == {TRACE}


def test_log_shows_request_each_stage_and_reply(client, chat_body, app_logs):
    client.post("/api/v1/chat", json=chat_body("hello"))

    messages = [r.getMessage() for r in app_logs.records if r.name == "diacausal"]
    # Each stage line ends with how long it took, e.g. "backend_guard: passed in 0.4 ms".
    timed = re.compile(r"^(\w+): (passed|skipped|blocked) in \d+\.\d ms$")
    assert [timed.sub(r"\1: \2", line) for line in messages] == [
        "chat request received: 1 part(s), 5 characters",
        f"guard rules version {RULES_VERSION}",
        "backend_guard: passed",
        "clinical_guardrails: skipped",
        "causal_engine: skipped",
        "rag_retrieval: skipped",
        "llm_explanation: skipped",
        "output_guard: passed",
        "reply sent: outcome=answered",
    ]
    assert sum(bool(timed.match(line)) for line in messages) == 6  # one line per stage


def test_printed_log_line_starts_with_the_trace_id(client, chat_body, app_logs):
    client.post("/api/v1/chat", json=chat_body())

    handler = next(h for h in log.handlers if h.formatter is not None)
    line = handler.format(app_logs.records[0])
    assert f"[{TRACE}] chat request received" in line


def test_message_text_is_never_logged(client, chat_body, app_logs):
    client.post("/api/v1/chat", json=chat_body("Patient Ramesh Kumar, HbA1c 8.4"))

    assert "Ramesh" not in app_logs.text


def test_rejected_request_is_logged_with_its_trace_id(client, chat_body, app_logs):
    client.post("/api/v1/chat", json=chat_body("a" * 8001))

    warning = next(r for r in app_logs.records if r.levelno == logging.WARNING)
    assert warning.trace_id == TRACE
    assert warning.getMessage().startswith("request rejected (422): Part 1 text is 8,001")


def test_hostile_field_name_cannot_forge_a_log_line(client, chat_body, app_logs):
    client.post("/api/v1/chat", json=chat_body(**{"x\nFAKE LOG LINE": 1}))

    warning = next(r for r in app_logs.records if r.levelno == logging.WARNING)
    assert "\n" not in warning.getMessage()


def test_logs_outside_a_request_use_a_dash(app_logs):
    log.info("startup")

    assert app_logs.records[-1].trace_id == "-"
