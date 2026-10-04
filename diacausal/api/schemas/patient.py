"""PatientV1 and AskRequestV1 (plan 8.2 and 8.4). Ranges are TEAM-SET plausibility bounds, kept in
docs/INPUT_RANGES.md; tests/contract/test_ranges.py fails if that table and RANGES differ."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from diacausal.api.schemas.base import V1

# (low, high) — the same numbers as docs/INPUT_RANGES.md. Not clinical thresholds (those are in data/rules.csv).
RANGES: dict[str, tuple[float, float]] = {
    "age": (18, 100),
    "duration_years": (0, 60),
    "hba1c_pct": (4.0, 20.0),
    "egfr": (5, 150),
    "bmi": (12, 60),
    "waist_cm": (50, 200),
    "glucose_mg_dl": (40, 600),
}


def _r(name: str) -> dict:
    low, high = RANGES[name]
    return {"ge": low, "le": high}


class PatientV1(V1):
    """One patient. Units: years, HbA1c %, eGFR mL/min/1.73m², BMI kg/m², waist cm, glucose mg/dL."""

    age: int = Field(description="years", **_r("age"))
    sex: Literal["F", "M"]
    duration_years: float = Field(description="years since type 2 diabetes was diagnosed", **_r("duration_years"))
    hba1c_pct: float = Field(description="HbA1c, %", **_r("hba1c_pct"))
    egfr: float = Field(description="eGFR, mL/min/1.73m²", **_r("egfr"))
    bmi: float = Field(description="BMI, kg/m²", **_r("bmi"))
    waist_cm: float | None = Field(default=None, description="display only", **_r("waist_cm"))
    ascvd: bool
    heart_failure: bool
    ckd: bool
    past_hypo: bool
    past_dka: bool
    past_pancreatitis: bool
    type1: bool = Field(description="type 1 diabetes: out of scope; the input guard blocks it")
    on_metformin: bool = Field(description="must be true; the scope guard blocks false")
    cost_concern: bool = False
    glucose_mg_dl: float | None = Field(default=None, description="NOT used in the estimate", **_r("glucose_mg_dl"))


class AskRequestV1(V1):
    """POST /api/v1/ask. `schema_version` is required here (the one payload every client builds)."""

    schema_version: Literal["1.0"]
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$", description="the client's trace ID (1-64 of A-Z a-z 0-9 - _)")
    patient: PatientV1
    question: str = Field(min_length=1, max_length=300)
    mode: Literal["template", "ollama"] = "template"


class RecommendRequestV1(V1):
    """POST /api/v1/recommend: the causal engine alone, for one patient."""

    schema_version: Literal["1.0"]
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    patient: PatientV1


def to_engine_patient(p: PatientV1):
    """Convert to the engine's own input model (diacausal.causal_inference.schemas.PatientIn), keeping its names.
    `ckd`, `waist_cm`, `glucose_mg_dl` and `on_metformin` are not engine inputs (the engine adds no inputs)."""
    from diacausal.causal_inference.schemas import PatientIn

    return PatientIn(
        age=p.age, sex="female" if p.sex == "F" else "male", duration_years=p.duration_years, hba1c=p.hba1c_pct,
        egfr=p.egfr, bmi=p.bmi, ascvd=p.ascvd, hf=p.heart_failure, hypo_history=p.past_hypo, t1d=p.type1,
        dka_history=p.past_dka, pancreatitis_history=p.past_pancreatitis, low_income=p.cost_concern,
    )
