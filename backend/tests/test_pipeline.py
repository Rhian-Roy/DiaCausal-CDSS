"""The guards: what they block, and what the rest of the pipeline does then."""

import pytest

from app.pipeline import STAGE_ORDER, output_guard
from app.pipeline.blocklist import find_blocked_term
from app.pipeline.context import PipelineContext
from app.schemas import StageStatus, TextPart


def test_stage_order_matches_the_contract():
    assert STAGE_ORDER == [
        "backend_guard",
        "clinical_guardrails",
        "causal_engine",
        "rag_retrieval",
        "llm_explanation",
        "output_guard",
    ]


@pytest.mark.parametrize("text", ["", "   ", "\n\t  \n"])
def test_empty_message_is_blocked_by_backend_guard(client, chat_body, text):
    response = client.post("/api/v1/chat", json=chat_body(text))

    assert response.status_code == 200
    data = response.json()
    assert data["outcome"] == "blocked"
    assert data["blocked_reason"] == "The message is empty."
    assert data["parts"] == []
    first, *later_stages = data["stages"]
    assert first == {
        "name": "backend_guard",
        "status": "blocked",
        "detail": "The message is empty.",
        "duration_ms": first["duration_ms"],
    }
    assert isinstance(first["duration_ms"], float) and 0 <= first["duration_ms"] < 5000
    assert all(stage["duration_ms"] >= 0 for stage in later_stages)
    later = data["stages"][1:]
    assert [s["status"] for s in later] == ["skipped"] * 5
    assert all(s["detail"] == "Not run: an earlier stage blocked the message." for s in later)


def test_blocked_word_is_blocked_without_repeating_it(client, chat_body, monkeypatch):
    monkeypatch.setattr("app.pipeline.blocklist.BLOCKED_TERMS", frozenset({"rudeword"}))

    data = client.post("/api/v1/chat", json=chat_body("You RudeWord, what next?")).json()

    assert data["outcome"] == "blocked"
    assert data["stages"][0]["status"] == "blocked"
    assert "rudeword" not in str(data).casefold()


def test_blocklist_matches_whole_words_only(monkeypatch):
    monkeypatch.setattr("app.pipeline.blocklist.BLOCKED_TERMS", frozenset({"ass"}))

    assert find_blocked_term("Please assess renal function") is None
    assert find_blocked_term("you ASS.") == "ass"


def test_ordinary_clinical_question_has_no_blocked_word():
    assert find_blocked_term("any ordinary clinical question") is None


def test_output_guard_withholds_an_empty_reply():
    ctx = PipelineContext(trace_id="t", parts=[TextPart(type="text", text="hi")], reply_parts=[])

    result = output_guard.run(ctx)

    assert result.status is StageStatus.BLOCKED
    assert ctx.blocked_reason == "The reply was empty, so it was withheld."


def test_reply_withheld_by_output_guard_is_not_sent(client, chat_body, monkeypatch):
    # "dummy" appears in the dummy reply, so blocking it makes output_guard withhold the reply.
    monkeypatch.setattr("app.pipeline.blocklist.BLOCKED_TERMS", frozenset({"dummy"}))

    data = client.post("/api/v1/chat", json=chat_body("hello")).json()

    assert data["outcome"] == "blocked"
    assert data["parts"] == []
    assert data["blocked_reason"] == "The reply did not pass the output check, so it was withheld."
    assert data["stages"][0]["status"] == "passed"
    assert data["stages"][-1]["status"] == "blocked"


def test_output_guard_withholds_a_whitespace_only_reply():
    ctx = PipelineContext(
        trace_id="t",
        parts=[TextPart(type="text", text="hi")],
        reply_parts=[TextPart(type="text", text=" \n\t ")],
    )

    assert output_guard.run(ctx).status is StageStatus.BLOCKED


def test_output_guard_withholds_a_reply_with_a_blocked_word(monkeypatch):
    monkeypatch.setattr("app.pipeline.blocklist.BLOCKED_TERMS", frozenset({"rudeword"}))
    ctx = PipelineContext(
        trace_id="t",
        parts=[TextPart(type="text", text="hi")],
        reply_parts=[TextPart(type="text", text="a rudeword reply")],
    )

    assert output_guard.run(ctx).status is StageStatus.BLOCKED


def test_output_guard_passes_a_normal_reply():
    ctx = PipelineContext(
        trace_id="t",
        parts=[TextPart(type="text", text="hi")],
        reply_parts=[TextPart(type="text", text="A normal reply.")],
    )

    assert output_guard.run(ctx).status is StageStatus.PASSED
    assert ctx.blocked_reason is None


def test_every_stage_reports_how_long_it_took(client, chat_body, monkeypatch):
    import time

    from app.pipeline import causal_engine

    def slow(ctx):
        time.sleep(0.02)
        return not_built_yet(causal_engine.NAME)

    from app.pipeline.context import not_built_yet

    monkeypatch.setattr(causal_engine, "run", slow)
    stages = client.post("/api/v1/chat", json=chat_body()).json()["stages"]

    assert all(stage["duration_ms"] >= 0 for stage in stages)
    slow_stage = next(stage for stage in stages if stage["name"] == "causal_engine")
    assert slow_stage["duration_ms"] >= 20  # the sleep really was measured
