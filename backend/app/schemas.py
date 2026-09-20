"""The API contract: exactly what JSON may come in and what goes out.

Pydantic checks every request against these models *before* our code runs. Anything
that does not fit is rejected with HTTP 422 and a plain-English message (see errors.py).
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.patient_ranges import RANGES
from app.settings import INTENDED_USE, MAX_PARTS, MAX_TEXT_CHARS, TRACE_ID_PATTERN


class StrictModel(BaseModel):
    """Base for every API model: unknown fields are rejected, never silently dropped."""

    model_config = ConfigDict(extra="forbid")


# ── Request ──────────────────────────────────────────────────────────────────


class TextPart(StrictModel):
    type: Literal["text"]
    text: str = Field(max_length=MAX_TEXT_CHARS)


def _limits(field: str) -> dict:
    """The plausibility range for one field, as Pydantic wants it (app/patient_ranges.py)."""
    low, high, *_ = RANGES[field]
    return {"ge": low, "le": high}


class PatientPart(StrictModel):
    """The patient details from the panel (design/v1/13-16). Every field is optional:
    the panel starts empty, and the clinical guardrails decide what they need.

    Values are structured, never parsed out of the doctor's sentence, and never logged.
    """

    type: Literal["patient"]
    age_years: int | None = Field(default=None, **_limits("age_years"))
    diabetes_duration_years: float | None = Field(default=None, **_limits("diabetes_duration_years"))
    hba1c_percent: float | None = Field(default=None, **_limits("hba1c_percent"))
    egfr_ml_min_1_73m2: float | None = Field(default=None, **_limits("egfr_ml_min_1_73m2"))
    bmi_kg_m2: float | None = Field(default=None, **_limits("bmi_kg_m2"))
    established_ascvd: bool | None = None  # established atherosclerotic cardiovascular disease
    ckd: bool | None = None
    heart_failure: bool | None = None
    past_dka: bool | None = None  # needed by the SGLT2 inhibitor rules in clinical/guardrails.v1.yaml
    recurrent_genital_or_urinary_infection: bool | None = None
    past_pancreatitis: bool | None = None  # needed by the DPP-4 inhibitor rules
    past_hypoglycaemia: Literal["none", "mild", "severe"] | None = None
    budget_inr_per_month: int | None = Field(default=None, **_limits("budget_inr_per_month"))

    def filled_fields(self) -> list[str]:
        """Which fields were filled in — safe to log; the values are not."""
        return [name for name, value in self.model_dump(exclude={"type"}).items() if value is not None]


class OptionStatus(StrEnum):
    """What the clinical guardrails say about one option, before any ranking."""

    SAFE_TO_CONSIDER = "safe_to_consider"
    CHECK_FIRST = "check_first"
    DO_NOT_USE = "do_not_use"


class OptionResult(StrictModel):
    """One of the three add-on options. Later stages add their own fields here."""

    option: Literal["sglt2i", "dpp4i", "sulfonylurea"]
    name: str  # e.g. "SGLT2 inhibitor"
    status: OptionStatus
    reasons: list[str] = []  # each reason is a sentence from the cited rules table
    sources: list[str] = []  # the citation behind each reason
    notes: list[str] = []  # "info" rules: relevant, but not a restriction
    rule_ids: list[str] = []  # which rules fired, for the audit trail


class OptionsPart(StrictModel):
    """A reply part carrying the three options and what the guardrails made of them."""

    type: Literal["options"]
    options: list[OptionResult]
    rules_version: str
    draft_warning: str | None = None  # set while the table is not clinically reviewed


# A message is a list of typed parts, so new kinds of input can be added later without
# changing the shape of the request. The "type" field picks the model (a tagged union).
# To add one (say "image"): define ImagePart above, add it to this union, and add the
# name to SUPPORTED_PART_TYPES in settings.py.
Part = Annotated[TextPart | PatientPart, Field(discriminator="type")]


class ChatRequest(StrictModel):
    schema_version: Literal["1.0"]
    client_trace_id: str = Field(pattern=TRACE_ID_PATTERN)
    parts: list[Part] = Field(min_length=1, max_length=MAX_PARTS)

    @model_validator(mode="after")
    def at_most_one_patient_part(self) -> Self:
        if sum(isinstance(part, PatientPart) for part in self.parts) > 1:
            raise ValueError("one patient part")
        return self


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
    duration_ms: float = 0.0  # how long this stage took, to the tenth of a millisecond


class Outcome(StrEnum):
    ANSWERED = "answered"
    BLOCKED = "blocked"


class ReasonCode(StrEnum):
    """Why backend_guard blocked a message; the page shows the matching notice (designs 09-12)."""

    IDENTIFIER = "identifier"  # notice 09: a patient identifier (Aadhaar, phone, PAN, email, ABHA)
    OUT_OF_SCOPE = "out_of_scope"  # notice 10: see scope_topic
    EMERGENCY = "emergency"  # notice 11: no treatment content at all
    LANGUAGE = "language"  # notice 12: foul language
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"  # design 19: the clinical rules stop here


# Which out-of-scope topic (only with reason_code "out_of_scope").
ScopeTopic = Literal["type_1", "pregnancy", "under_18", "dka_hhs", "insulin_start"]


class ChatResponse(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    trace_id: str
    outcome: Outcome
    parts: list[Part | OptionsPart]  # the reply; empty when the message was blocked
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
