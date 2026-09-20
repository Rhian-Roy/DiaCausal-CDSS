"""How wide each patient field may be.

These are **plausibility limits, not clinical thresholds**: they exist only to catch a
typing slip (HbA1c 45% instead of 4.5%, age 580 instead of 58) before anything is
calculated. Nothing here says a value is healthy, safe or treatable — the clinical rules
live in backend/app/clinical/guardrails.v1.yaml and are reviewed by a doctor.

Both sides use these numbers: the browser copies them in
frontend/src/features/patient/ranges.ts, and the two are checked against each other by
tests. The server is the authority.
"""

from typing import NamedTuple


class Range(NamedTuple):
    low: float
    high: float
    unit: str
    label: str
    decimals: int = 0  # how the limits are written in the error message


RANGES: dict[str, Range] = {
    # An adult service: under 18 is out of scope (the guards also catch it in the text).
    "age_years": Range(18, 110, "years", "Age", 0),
    "diabetes_duration_years": Range(0, 80, "years", "Diabetes duration", 0),
    # Below 4% or above 20% is beyond what an assay reports.
    "hba1c_percent": Range(4, 20, "%", "HbA1c", 1),
    "egfr_ml_min_1_73m2": Range(0, 150, "mL/min/1.73m²", "eGFR", 0),
    "bmi_kg_m2": Range(12, 70, "kg/m²", "BMI", 1),
    "budget_inr_per_month": Range(0, 100_000, "₹ per month", "Budget", 0),
}

# BMI categories for Indian adults. Source: Misra A, et al. Consensus statement for
# diagnosis of obesity, abdominal obesity and the metabolic syndrome for Asian Indians.
# J Assoc Physicians India 2009;57:163-170. (Lower than the WHO cut-offs of 25 / 30.)
BMI_CATEGORIES = (
    (18.5, "Underweight (<18.5)"),
    (23.0, "Normal (18.5–22.9)"),
    (25.0, "Overweight (23–24.9)"),
    (float("inf"), "Obese (≥25)"),
)


def bmi_category(bmi: float) -> str:
    return next(name for limit, name in BMI_CATEGORIES if bmi < limit)
