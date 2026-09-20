"""Stage 2 — clinical_guardrails (runs today).

Hard safety rules, from the cited table in app/clinical/guardrails.v1.yaml, applied
**before** anything is ranked. Three invariants:

1. Guardrails run before the causal engine, so a contraindicated option can never be
   ranked, let alone shown first.
2. Every threshold comes from the table, with a source. Nothing is read out of the
   doctor's sentence and nothing comes from a language model.
3. An option marked "do not use" is removed here, so later stages never see it.

When a patient-scope rule fires (for example eGFR below 30, or eGFR not entered at all),
the whole question is refused with the rule's reason — "insufficient evidence" rather
than a guess (design 19).

While the table has not been reviewed by the collaborating doctor, every reply says so.
"""

from app.clinical import rules as clinical_rules
from app.clinical.rules import DRAFT_WARNING, OPTION_NAMES, OPTIONS, RuleSet
from app.pipeline.context import PipelineContext, blocked, passed
from app.schemas import OptionResult, OptionsPart, OptionStatus, PatientPart, ReasonCode, StageName, StageResult
from app.tracing import log

NAME = StageName.CLINICAL_GUARDRAILS

_rule_set: RuleSet | None = None

# The order matters: the strictest action wins for an option.
_STATUS = {"do_not_use": OptionStatus.DO_NOT_USE, "check_first": OptionStatus.CHECK_FIRST}


def rule_set() -> RuleSet:
    """The table, read once. Refused rules (TODO, no source) are reported, never applied."""
    global _rule_set
    if _rule_set is None:
        _rule_set = clinical_rules.load()
        for refused in _rule_set.refused:
            log.warning("clinical rule NOT in use — %s", refused)
        for rule in _rule_set.rules:
            if rule.needs_recheck:
                log.warning("clinical rule %s is marked 'recheck': its source must be re-opened", rule.id)
    return _rule_set


def reset() -> None:
    """Forget the loaded table (tests that use their own file)."""
    global _rule_set
    _rule_set = None


def _patient_values(patient: PatientPart | None) -> dict:
    """Every field the rules may ask about; not entered means None, which means "unknown"."""
    empty = PatientPart(type="patient")
    return (patient or empty).model_dump(exclude={"type"})


def run(ctx: PipelineContext) -> StageResult:
    table = rule_set()
    values = _patient_values(ctx.patient)
    log.info("clinical_guardrails: rules %s (%d in use)", table.version, len(table.rules))

    # 1. Rules about the patient as a whole: they stop the question entirely.
    for rule in table.patient_rules:
        if clinical_rules.applies(rule, values):
            log.info("clinical_guardrails: %s stops this question", rule.id)
            return blocked(ctx, NAME, rule.reason, ReasonCode.INSUFFICIENT_EVIDENCE)

    # 2. Rules about one option: strictest wins, and "do not use" removes the option.
    results: list[OptionResult] = []
    for option in OPTIONS:
        status, reasons, sources, notes, fired = OptionStatus.SAFE_TO_CONSIDER, [], [], [], []
        for rule in table.for_option(option):
            if not clinical_rules.applies(rule, values):
                continue
            fired.append(rule.id)
            if rule.action == "info":
                notes.append(rule.reason)
                sources.extend(rule.sources)
                continue
            reasons.append(rule.reason)
            sources.extend(rule.sources)
            if _STATUS[rule.action] is OptionStatus.DO_NOT_USE:
                status = OptionStatus.DO_NOT_USE
            elif status is not OptionStatus.DO_NOT_USE:
                status = OptionStatus.CHECK_FIRST
        results.append(
            OptionResult(
                option=option, name=OPTION_NAMES[option], status=status, reasons=reasons,
                sources=list(dict.fromkeys(sources)), notes=notes, rule_ids=fired,
            )
        )

    # 3. Nothing left to consider: say so instead of ranking the unusable.
    if all(result.status is OptionStatus.DO_NOT_USE for result in results):
        return blocked(
            ctx, NAME,
            "None of the three add-on options can be used for this patient, so DiaCausal has not "
            "ranked anything. " + " ".join(reason for result in results for reason in result.reasons),
            ReasonCode.INSUFFICIENT_EVIDENCE,
        )

    # Only options that may be used go forward; the causal engine never sees the others.
    ctx.options = [result for result in results if result.status is not OptionStatus.DO_NOT_USE]
    ctx.removed_options = [result for result in results if result.status is OptionStatus.DO_NOT_USE]
    ctx.options_part = OptionsPart(
        type="options",
        options=results,
        rules_version=table.version,
        draft_warning=DRAFT_WARNING if table.is_draft else None,
    )

    removed = ", ".join(result.option for result in ctx.removed_options)
    detail = f"{len(ctx.options)} of {len(OPTIONS)} options may be used" + (f"; removed: {removed}" if removed else "")
    log.info("clinical_guardrails: %s", detail)
    return passed(NAME, detail)
