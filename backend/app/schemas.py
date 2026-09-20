"""The API contract: exactly what JSON may come in and what goes out.

Pydantic checks every request against these models *before* our code runs. Anything
that does not fit is rejected with HTTP 422 and a plain-English message (see errors.py).
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.settings import INTENDED_USE, MAX_PARTS, MAX_TEXT_CHARS, TRACE_ID_PATTERN


class StrictModel(BaseModel):
    """Base for every API model: unknown fields are rejected, never silently dropped."""

    model_config = ConfigDict(extra="forbid")


# ── Request ──────────────────────────────────────────────────────────────────


class TextPart(StrictModel):
    type: Literal["text"]
    text: str = Field(max_length=MAX_TEXT_CHARS)


# A message is a list of typed parts so new kinds of input can be added later
# without changing the shape of the request. Today the only type is "text".
# To add one (say "image"): define ImagePart above, then change this line to
#     Part = Annotated[TextPart | ImagePart, Field(discriminator="type")]
# and add "image" to SUPPORTED_PART_TYPES in settings.py.
Part = TextPart


class ChatRequest(StrictModel):
    schema_version: Literal["1.0"]
    client_trace_id: str = Field(pattern=TRACE_ID_PATTERN)
    parts: list[Part] = Field(min_length=1, max_length=MAX_PARTS)


# ── Response ─────────────────────────────────────────────────────────────────


class StageName(StrEnum):
    """Every stage of the pipeline, in the order they run."""

    BACKEND_GUARD = "backend_guard"
    CLINICAL_GUARDRAILS = "clinical_guardrails"
    CAUSAL_ENGINE = "causal_engine"
    RAG_RETRIEVAL = "rag_retrieval"
    LLM_EXPLANATION = "llm_explanation"
    OUTPUT_GUARD = "output_guard"


class StageStatus(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class StageResult(StrictModel):
    name: StageName
    status: StageStatus
    detail: str


class Outcome(StrEnum):
    ANSWERED = "answered"
    BLOCKED = "blocked"


class ReasonCode(StrEnum):
    """Why backend_guard blocked a message; the page shows the matching notice (designs 09-12)."""

    IDENTIFIER = "identifier"  # notice 09: a patient identifier (Aadhaar, phone, PAN, email, ABHA)
    OUT_OF_SCOPE = "out_of_scope"  # notice 10: see scope_topic
    EMERGENCY = "emergency"  # notice 11: no treatment content at all
    LANGUAGE = "language"  # notice 12: foul language


# Which out-of-scope topic (only with reason_code "out_of_scope").
ScopeTopic = Literal["type_1", "pregnancy", "under_18", "dka_hhs", "insulin_start"]


class ChatResponse(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    trace_id: str
    outcome: Outcome
    parts: list[Part]  # the reply; empty when the message was blocked
    blocked_reason: str | None = None
    reason_code: ReasonCode | None = None  # set when backend_guard blocked by a guard rule
    scope_topic: ScopeTopic | None = None
    stages: list[StageResult]
    intended_use: str = INTENDED_USE
    request_id: str | None = None  # server-generated UUID, the row in audit_log


class HealthResponse(StrictModel):
    status: Literal["ok"] = "ok"
    schema_version: Literal["1.0"] = "1.0"


class Problem(StrictModel):
    field: str
    message: str


class ErrorResponse(StrictModel):
    """What a rejected request (HTTP 422) gets back."""

    error: Literal["invalid_request"] = "invalid_request"
    message: str
    problems: list[Problem]
    trace_id: str | None = None
