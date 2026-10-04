"""CausalOutputV1: the existing engine CausalOutput, every field and name unchanged, plus an optional list
of SHAP drivers per option (DriverV1, empty until P25). Reused by subclassing, so the two cannot drift."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from diacausal.api.schemas.base import V1
from diacausal.causal_inference.schemas import CausalOutput, OptionOut


class DriverV1(V1):
    """One SHAP driver of one option's estimate: 'the estimate is larger/smaller for patients with ...'
    (never a cause). `contribution` is in HbA1c percentage points, signed."""

    feature: str
    value: float | bool | str = Field(description="this patient's value for the feature")
    contribution: float
    ci95: tuple[float, float] | None = Field(default=None, description="95% interval, when computed (P25)")


class OptionV1(OptionOut):
    """The engine's OptionOut, unchanged, plus drivers."""

    schema_version: Literal["1.0"] = "1.0"
    drivers: list[DriverV1] = []


class CausalOutputV1(CausalOutput):
    """The engine's CausalOutput, unchanged (applicable, intervention, outcome, options, comparisons,
    assumptions, bmi_category, versions, decision, intended_use), with options that may carry drivers."""

    options: list[OptionV1]
