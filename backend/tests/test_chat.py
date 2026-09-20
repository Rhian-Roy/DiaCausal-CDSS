"""The happy path: a valid message gets the dummy reply and all six stages."""

from app.settings import INTENDED_USE, MAX_TEXT_CHARS
from conftest import PATIENT, TRACE

EXPECTED_STAGES = [
    ("backend_guard", "passed"),
    ("clinical_guardrails", "passed"),
    ("causal_engine", "skipped"),
    ("rag_retrieval", "skipped"),
    ("llm_explanation", "skipped"),
    ("output_guard", "passed"),
]


def test_valid_message_gets_dummy_reply(client, chat_body):
    response = client.post("/api/v1/chat", json=chat_body())

    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == "1.0"
    assert data["trace_id"] == TRACE
    assert data["outcome"] == "answered"
    assert data["blocked_reason"] is None
    assert data["intended_use"] == INTENDED_USE
    # The reply carries the three options from the clinical guardrails, then the text.
    assert [part["type"] for part in data["parts"]] == ["options", "text"]
    assert data["parts"][1]["text"].startswith("Dummy reply")


def test_reply_lists_all_six_stages_in_order(client, chat_body):
    data = client.post("/api/v1/chat", json=chat_body()).json()

    assert [(s["name"], s["status"]) for s in data["stages"]] == EXPECTED_STAGES
    skipped = [s for s in data["stages"] if s["status"] == "skipped"]
    assert all(s["detail"] == "Not built yet." for s in skipped)


def test_trace_id_comes_back_in_body_and_header(client, chat_body):
    response = client.post("/api/v1/chat", json=chat_body(client_trace_id="7f3a9c01"))

    assert response.json()["trace_id"] == "7f3a9c01"
    assert response.headers["X-Trace-Id"] == "7f3a9c01"


def test_reply_does_not_echo_the_message(client, chat_body):
    data = client.post("/api/v1/chat", json=chat_body("Patient Ramesh, 58, HbA1c 8.4")).json()

    reply_text = next(part["text"] for part in data["parts"] if part["type"] == "text")
    assert "Ramesh" not in reply_text


def test_several_text_parts_are_accepted(client, chat_body):
    parts = [{"type": "text", "text": "HbA1c 8.4%."}, {"type": "text", "text": "What next?"}, PATIENT]
    response = client.post("/api/v1/chat", json=chat_body(parts=parts))

    assert response.status_code == 200
    assert response.json()["outcome"] == "answered"


def test_text_of_exactly_the_limit_is_accepted(client, chat_body):
    response = client.post("/api/v1/chat", json=chat_body("a" * MAX_TEXT_CHARS))

    assert response.status_code == 200


def test_limit_counts_characters_not_bytes(client, chat_body):
    # Devanagari letters take 3 bytes each in UTF-8, but count as 1 character.
    response = client.post("/api/v1/chat", json=chat_body("म" * MAX_TEXT_CHARS))

    assert response.status_code == 200
