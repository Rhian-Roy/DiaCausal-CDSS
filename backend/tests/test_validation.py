"""Requests that break the contract get HTTP 422 and a clear message."""

import pytest

from app.settings import SUPPORTED_PART_TYPES
from conftest import TRACE

SUPPORTED = ", ".join(SUPPORTED_PART_TYPES)


def post(client, body):
    response = client.post("/api/v1/chat", json=body)
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "invalid_request"
    return data


def test_unknown_part_type_is_rejected_clearly(client, chat_body):
    parts = [{"type": "image", "url": "https://example.org/x.png"}]
    data = post(client, chat_body(parts=parts))

    assert data["message"] == (
        f'Part 1 has type "image", which this API does not accept. Supported part types: {SUPPORTED}.'
    )
    # Only the real problem is reported, not the knock-on "text missing" / "url not allowed".
    assert data["problems"] == [{"field": "parts[0].type", "message": data["message"]}]
    assert data["trace_id"] == TRACE


def test_unknown_type_in_second_part_names_part_2(client, chat_body):
    parts = [{"type": "text", "text": "hi"}, {"type": "audio", "data": "..."}]
    data = post(client, chat_body(parts=parts))

    assert data["message"].startswith('Part 2 has type "audio"')


def test_missing_part_type_is_rejected(client, chat_body):
    data = post(client, chat_body(parts=[{"text": "hello"}]))

    assert data["message"] == f'Part 1 has no "type". Supported part types: {SUPPORTED}.'


def test_text_over_8000_characters_is_rejected_clearly(client, chat_body):
    data = post(client, chat_body("a" * 8001))

    assert data["message"] == "Part 1 text is 8,001 characters long; the limit is 8,000."


def test_rejection_does_not_echo_the_long_text(client, chat_body):
    response = client.post("/api/v1/chat", json=chat_body("a" * 8001))

    assert len(response.content) < 1000


def test_wrong_schema_version_is_rejected(client, chat_body):
    data = post(client, chat_body(schema_version="2.0"))

    assert data["message"] == 'schema_version must be "1.0" (got "2.0").'


def test_missing_schema_version_is_rejected(client, chat_body):
    body = chat_body()
    del body["schema_version"]

    assert post(client, body)["message"] == 'schema_version must be "1.0".'


@pytest.mark.parametrize("bad_id", ["", "has space", "a" * 65, "semi;colon", "line\nbreak"])
def test_bad_trace_id_is_rejected(client, chat_body, bad_id):
    data = post(client, chat_body(client_trace_id=bad_id))

    assert data["problems"][0]["field"] == "client_trace_id"
    # It was supplied, so say what is wrong with it, not that it is "required".
    assert data["message"].startswith('client_trace_id must be 1-64 letters, digits, "-" or "_" (got ')
    assert data["trace_id"] is None


def test_bad_trace_id_message_shows_the_value(client, chat_body):
    data = post(client, chat_body(client_trace_id="has space"))

    assert data["message"] == 'client_trace_id must be 1-64 letters, digits, "-" or "_" (got "has space").'


def test_missing_trace_id_is_rejected(client, chat_body):
    body = chat_body()
    del body["client_trace_id"]

    data = post(client, body)
    assert data["problems"][0]["field"] == "client_trace_id"
    assert data["message"] == 'client_trace_id is required: 1-64 letters, digits, "-" or "_".'


def test_empty_parts_list_is_rejected(client, chat_body):
    data = post(client, chat_body(parts=[]))

    assert data["message"] == "parts must contain at least one part."


def test_too_many_parts_are_rejected(client, chat_body):
    parts = [{"type": "text", "text": "x"}] * 21

    assert post(client, chat_body(parts=parts))["message"] == "parts may contain at most 20 parts."


def test_part_that_is_not_an_object_is_rejected(client, chat_body):
    data = post(client, chat_body(parts=["hello"]))

    assert data["message"].startswith("Part 1 must be an object")


def test_unknown_top_level_field_is_rejected(client, chat_body):
    data = post(client, chat_body(patient_name="Ramesh"))

    assert data["message"] == '"patient_name" is not a field this API accepts.'


def test_several_problems_are_all_listed(client):
    data = post(client, {"schema_version": "9", "client_trace_id": TRACE, "parts": []})

    assert len(data["problems"]) == 2
    assert data["message"].endswith('(1 more problem listed in "problems".)')


def test_invalid_json_is_rejected(client):
    response = client.post(
        "/api/v1/chat", content=b'{"schema_version": "1.0",', headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["message"] == "The request body is not valid JSON."
    assert response.json()["trace_id"] is None


@pytest.mark.parametrize(
    "raw",
    [
        b'{"schema_version":"1.0","client_trace_id":"abc12345","parts":[{"type":"\\ud800","text":"x"}]}',
        b'{"schema_version":"\\ud800","client_trace_id":"abc12345","parts":[{"type":"text","text":"x"}]}',
    ],
)
def test_broken_unicode_gets_a_clear_422_not_a_crash(client, raw):
    # "\ud800" is legal JSON but cannot be encoded as UTF-8; echoing it raw used to cause a 500.
    response = client.post("/api/v1/chat", content=raw, headers={"Content-Type": "application/json"})

    assert response.status_code == 422
    assert "\\ud800" in response.json()["message"]


def test_rejection_does_not_echo_a_long_part_type(client, chat_body):
    data = post(client, chat_body(parts=[{"type": "x" * 5000}]))

    assert len(data["message"]) < 200


def test_json_sent_without_the_json_header_gets_told_so(client):
    body = b'{"schema_version":"1.0","client_trace_id":"abc12345","parts":[{"type":"text","text":"x"}]}'
    response = client.post("/api/v1/chat", content=body)  # no Content-Type header

    assert response.status_code == 422
    assert response.json()["message"] == 'Send the body as JSON with the header "Content-Type: application/json".'


def test_non_object_body_is_rejected(client):
    assert post(client, ["not", "an", "object"])["message"].startswith("The request body must be a JSON object")
