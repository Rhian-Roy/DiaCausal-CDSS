"""What travels through the pipeline for one request. Layers read what earlier layers left here and add their own.

The context holds patient values and the question, so it is never logged: the trace (diacausal/tracing.py) only ever
receives `request_id`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from diacausal.api.schemas import (AnswerCardV1, AskRequestV1, CausalOutputV1, DriverV1, EligibleOptionsV1,
                                   EvidenceBundleV1, GuardResultV1)
from diacausal.api.schemas.card import EvidenceLevelV1
from diacausal.causal_inference.recommend import Engine
from diacausal.causal_inference.schemas import PatientIn


class RequestBlocked(Exception):
    """An input guard stopped the request. `message` is the plain-language reason shown first, `problems` has one
    entry per blocking guard ({"check", "code", "message"}). The route answers HTTP 422 with both (the screens' notices
    09-12 are built from `check` and `code`). Nothing the user typed is in either."""

    def __init__(self, code: str, message: str = "", problems: list[dict] | None = None):
        super().__init__(code)
        self.code = code
        self.message = message
        self.problems = problems or []


@dataclass
class Context:
    request: AskRequestV1
    engine: Engine
    patient: PatientIn
    guard: GuardResultV1 | None = None
    eligible: EligibleOptionsV1 | None = None
    causal: CausalOutputV1 | None = None
    evidence: EvidenceBundleV1 | None = None
    retrieval: dict[str, Any] | None = None  # the retriever's own reply (passages), as explain() expects it
    labels: dict[str, str] = field(default_factory=dict)  # chunk_id -> "WHO 2018, p.12"
    idf: dict[str, float] | None = None
    explanation: dict[str, Any] | None = None
    drivers: dict[str, list[DriverV1]] = field(default_factory=dict)
    evidence_levels: list[EvidenceLevelV1] = field(default_factory=list)
    card: AnswerCardV1 | None = None
    abstained: dict[str, str] = field(default_factory=dict)  # layer name -> reason CODE

    @property
    def request_id(self) -> str:
        return self.request.request_id
