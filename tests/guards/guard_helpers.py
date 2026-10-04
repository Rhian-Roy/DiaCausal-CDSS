"""Helpers for the input-guard tests (a module of its own: two folders both importing a module called `conftest` would clash)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from diacausal.api.schemas import AskRequestV1  # noqa: E402

PATIENT = dict(age=52, sex="M", duration_years=5.0, hba1c_pct=8.4, egfr=88.0, bmi=27.0, ascvd=False, heart_failure=False,
               ckd=False, past_hypo=False, past_dka=False, past_pancreatitis=False, type1=False, on_metformin=True)


def make(question: str, **patient) -> AskRequestV1:
    return AskRequestV1(schema_version="1.0", request_id="g1", patient={**PATIENT, **patient}, question=question)


def raw(question: str, **patient) -> AskRequestV1:
    """A request that skips validation (a question longer than the contract allows, a form value out of range): the
    guards must hold even if the request model were bypassed."""
    base = make("placeholder")
    return base.model_copy(update={"question": question, "patient": base.patient.model_copy(update=patient)})
