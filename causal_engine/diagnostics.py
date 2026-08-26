"""
ACT 4 — Are you even ALLOWED to answer this question?
=====================================================

Every method in Act 5 will return a number. All of them return a number even
when the number is meaningless. Nothing in the code will warn you.

Causal inference rests on three assumptions. They are not technicalities — they
are the entire licence to make a causal claim from observational data. This
module turns each one into something you can run, look at, and fail.

    1. SUTVA / consistency
       One patient's treatment does not change another patient's outcome, and
       "treatment" means the same thing for everyone.
       -> Not statistically testable. Argued from the clinical setting.
          (For a chronic oral drug it is uncontroversial. For a vaccine, or a
          hospital-level intervention, it is a real problem.)

    2. POSITIVITY / overlap    0 < P(T=1 | X) < 1
       Every patient must have had SOME chance of either drug.
       -> TESTABLE. Look at the propensity distributions: `overlap_report`.
          If a whole region of patient space has no treated patients, no
          honest comparison exists there and no method can invent one.

    3. IGNORABILITY / no unmeasured confounding
       Once we condition on X, treatment is as good as random.
       -> NOT testable, ever. This is the load-bearing assumption and it is
          untestable in principle. So instead of claiming it, we ask how WRONG
          it would have to be to overturn our conclusion: `e_value`.

The professional move — and the thing that distinguishes a serious project — is
that assumption 3 is never asserted. It is quantified as a vulnerability.

BALANCE is not a fourth assumption; it is the *evidence* that our adjustment
did what we asked. `balance_table` and the love plot show the two groups
becoming comparable, which is the visual proof that weighting worked.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import PALETTE

#: Conventional threshold. |SMD| > 0.1 is treated as meaningful imbalance in
#: the epidemiology literature (Austin 2009). It is a convention, not a law.
SMD_THRESHOLD = 0.1


# ═════════════════════════════════════════════════════════════════════════════
# ASSUMPTION 2 — POSITIVITY / OVERLAP.  Testable, so we test it.
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class OverlapReport:
    """Did every patient have a real chance of either drug?"""

    propensity: np.ndarray
    treatment: np.ndarray
    min_treated: float
    max_treated: float
    min_control: float
    max_control: float
    n_extreme: int
    effective_sample_size: float
    max_weight: float
    verdict: str
    detail: str

    def __str__(self) -> str:
        return (
            f"POSITIVITY: {self.verdict}\n"
            f"    treated   e(x) in [{self.min_treated:.3f}, {self.max_treated:.3f}]\n"
            f"    control   e(x) in [{self.min_control:.3f}, {self.max_control:.3f}]\n"
            f"    patients with e(x) outside [0.05, 0.95] : {self.n_extreme}\n"
            f"    largest IPW weight                      : {self.max_weight:.1f}\n"
            f"    effective sample size                   : "
            f"{self.effective_sample_size:.0f} of {len(self.propensity)}\n"
            f"    {self.detail}"
        )


def overlap_report(
    propensity: np.ndarray,
    treatment: np.ndarray,
    extreme: tuple[float, float] = (0.05, 0.95),
) -> OverlapReport:
    """Check positivity, and say plainly whether the analysis is defensible.

    The two numbers that actually matter:

    `max_weight` — one patient's influence on the answer. A weight of 100 means
    a single person is standing in for a hundred. Your "average over 4000
    patients" is really a rumour about a handful of unusual ones.

    `effective_sample_size` — how many patients the estimate is really standing
    on, `(sum w)^2 / sum(w^2)`. If 4000 patients give an ESS of 600, the
    confidence interval is quietly lying to you, because it was computed as
    though you had 4000 independent contributions.

    Neither of these appears in a p-value. Both should appear in your report.
    """
    e = np.asarray(propensity, dtype=float)
    t = np.asarray(treatment, dtype=int)
    lo, hi = extreme

    e_treated, e_control = e[t == 1], e[t == 0]
    weights = np.where(t == 1, 1.0 / np.clip(e, 1e-12, 1), 1.0 / np.clip(1 - e, 1e-12, 1))
    ess = float(weights.sum() ** 2 / np.sum(weights ** 2))
    n_extreme = int(((e < lo) | (e > hi)).sum())

    # The decisive question is not "is the range wide" but "do the two groups
    # OVERLAP" — is there a region where both drugs actually occur?
    shared_lo = max(e_treated.min(), e_control.min())
    shared_hi = min(e_treated.max(), e_control.max())
    overlap_width = shared_hi - shared_lo

    if overlap_width <= 0:
        verdict = "VIOLATED — no comparable patients at all"
        detail = (
            "The treated and control propensity ranges do not overlap. There is "
            "no region of patient space containing both drugs, so there is "
            "nothing to compare. STOP: no method can fix this."
        )
    elif ess < 0.4 * len(e) or weights.max() > 50:
        verdict = "FRAGILE — overlap is technically present but thin"
        detail = (
            "A few patients dominate the weighted average. Report the effective "
            "sample size alongside the estimate, and trim to the overlap region "
            "(causal_engine.estimators.trim_by_overlap) before believing the CI."
        )
    elif n_extreme > 0.05 * len(e):
        verdict = "ACCEPTABLE with caution"
        detail = (
            f"{n_extreme} patients sit in the tails. Consider trimming and "
            "report both the trimmed and untrimmed answers."
        )
    else:
        verdict = "SATISFIED"
        detail = (
            "Both groups span a common propensity range with no extreme weights. "
            "Every patient had a genuine chance of either drug, so a comparison "
            "is licensed."
        )

    return OverlapReport(
        propensity=e,
        treatment=t,
        min_treated=float(e_treated.min()),
        max_treated=float(e_treated.max()),
        min_control=float(e_control.min()),
        max_control=float(e_control.max()),
        n_extreme=n_extreme,
        effective_sample_size=ess,
        max_weight=float(weights.max()),
        verdict=verdict,
        detail=detail,
    )


def plot_overlap(propensity, treatment, ax=None, title=None, save_to=None):
    """The single most important diagnostic plot in observational research.

    Two histograms of the propensity score. Where they overlap, we can compare
    patients. Where only one colour appears, we are extrapolating — inventing
    an answer for patients who had no counterpart.

    What good looks like: two broad, heavily-overlapping humps.
    What broken looks like: two spikes pinned at opposite ends, touching nowhere.
    """
    import matplotlib.pyplot as plt

    e = np.asarray(propensity, float)
    t = np.asarray(treatment, int)
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 4.6))

    bins = np.linspace(0, 1, 41)
    ax.hist(e[t == 0], bins=bins, alpha=0.62, label="Metformin (T=0)",
            color=PALETTE["muted"], edgecolor="white", linewidth=0.4)
    ax.hist(e[t == 1], bins=bins, alpha=0.62, label="SGLT2i (T=1)",
            color=PALETTE["primary"], edgecolor="white", linewidth=0.4)

    for b in (0.05, 0.95):
        ax.axvline(b, color=PALETTE["alert"], linestyle=":", linewidth=1.4)
    ax.text(0.5, ax.get_ylim()[1] * 0.94,
            "dotted lines = conventional trimming bounds",
            ha="center", fontsize=8, color=PALETTE["alert"])

    ax.set_xlabel("Propensity score  e(x) = P(SGLT2i | patient features)")
    ax.set_ylabel("Number of patients")
    ax.set_title(title or "Overlap / positivity check",
                 fontweight="bold", color=PALETTE["secondary"])
    ax.legend()
    ax.spines[["top", "right"]].set_visible(False)

    if save_to:
        ax.figure.tight_layout()
        ax.figure.savefig(save_to, dpi=150, bbox_inches="tight")
    return ax


# ═════════════════════════════════════════════════════════════════════════════
# BALANCE — the evidence that our adjustment actually worked
# ═════════════════════════════════════════════════════════════════════════════

def standardised_mean_difference(x, t, weights=None) -> float:
    """Difference between groups, measured in pooled standard deviations.

    Why not just the raw difference? Because age is measured in years and eGFR
    in mL/min. A 5-unit gap means completely different things. Dividing by the
    pooled SD makes every variable comparable on one axis, which is what lets
    the love plot put them all on one chart.

    Note the denominator uses the UNWEIGHTED pooled SD even when weights are
    supplied. That is deliberate and standard (Austin & Stuart 2015): keeping
    the yardstick fixed is what makes before-and-after comparable. If the
    denominator moved too, you could "improve" balance by inflating variance.
    """
    x = np.asarray(x, float)
    t = np.asarray(t, int)
    a, b = x[t == 1], x[t == 0]
    pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2.0)
    if pooled == 0:
        return 0.0

    if weights is None:
        return float((a.mean() - b.mean()) / pooled)

    w = np.asarray(weights, float)
    wa, wb = w[t == 1], w[t == 0]
    mean_a = float(np.average(a, weights=wa))
    mean_b = float(np.average(b, weights=wb))
    return (mean_a - mean_b) / pooled


def balance_table(X, T, covariate_names, weights=None) -> pd.DataFrame:
    """Per-covariate balance, before and (optionally) after weighting.

    Read the `after` column as the receipt for your adjustment. If SMDs are
    still above 0.1 after weighting, the propensity model has not done its job
    and no downstream number should be trusted, however tight its CI.
    """
    X = np.asarray(X, float)
    rows = []
    for j, name in enumerate(covariate_names):
        before = standardised_mean_difference(X[:, j], T)
        row = {"covariate": name, "SMD before": round(before, 4)}
        if weights is not None:
            after = standardised_mean_difference(X[:, j], T, weights)
            row["SMD after"] = round(after, 4)
            row["improved?"] = "yes" if abs(after) < abs(before) else "NO"
            row["balanced?"] = "yes" if abs(after) < SMD_THRESHOLD else "NO"
        else:
            row["balanced?"] = "yes" if abs(before) < SMD_THRESHOLD else "NO"
        rows.append(row)
    return pd.DataFrame(rows)


def plot_love(table: pd.DataFrame, ax=None, title=None, save_to=None):
    """The 'love plot' (named after Thomas Love), a before/after balance chart.

    One row per covariate, |SMD| on the x-axis, a vertical line at 0.1. Grey
    dots (before) should sit to the right of the line; teal dots (after) should
    all have collapsed to the left of it. It is the most compact possible proof
    that weighting worked — and if it hasn't, this is where you find out.
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(8.4, 4.8))

    order = table.reindex(
        table["SMD before"].abs().sort_values().index
    ).reset_index(drop=True)
    y = np.arange(len(order))

    ax.scatter(order["SMD before"].abs(), y, s=95, color=PALETTE["muted"],
               label="before adjustment", zorder=3, edgecolors="white")
    if "SMD after" in order:
        ax.scatter(order["SMD after"].abs(), y, s=95, color=PALETTE["primary"],
                   label="after weighting", zorder=4, edgecolors="white")
        for i in y:
            ax.plot([abs(order["SMD before"][i]), abs(order["SMD after"][i])],
                    [i, i], color=PALETTE["muted"], linewidth=1.0, alpha=0.6,
                    zorder=2)

    ax.axvline(SMD_THRESHOLD, color=PALETTE["alert"], linestyle="--", linewidth=1.5)
    ax.text(SMD_THRESHOLD, len(order) - 0.35, "  balance threshold 0.1",
            color=PALETTE["alert"], fontsize=8.5, va="top")

    ax.set_yticks(y)
    ax.set_yticklabels(order["covariate"])
    ax.set_xlabel("|standardised mean difference|   (0 = perfectly balanced)")
    ax.set_title(title or "Love plot — did adjustment make the groups comparable?",
                 fontweight="bold", color=PALETTE["secondary"])
    ax.legend(loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)

    if save_to:
        ax.figure.tight_layout()
        ax.figure.savefig(save_to, dpi=150, bbox_inches="tight")
    return ax


# ═════════════════════════════════════════════════════════════════════════════
# ASSUMPTION 3 — IGNORABILITY. Untestable, so we quantify the vulnerability.
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class EValueResult:
    """How strong would a hidden confounder have to be to erase our finding?"""

    estimate: float
    ci_low: float | None
    e_value: float
    e_value_ci: float | None
    scale: str
    interpretation: str
    notes: dict = field(default_factory=dict)

    def __str__(self) -> str:
        out = [
            f"E-VALUE  (scale: {self.scale})",
            f"    point estimate       : {self.estimate:+.4f}",
            f"    E-value              : {self.e_value:.2f}",
        ]
        if self.e_value_ci is not None:
            out.append(f"    E-value for CI bound : {self.e_value_ci:.2f}")
        out.append(f"    {self.interpretation}")
        return "\n".join(out)


def e_value(
    estimate: float,
    ci_low: float | None = None,
    sd: float | None = None,
    scale: str = "difference",
) -> EValueResult:
    """VanderWeele & Ding (2017) E-value: the honest answer to "what if you
    missed a confounder?"

    THE IDEA
    --------
    We cannot test ignorability. But we can ask a question with a real answer:

        How strongly would an unmeasured confounder have to be associated with
        BOTH the treatment and the outcome — above and beyond everything we
        already adjusted for — to explain away our entire result?

    The answer is a single number on a risk-ratio scale.

        E-value = 1.0  ->  the tiniest hidden confounder destroys the finding.
        E-value = 2.0  ->  a hidden confounder would have to double both the
                           odds of getting the drug AND the odds of the outcome.
        E-value = 5.0  ->  it would have to be a stronger predictor than any
                           variable you measured. Implausible in most settings.

    Then you argue clinically: is a confounder that strong plausible here, given
    that we already adjusted for HbA1c, eGFR, age, BMI and comorbidity?

    THE MATHS
    ---------
    For a risk ratio RR > 1:      E = RR + sqrt(RR * (RR - 1))
    For a continuous outcome, first convert the standardised effect d to an
    approximate risk ratio (Chinn 2000; VanderWeele 2017):

        RR ~= exp(0.91 * d),     d = estimate / sd

    We report the E-value for the point estimate AND for the CI bound nearest
    the null. The CI one is the more conservative and more honest number, and
    it is the one to quote.
    """
    if scale == "difference":
        if sd is None:
            raise ValueError(
                "For a continuous outcome, pass sd = the outcome's standard "
                "deviation so the effect can be standardised."
            )
        d = estimate / sd
        rr = float(np.exp(0.91 * d))
        rr_ci = float(np.exp(0.91 * ci_low / sd)) if ci_low is not None else None
        note = {"cohens_d": d, "approx_risk_ratio": rr}
    else:
        rr, rr_ci, note = float(estimate), (
            float(ci_low) if ci_low is not None else None
        ), {}

    def _ev(r: float) -> float:
        # The formula assumes RR > 1. For a protective effect (RR < 1) the
        # standard move is to invert it, because "halving the risk" and
        # "doubling the risk" are equally strong findings.
        if r <= 0:
            return 1.0
        if r < 1:
            r = 1.0 / r
        if r <= 1:
            return 1.0
        return float(r + np.sqrt(r * (r - 1.0)))

    ev = _ev(rr)
    ev_ci = _ev(rr_ci) if rr_ci is not None else None

    # Interpretation thresholds are judgement, and we say so rather than
    # dressing them up as a test.
    quoted = ev_ci if ev_ci is not None else ev
    if quoted < 1.25:
        verdict = (
            "VERY FRAGILE. Almost any unmeasured confounder could account for "
            "this. Do not act on it."
        )
    elif quoted < 2.0:
        verdict = (
            "MODERATELY ROBUST. A moderate hidden confounder could explain it. "
            "State this limitation explicitly."
        )
    elif quoted < 4.0:
        verdict = (
            "ROBUST. The hidden confounder would need to be about as strong as "
            "the strongest variable we measured. Possible, but it would have to "
            "be named."
        )
    else:
        verdict = (
            "VERY ROBUST. An unmeasured confounder this strong would be hard to "
            "believe had gone unrecorded in an EHR."
        )

    return EValueResult(
        estimate=float(estimate),
        ci_low=ci_low,
        e_value=ev,
        e_value_ci=ev_ci,
        scale=scale,
        interpretation=verdict,
        notes=note,
    )


# ═════════════════════════════════════════════════════════════════════════════
# CLOSING THE LOOP — checking the E-value against a confounder we can SEE
# ═════════════════════════════════════════════════════════════════════════════

def oracle_confounder_strength(cohort, column: str = "hidden_frailty") -> dict:
    """Measure how strong the hidden confounder ACTUALLY is, and compare it to
    the E-value that was supposed to warn us about it.

    In real research this function is impossible. The unmeasured confounder is
    unmeasured — that is what the word means. You compute an E-value, you argue
    about plausibility, and you never find out who was right.

    Here we can find out, because we authored the world. That makes this one of
    the most valuable things in the whole project: it *validates the E-value as
    a tool*, on a case where we know the answer.

    The check: convert the hidden variable's association with treatment and with
    outcome onto the same approximate risk-ratio scale the E-value uses, take
    the weaker of the two (a confounder is only as strong as its weaker leg —
    it must move BOTH treatment and outcome to create bias), and see whether it
    clears the E-value threshold.

        strength >= E-value  ->  a confounder this strong CAN erase the finding,
                                 and one exists. The E-value warned us
                                 correctly, and we should have listened.
        strength <  E-value  ->  this confounder is too weak to overturn the
                                 result, even though it biases it somewhat.
    """
    df = cohort.data
    from .data import OUTCOME, TREATMENT

    u = df[column].to_numpy(float)
    t = df[TREATMENT].to_numpy(int)
    y = df[OUTCOME].to_numpy(float)

    u_sd = u.std(ddof=1)
    if u_sd == 0:
        return {
            "column": column,
            "present": False,
            "note": (
                f"{column!r} has zero variance in this scenario — there is no "
                "hidden confounder to find. Nothing to check."
            ),
        }

    # Leg 1: how much does the hidden trait shift the chance of treatment?
    # Expressed as a risk ratio between the top and bottom third of U.
    hi, lo = np.quantile(u, 0.75), np.quantile(u, 0.25)
    p_hi, p_lo = t[u >= hi].mean(), t[u <= lo].mean()
    rr_treatment = float(max(p_hi, p_lo) / max(min(p_hi, p_lo), 1e-9))

    # Leg 2: how much does it shift the outcome? Standardise, then use the same
    # Chinn (2000) conversion the E-value itself relies on, so the two numbers
    # are on one scale and the comparison is fair.
    d_outcome = float(abs(y[u >= hi].mean() - y[u <= lo].mean()) / y.std(ddof=1))
    rr_outcome = float(np.exp(0.91 * d_outcome))

    # A confounder is only as strong as its weaker leg.
    strength = min(rr_treatment, rr_outcome)

    return {
        "column": column,
        "present": True,
        "rr_treatment_leg": rr_treatment,
        "rr_outcome_leg": rr_outcome,
        "confounder_strength": strength,
        "explanation": (
            f"The unrecorded trait multiplies the odds of getting the drug by "
            f"~{rr_treatment:.2f} and the outcome risk by ~{rr_outcome:.2f}. "
            f"Its effective strength as a confounder is the weaker leg, "
            f"~{strength:.2f}."
        ),
    }


def evalue_verdict(cohort, sensitivity: EValueResult, column="hidden_frailty") -> str:
    """Was the E-value's warning correct? Answerable only because we cheated.

    Print this straight after the audit in Act 9. It is the difference between
    "we computed a sensitivity analysis" and "we showed our sensitivity analysis
    works".
    """
    s = oracle_confounder_strength(cohort, column)
    quoted = sensitivity.e_value_ci or sensitivity.e_value

    if not s["present"]:
        return (
            f"E-value quoted: {quoted:.2f}\n"
            f"{s['note']}\n"
            "In this scenario the estimate is unbiased, and the E-value is "
            "simply telling us how much protection we have against a confounder "
            "that does not happen to exist here."
        )

    strength = s["confounder_strength"]
    if strength >= quoted:
        judgement = (
            f"THE E-VALUE WAS RIGHT, AND WE SHOULD HAVE LISTENED.\n"
            f"    A confounder of strength >= {quoted:.2f} would erase this "
            f"finding, and the one hiding in this data has strength "
            f"{strength:.2f}. That is exactly what happened: every method "
            f"returned the wrong sign, every balance check passed, and the "
            f"E-value was the only diagnostic that pointed at the danger."
        )
    else:
        judgement = (
            f"THE FINDING SURVIVES THIS PARTICULAR CONFOUNDER.\n"
            f"    It would take strength >= {quoted:.2f} to erase the result, "
            f"and this one is only {strength:.2f}. It biases the estimate but "
            f"cannot overturn the conclusion."
        )

    return (
        f"E-value quoted            : {quoted:.2f}\n"
        f"Actual confounder strength: {strength:.2f}   "
        f"(treatment leg {s['rr_treatment_leg']:.2f}, "
        f"outcome leg {s['rr_outcome_leg']:.2f})\n\n"
        f"{judgement}"
    )


# ═════════════════════════════════════════════════════════════════════════════
# One call that runs every check and returns a go / no-go
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class AssumptionAudit:
    """A single go/no-go verdict, with each assumption's status attached."""

    overlap: OverlapReport
    balance: pd.DataFrame
    sensitivity: EValueResult
    n_unbalanced_after: int
    safe_to_report: bool

    def __str__(self) -> str:
        head = "SAFE TO REPORT" if self.safe_to_report else "NOT SAFE TO REPORT"
        return (
            f"════ ASSUMPTION AUDIT: {head} ════\n\n"
            f"1. SUTVA          not testable — argued from the setting\n"
            f"                  (a chronic oral drug; no interference between "
            f"patients)\n\n"
            f"2. {self.overlap}\n\n"
            f"3. BALANCE (evidence, not assumption)\n"
            f"                  covariates still unbalanced after weighting: "
            f"{self.n_unbalanced_after}\n"
            f"                  CAUTION: balance proves we adjusted for what we "
            f"MEASURED.\n"
            f"                  It says nothing whatever about what we did not "
            f"measure.\n"
            f"                  Perfect balance is necessary, never sufficient.\n\n"
            f"4. {self.sensitivity}\n"
        )


def audit_assumptions(
    X,
    T,
    Y,
    covariate_names,
    propensity,
    estimate: float,
    ci_low: float | None = None,
) -> AssumptionAudit:
    """Run every diagnostic and return one honest verdict.

    Called before any estimate is shown to a clinician. If `safe_to_report` is
    False, the CDSS in `cdss.py` refuses to personalise and falls back to the
    population-level guideline recommendation — which is the correct, humble
    behaviour, and exactly what a regulator would want to see.
    """
    T = np.asarray(T, int)
    e = np.asarray(propensity, float)
    weights = np.where(T == 1, 1.0 / np.clip(e, 1e-6, 1), 1.0 / np.clip(1 - e, 1e-6, 1))

    ov = overlap_report(e, T)
    bal = balance_table(X, T, covariate_names, weights=weights)
    n_bad = int((bal["SMD after"].abs() >= SMD_THRESHOLD).sum())
    sens = e_value(estimate, ci_low=ci_low, sd=float(np.std(Y, ddof=1)))

    safe = (
        "VIOLATED" not in ov.verdict
        and n_bad == 0
        and (sens.e_value_ci or sens.e_value) >= 1.25
    )
    return AssumptionAudit(
        overlap=ov,
        balance=bal,
        sensitivity=sens,
        n_unbalanced_after=n_bad,
        safe_to_report=safe,
    )
