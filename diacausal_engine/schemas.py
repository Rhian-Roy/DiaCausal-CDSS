"""The contract: what a request must look like, and the structured Causal Output we return.

The Causal Output is the box at the bottom of the "Causal Inference Pipeline" column in the
team's flow chart: Applicable (or NOT_APPLICABLE), Intervention, Outcome, Effect,
Confidence and Assumptions — as JSON, so the Evidence Fusion layer (October) can read it.

Unknown fields are rejected (extra="forbid"); out-of-range values are rejected with a
plain-English message. Plausibility ranges come from data/params.yaml.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from diacausal_engine import INTENDED_USE
from diacausal_engine.config import load_params

_RANGES = load_params().group("display.input_ranges")


def _limits(name: str) -> dict:
    low, high = _RANGES[name]
    return {"ge": low, "le": high}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PatientIn(Strict):
    """One patient. Units: years, HbA1c %, eGFR mL/min/1.73m2, BMI kg/m2."""

    age: int = Field(description="years", **_limits("age"))
    sex: Literal["female", "male"]
    duration_years: float = Field(description="years since type 2 diabetes was diagnosed", **_limits("duration_years"))
    hba1c: float = Field(description="HbA1c, %", **_limits("hba1c"))
    egfr: float = Field(description="eGFR, mL/min/1.73m2", **_limits("egfr"))
    bmi: float = Field(description="BMI, kg/m2", **_limits("bmi"))
    ascvd: bool = False
    hf: bool = False
    hypo_history: bool = False
    t1d: bool = False
    dka_history: bool = False
    pancreatitis_history: bool = False
    low_income: bool = False


class RecommendRequest(Strict):
    schema_version: Literal["1.0"]
    patient: PatientIn


class SafetyNote(Strict):
    rule_id: str
    action: Literal["EXCLUDE", "CAUTION"]
    condition: str
    message: str
    source: str
    section: str
    rule_status: Literal["VERIFIED", "UNVERIFIED"]


class Interval(Strict):
    """Expected 6-month change in HbA1c (percentage points) with its 95% interval."""

    value: float
    ci_low: float
    ci_high: float
    level: float = 0.95


class Confidence(Strict):
    propensity: float  # how often patients like this got this option in the cohort
    overlap_threshold: float
    interval_level: float = 0.95
    method: str


class Cost(Strict):
    inr_per_month: float | None
    label: str  # e.g. "price unavailable"
    as_of_date: str | None = None
    source: str | None = None


class OptionOut(Strict):
    arm: Literal["SGLT2i", "DPP4i", "SU"]
    name: str
    example_molecule: str
    status: Literal["estimate", "insufficient_evidence", "excluded"]
    safety: list[SafetyNote]
    effect: Interval | None = None  # only when status == "estimate"
    confidence: Confidence | None = None
    insufficient_reason: str | None = None
    cost: Cost


class Comparison(Strict):
    first: str
    second: str
    difference: Interval  # first minus second; negative = first lowers HbA1c more


class Outcome(Strict):
    name: str = "Change in HbA1c at 6 months"
    unit: str = "percentage points of HbA1c (%)"
    direction: str = "negative = HbA1c falls (better glucose control)"


class Versions(Strict):
    engine: str
    params: str
    params_sha: str
    rules_sha: str
    cohort: str


class CausalOutput(Strict):
    schema_version: Literal["1.0"] = "1.0"
    request_id: str
    applicable: Literal["APPLICABLE", "NOT_APPLICABLE"]
    not_applicable_reasons: list[str] = []
    intervention: str = "Add one of three options to metformin: SGLT2 inhibitor, DPP-4 inhibitor or sulfonylurea"
    outcome: Outcome = Outcome()
    options: list[OptionOut]
    comparisons: list[Comparison] = []
    assumptions: list[str]
    bmi_category: str
    versions: Versions
    decision: str = "Decision support only. The clinician decides."
    intended_use: str = INTENDED_USE


class ErrorOut(Strict):
    error: Literal["invalid_request"] = "invalid_request"
    message: str
    problems: list[dict]
    intended_use: str = INTENDED_USE


class HealthOut(Strict):
    status: Literal["ok"] = "ok"
    engine: str
    intended_use: str = INTENDED_USE
