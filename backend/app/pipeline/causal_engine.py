"""Stage 3 — causal_engine (runs today).

Estimates each remaining option's 6-month HbA1c change for this patient, with a 95%
interval, using the causal engine in diacausal_engine/ (cross-fitted propensity, overlap
check, DR-learner). Four rules:

1. It runs after the clinical guardrails and only on what they left: an option they marked
   "do not use" is reported as excluded and never gets a number (the stricter table wins).
2. The engine applies its own cited rules (data/rules.csv) first as well; its exclusions stand.
3. Too few similar patients (propensity below 0.05) or too wide a range means
   "insufficient evidence", never a number.
4. It needs age, sex, diabetes duration, HbA1c, eGFR and BMI from the patient panel; without
   them the stage is skipped and says which fields are missing. Values are never logged.
"""

from __future__ import annotations

from app import engines
from app.pipeline.context import PipelineContext, passed
from app.schemas import (
    Comparison,
    EstimateResult,
    EstimatesPart,
    OptionStatus,
    PatientPart,
    Range,
    StageName,
    StageResult,
    StageStatus,
)
from app.tracing import log

NAME = StageName.CAUSAL_ENGINE

# chat-app option id <-> engine arm
ARM = {"sglt2i": "SGLT2i", "dpp4i": "DPP4i", "sulfonylurea": "SU"}
OPTION = {arm: option for option, arm in ARM.items()}
REQUIRED = {
    "age_years": "age",
    "sex": "sex",
    "diabetes_duration_years": "diabetes duration",
    "hba1c_percent": "HbA1c",
    "egfr_ml_min_1_73m2": "eGFR",
    "bmi_kg_m2": "BMI",
}


def _skipped(detail: str) -> StageResult:
    return StageResult(name=NAME, status=StageStatus.SKIPPED, detail=detail)


def engine_patient(patient: PatientPart):
    """The panel's values in the engine's own model (diacausal_engine.schemas.PatientIn)."""
    from diacausal_engine.schemas import PatientIn

    return PatientIn(
        age=patient.age_years,
        sex=patient.sex,
        duration_years=patient.diabetes_duration_years,
        hba1c=patient.hba1c_percent,
        egfr=patient.egfr_ml_min_1_73m2,
        bmi=patient.bmi_kg_m2,
        ascvd=bool(patient.established_ascvd),
        hf=bool(patient.heart_failure),
        hypo_history=patient.past_hypoglycaemia in ("mild", "severe"),
        dka_history=bool(patient.past_dka),
        pancreatitis_history=bool(patient.past_pancreatitis),
    )


def _range(interval) -> Range | None:
    if interval is None:
        return None
    return Range(value=round(interval.value, 3), ci_low=round(interval.ci_low, 3), ci_high=round(interval.ci_high, 3))


def run(ctx: PipelineContext) -> StageResult:
    patient = ctx.patient
    missing = [label for field, label in REQUIRED.items() if patient is None or getattr(patient, field) is None]
    if missing:
        return _skipped("Needs " + ", ".join(missing) + " in the patient panel.")
    try:
        engine_input = engine_patient(patient)
    except ValueError:
        return _skipped("A patient value is outside the range the causal engine was built for.")

    result = engines.causal_engine().recommend(engine_input, audit=False)
    if result.applicable != "APPLICABLE":
        ctx.estimates_part = None
        return passed(NAME, "Not applicable to this patient: " + "; ".join(result.not_applicable_reasons))

    removed = {o.option for o in ctx.removed_options} | {
        o.option for o in (ctx.options_part.options if ctx.options_part else []) if o.status is OptionStatus.DO_NOT_USE
    }
    estimates: list[EstimateResult] = []
    for out in result.options:
        option = OPTION[out.arm]
        rule_ids = [note.rule_id for note in out.safety]
        if option in removed:
            estimates.append(EstimateResult(option=option, name=out.name, status="excluded", rule_ids=rule_ids,
                                            reason="Removed by the clinical guardrails before any estimate."))
            continue
        if out.status == "excluded":
            reason = "; ".join(n.message for n in out.safety if n.action == "EXCLUDE") or "Excluded by a safety rule."
            estimates.append(EstimateResult(option=option, name=out.name, status="excluded", reason=reason, rule_ids=rule_ids))
        elif out.status == "insufficient_evidence":
            estimates.append(EstimateResult(option=option, name=out.name, status="insufficient_evidence",
                                            reason=out.insufficient_reason, rule_ids=rule_ids,
                                            propensity=out.confidence.propensity if out.confidence else None))
        else:
            estimates.append(EstimateResult(
                option=option, name=out.name, status="estimate", rule_ids=rule_ids,
                hba1c_change=_range(out.effect),
                weight_change_kg=_range(out.secondary.weight_change_kg) if out.secondary else None,
                hypo_risk_pct=_range(out.secondary.hypo_risk_pct) if out.secondary else None,
                propensity=round(out.confidence.propensity, 3) if out.confidence else None,
            ))
    shown = {e.option for e in estimates if e.status == "estimate"}
    comparisons = [
        Comparison(first=c.first, second=c.second, difference=_range(c.difference))
        for c in result.comparisons
        if OPTION.get(c.first) in shown and OPTION.get(c.second) in shown
    ]
    method = next((o.confidence.method for o in result.options if o.confidence), "DR-learner")
    ctx.estimates_part = EstimatesPart(
        type="estimates", estimates=estimates, comparisons=comparisons, method=method,
        engine_version=f"engine {result.versions.engine}, params {result.versions.params_sha}, rules {result.versions.rules_sha}",
    )
    counts = {s: sum(e.status == s for e in estimates) for s in ("estimate", "insufficient_evidence", "excluded")}
    log.info("causal_engine: %d estimates, %d insufficient evidence, %d excluded",
             counts["estimate"], counts["insufficient_evidence"], counts["excluded"])
    return passed(NAME, f"{counts['estimate']} estimates, {counts['insufficient_evidence']} insufficient evidence, "
                        f"{counts['excluded']} excluded.")
