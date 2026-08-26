"""
Clinical safety rules — the part of the system that is allowed to say no.
=======================================================================

Everything else in this package is statistics. This file is not. It is a short
list of hard clinical rules that sit ABOVE the model and can override it.

Why a machine-learning project needs a layer of hand-written `if` statements:

    A CATE model is fitted to data. It only knows what was in that data. If no
    patient in the cohort had an eGFR of 22, the model has never seen renal
    failure and will cheerfully extrapolate a number for it. That number is not
    a prediction; it is an artefact of whatever the last tree split happened to
    be. A guardrail catches it before it reaches a clinician.

    Some contraindications are not statistical claims at all. "Metformin is
    contraindicated below eGFR 30" is not a statement about average effects — it
    is about lactic acidosis, a rare event that a 4,000-patient effect model
    would never learn and should never be trusted to weigh.

So the architecture is deliberately asymmetric:

    The model may RECOMMEND.
    Only the guardrails may FORBID.

--------------------------------------------------------------------------------
THE FOUR PRINCIPLES THIS FILE ENCODES
--------------------------------------------------------------------------------
    1. HARD RULES BEAT SOFT ESTIMATES
       A contraindication is not a number to be traded off against a predicted
       benefit. It is a veto.

    2. OUT-OF-DISTRIBUTION IS A SAFETY EVENT
       If a patient sits outside the range the model was trained on, the honest
       output is "I don't know", not a confident extrapolation.

    3. SMALL EFFECTS ARE NOT DECISIONS
       An estimated benefit of 0.08 HbA1c points, with a standard error of 0.05,
       is a rounding error dressed as advice. Say so.

    4. EVERY FLAG NAMES ITS REASON AND ITS SOURCE
       A warning a clinician cannot audit is a warning a clinician will learn to
       dismiss.

--------------------------------------------------------------------------------
SCOPE, PLAINLY
--------------------------------------------------------------------------------
These thresholds are drawn from published guidance and are here to demonstrate
the architecture of a safety layer in a student project. They are not a clinical
reference, they are not exhaustive, and nothing here should be used to treat a
real person. A deployed system would need pharmacist review, the full
contraindication set, drug-interaction checking, and local formulary rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Severity(IntEnum):
    """How much attention a flag demands. Ordered, so `max()` works."""

    INFO = 0      #: worth knowing
    CAUTION = 1   #: proceed, but with a named risk
    WARNING = 2   #: do not proceed without a reason
    VETO = 3      #: do not proceed


SEVERITY_LABEL = {
    Severity.INFO: "INFO",
    Severity.CAUTION: "CAUTION",
    Severity.WARNING: "WARNING",
    Severity.VETO: "CONTRAINDICATED",
}


@dataclass
class Flag:
    """One triggered rule. Carries its reason and its source, always."""

    rule: str
    severity: Severity
    message: str
    source: str

    def __str__(self) -> str:
        return f"[{SEVERITY_LABEL[self.severity]}] {self.message}  ({self.source})"


@dataclass
class GuardrailResult:
    """The verdict of the safety layer on one patient."""

    flags: list[Flag] = field(default_factory=list)
    #: The range the model was actually trained on, for the OOD check.
    training_ranges: dict = field(default_factory=dict)

    @property
    def severity(self) -> Severity:
        return max((f.severity for f in self.flags), default=Severity.INFO)

    @property
    def vetoed(self) -> bool:
        """Is the recommendation forbidden outright?"""
        return any(f.severity == Severity.VETO for f in self.flags)

    @property
    def status(self) -> str:
        if self.vetoed:
            return "BLOCKED — contraindication present"
        if self.severity == Severity.WARNING:
            return "HOLD — specialist review required"
        if self.severity == Severity.CAUTION:
            return "PROCEED WITH CAUTION"
        return "APPROVED"

    def __str__(self) -> str:
        if not self.flags:
            return "APPROVED — no safety rule triggered."
        return "\n".join(f"    {f}" for f in self.flags)


# ─────────────────────────────────────────────────────────────────────────────
# The rules.
#
# Each is a small function of (patient, estimate) returning a Flag or None. Kept
# as separate functions rather than one long if-chain so that each can be unit
# tested, cited, and read in isolation — which is what makes the set auditable.
# ─────────────────────────────────────────────────────────────────────────────

def rule_metformin_contraindicated(patient: dict, est: dict) -> Flag | None:
    """eGFR < 30: metformin is contraindicated (lactic acidosis risk).

    Note carefully what this rule does NOT say. It does not say "give the SGLT2
    inhibitor". Both arms of our comparison are problematic here, so the correct
    output is to stop and escalate, not to pick the less-vetoed option. A CDSS
    that silently converts "drug A is contraindicated" into "therefore drug B"
    has invented a recommendation nobody made.
    """
    if patient.get("egfr", 100) < 30:
        return Flag(
            rule="metformin_egfr_30",
            severity=Severity.VETO,
            message=(
                f"eGFR {patient['egfr']:.0f} is below 30 mL/min/1.73m². Metformin "
                "is contraindicated (lactic acidosis). SGLT2i glucose-lowering "
                "efficacy is also minimal at this eGFR. Neither arm of this "
                "comparison is appropriate — refer to nephrology/endocrinology."
            ),
            source="ADA Standards of Care; national formulary labelling",
        )
    return None


def rule_sglt2i_low_egfr(patient: dict, est: dict) -> Flag | None:
    """eGFR < 45: SGLT2i are not started for GLYCAEMIC benefit.

    The distinction this rule preserves is the one clinicians care about and
    models routinely lose. SGLT2 inhibitors have two separate reasons to exist:

        glucose lowering   depends on renal filtration, so it fades with eGFR
        organ protection   kidney and heart outcomes, which persist at low eGFR

    Our model estimates HbA1c reduction — the first one only. So a low predicted
    HbA1c benefit is NOT a reason to stop or avoid the drug in someone taking it
    for cardiorenal protection. Getting this wrong would be a serious clinical
    error, so the flag says it explicitly rather than leaving it to be inferred.
    """
    egfr = patient.get("egfr", 100)
    if 30 <= egfr < 45:
        return Flag(
            rule="sglt2i_egfr_45",
            severity=Severity.WARNING,
            message=(
                f"eGFR {egfr:.0f} is below 45. SGLT2i are generally not INITIATED "
                "for glycaemic benefit here — but their kidney and heart benefits "
                "persist and are a valid reason to start or continue independently "
                "of HbA1c. This model estimates HbA1c reduction ONLY, so a low "
                "estimate is not evidence against the drug for cardiorenal "
                "indications."
            ),
            source="ADA Standards of Care, pharmacologic approaches",
        )
    return None


def rule_out_of_distribution(patient: dict, est: dict) -> Flag | None:
    """Is this patient outside the range the model was trained on?

    Principle 2 in code. A gradient-boosted model does not refuse to answer for
    inputs it has never seen — it returns whatever the nearest leaf holds, with
    no signal that it is guessing. For a 24-year-old with an eGFR of 118, every
    tree split was learned from people who look nothing like them.

    The threshold is the training data's own observed range, passed in rather
    than hardcoded, so this rule stays true if the cohort changes.
    """
    ranges = est.get("training_ranges") or {}
    outside = []
    for var, (lo, hi) in ranges.items():
        v = patient.get(var)
        if v is None:
            continue
        if v < lo or v > hi:
            outside.append(f"{var}={v:g} (trained on {lo:g}–{hi:g})")
    if outside:
        return Flag(
            rule="out_of_distribution",
            severity=Severity.WARNING,
            message=(
                "This patient falls outside the range the model was trained on: "
                + "; ".join(outside)
                + ". The estimate below is an extrapolation, not a prediction. "
                "Treat it as unavailable."
            ),
            source="model training-data envelope",
        )
    return None


def rule_effect_too_small(patient: dict, est: dict) -> Flag | None:
    """Is the predicted benefit smaller than our own uncertainty about it?

    Principle 3. An estimate of +0.09 with a standard error of ±0.20 is not a
    small benefit — it is no information. Reporting it as "SGLT2i slightly
    preferred" converts noise into advice, which is exactly how a decision
    support tool loses a clinician's trust for good.
    """
    cate = est.get("cate")
    se = est.get("cate_se")
    if cate is None:
        return None
    if abs(cate) < 0.3:
        detail = f"estimated difference {cate:+.2f} HbA1c points"
        if se:
            detail += f" (± {se:.2f})"
        return Flag(
            rule="effect_below_threshold",
            severity=Severity.CAUTION,
            message=(
                f"The two drugs are near-equivalent for this patient: {detail}, "
                "which is below the ~0.3 point threshold usually considered "
                "clinically meaningful. Decide on cost, tolerability, adherence "
                "and patient preference instead — the effect model has nothing "
                "useful to add here, and saying so is more honest than ranking "
                "noise."
            ),
            source="clinical significance threshold for HbA1c",
        )
    return None


def rule_predicted_harm(patient: dict, est: dict) -> Flag | None:
    """Does the model predict this patient is HARMED by the newer drug?

    The reason the whole project exists. The population average effect is
    positive — the drug helps on average — so any tool reasoning from the average
    recommends it here. This rule is the one that catches the roughly one patient
    in six for whom the average is wrong.
    """
    cate = est.get("cate")
    if cate is not None and cate <= -0.3:
        return Flag(
            rule="predicted_harm",
            severity=Severity.WARNING,
            message=(
                f"The model predicts SGLT2i is WORSE than metformin for this "
                f"patient ({cate:+.2f} HbA1c points), despite being better on "
                "population average. This is precisely the case a "
                "population-average tool gets wrong. Verify the renal and "
                "adherence assumptions before acting."
            ),
            source="individual treatment effect estimate (this model)",
        )
    return None


def rule_severe_hyperglycaemia(patient: dict, est: dict) -> Flag | None:
    """Very high HbA1c changes the question from 'which drug' to 'how fast'."""
    if patient.get("baseline_hba1c", 0) >= 10.0:
        return Flag(
            rule="severe_hyperglycaemia",
            severity=Severity.CAUTION,
            message=(
                f"Baseline HbA1c {patient['baseline_hba1c']:.1f}% indicates severe "
                "hyperglycaemia. Guidance favours early combination therapy or "
                "insulin rather than a single oral agent, so the "
                "SGLT2i-vs-metformin comparison this model answers may be the "
                "wrong question for this patient."
            ),
            source="IDF 2025; ADA Standards of Care",
        )
    return None


def rule_cvd_indication(patient: dict, est: dict) -> Flag | None:
    """Established CVD is an indication in its own right, HbA1c aside."""
    if patient.get("has_cvd"):
        return Flag(
            rule="cvd_indication",
            severity=Severity.INFO,
            message=(
                "Established cardiovascular disease is an independent indication "
                "for an SGLT2 inhibitor, on cardiovascular outcomes rather than "
                "glycaemic control. That benefit is NOT captured by this model, "
                "which estimates HbA1c reduction only — so the true case for the "
                "drug in this patient is stronger than the number below."
            ),
            source="ADA Standards of Care; IDF 2025",
        )
    return None


#: Evaluated in order. Order affects only presentation, never the verdict —
#: `GuardrailResult.severity` takes the maximum, so no rule can be buried by an
#: earlier one.
ALL_RULES = [
    rule_metformin_contraindicated,
    rule_sglt2i_low_egfr,
    rule_out_of_distribution,
    rule_predicted_harm,
    rule_effect_too_small,
    rule_severe_hyperglycaemia,
    rule_cvd_indication,
]


def check(patient: dict, estimate: dict | None = None) -> GuardrailResult:
    """Run every rule against one patient. The single entry point.

    Parameters
    ----------
    patient
        Covariates: age, bmi, baseline_hba1c, egfr, has_cvd, has_ckd.
    estimate
        Optional model output: ``{"cate": float, "cate_se": float,
        "training_ranges": {var: (lo, hi)}}``. Rules that need it skip
        themselves when it is absent, so the safety layer works standalone —
        useful, because it means the contraindication checks still run even if
        the model fails to load.
    """
    est = estimate or {}
    flags = [f for f in (rule(patient, est) for rule in ALL_RULES) if f is not None]
    return GuardrailResult(flags=flags, training_ranges=est.get("training_ranges", {}))


def training_ranges(cohort) -> dict:
    """The observed min/max of each covariate — the model's honest domain.

    Passed into :func:`check` so `rule_out_of_distribution` compares against
    reality rather than against a hardcoded guess that will drift out of date.
    """
    from .data import COVARIATES

    df = cohort.data
    return {
        c: (float(df[c].min()), float(df[c].max()))
        for c in COVARIATES
        if c not in {"has_cvd", "has_ckd"}   # binary; a range is meaningless
    }


def rules_table():
    """Print the rule set as a table. Good for the report's safety section."""
    import pandas as pd

    rows = []
    for fn in ALL_RULES:
        doc = (fn.__doc__ or "").strip().split("\n")[0]
        rows.append({"rule": fn.__name__.replace("rule_", ""), "trigger": doc})
    return pd.DataFrame(rows)
