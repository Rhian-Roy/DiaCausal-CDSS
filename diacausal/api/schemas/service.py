"""Small service models: health and the error reply (same shape the engine API already returns)."""

from __future__ import annotations

from typing import Literal

from diacausal.api.schemas.base import V1
from diacausal_engine import INTENDED_USE


class HealthV1(V1):
    status: Literal["ok"] = "ok"
    engine: str
    intended_use: str = INTENDED_USE


class ErrorV1(V1):
    error: Literal["invalid_request"] = "invalid_request"
    message: str
    problems: list[dict]
    intended_use: str = INTENDED_USE
