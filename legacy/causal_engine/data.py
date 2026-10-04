"""
ACT 1 — Build a world where we KNOW the truth.
==============================================

Why synthetic data, when we have real diabetes datasets sitting in `Datasets/`?

Because of a problem that has nothing to do with programming and everything to
do with logic:

    On real patient data, the true causal effect is UNKNOWABLE.
    You never observe what would have happened to a patient under the other drug.
    So you can never grade your estimator. You can only hope.

So we do what physicists do with a wind tunnel: we build a small world whose
rules we wrote ourselves. Because we author the true treatment effect for every
patient, we can run each method and *score it against the answer key*. Once a
method is proven to recover a truth we planted, we have earned the right to
point it at real data.

This module authors that world.

--------------------------------------------------------------------------------
THE STORY
--------------------------------------------------------------------------------
Patients with Type-2 diabetes come to a clinic. Each gets either:

    T = 0   Metformin      (the standard, cheap, first-line drug)
    T = 1   an SGLT2 inhibitor  (newer, more expensive)

Outcome Y = how much their HbA1c fell after 6 months. Higher = better.

THE TRUE EFFECT WE PLANT (the answer key):

    true_cate = 1.5 + 0.035*(BMI - 30) - 2.5 * max(0, (70 - eGFR)/25)

On average SGLT2i lowers HbA1c about 0.95 points more than Metformin — but that
average hides the thing that matters. Heavier patients benefit MORE, and
patients with failing kidneys benefit LESS, to the point where below about
eGFR 55 the drug is actively worse than Metformin. Both gradients are real
pharmacology: the drug works by making the kidney flush glucose into the urine,
so it needs a functioning kidney to work at all.

About 16% of our patients are genuinely HARMED by this drug. That is the whole
reason a CDSS needs more than an average: the average says "helpful", and for
one patient in six the average is dangerous advice.

--------------------------------------------------------------------------------
THE ONE DIAL THAT MATTERS: how the doctor chose the drug
--------------------------------------------------------------------------------
The biology stays FIXED across every scenario. The only thing that changes is
*how treatment was assigned*. That is the whole point:

    Confounding is not a property of the disease.
    It is a property of how the data came to exist.

    'rct'                Coin flip. Assignment ignores the patient entirely.
    'mild'               Doctors mildly prefer the new drug for sicker patients.
    'strong'             Doctors strongly prefer the new drug for sicker patients.
    'hidden_confounder'  Doctors are also driven by something NOBODY WROTE DOWN.

Sicker patients do worse no matter what they take. So when sicker patients are
the ones getting the new drug, the new drug inherits the blame for their poor
outcomes. That is confounding by indication, and in the 'strong' scenario it is
severe enough to make a genuinely helpful drug look actively harmful.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# What the analyst is ALLOWED to use.
#
# Note what is absent: `severity`, `hidden_frailty`, `y0`, `y1` and `true_cate`
# are all in the returned DataFrame for teaching purposes, but a real analyst
# would never see them. Passing them to an estimator is cheating; the tests
# assert that we don't.
# ─────────────────────────────────────────────────────────────────────────────
COVARIATES: list[str] = [
    "age",
    "bmi",
    "baseline_hba1c",
    "egfr",
    "has_cvd",
    "has_ckd",
]

TREATMENT = "treatment_sglt2i"
OUTCOME = "hba1c_reduction"

#: Columns that exist only because we built the world. Never feed these to a model.
ORACLE_COLUMNS: list[str] = [
    "severity",
    "hidden_frailty",
    "propensity_true",
    "y0",
    "y1",
    "true_cate",
]


@dataclass(frozen=True)
class Scenario:
    """One way the doctors could have chosen who gets the new drug."""

    name: str
    #: How strongly observed severity drives the prescription (0 = coin flip).
    severity_pull: float
    #: How strongly an UNRECORDED trait drives the prescription.
    hidden_pull: float
    #: How strongly that same unrecorded trait drives the outcome.
    hidden_outcome_effect: float
    #: One-line summary of what this scenario teaches.
    lesson: str
    headline: str = ""

    def describe(self) -> str:
        return f"{self.name:<18s} {self.lesson}"


SCENARIOS: dict[str, Scenario] = {
    "rct": Scenario(
        name="rct",
        severity_pull=0.0,
        hidden_pull=0.0,
        hidden_outcome_effect=0.0,
        headline="Randomised trial — a coin flip decides the drug.",
        lesson=(
            "The naive difference in means is CORRECT. This is exactly why "
            "randomised trials are the gold standard, and the benchmark every "
            "observational method is trying to imitate."
        ),
    ),
    "mild": Scenario(
        name="mild",
        severity_pull=0.15,
        hidden_pull=0.0,
        hidden_outcome_effect=0.0,
        headline="Doctors mildly favour the new drug for sicker patients.",
        lesson=(
            "The naive answer still has the right SIGN but understates the true "
            "benefit by nearly 40%. This is the dangerous case: you would make "
            "the right decision for the wrong reason, and never notice the bias. "
            "Adjustment recovers the truth almost exactly."
        ),
    ),
    "strong": Scenario(
        name="strong",
        severity_pull=0.5,
        hidden_pull=0.0,
        hidden_outcome_effect=0.0,
        headline="Doctors strongly favour the new drug for sicker patients.",
        lesson=(
            "THE SIGN FLIPS. The naive answer says this genuinely helpful drug "
            "HARMS patients. A CDSS built on correlation would withhold an "
            "effective treatment. Adjustment recovers the correct sign and "
            "roughly the correct size."
        ),
    ),
    "hidden_confounder": Scenario(
        name="hidden_confounder",
        severity_pull=0.30,
        hidden_pull=1.2,
        hidden_outcome_effect=2.5,
        headline="A confounder drives everything — and nobody recorded it.",
        lesson=(
            "Adjustment FAILS TOO, and fails quietly. Every method lands near "
            "-1.06 instead of +1.23: the sign is STILL wrong. Note that "
            "adjustment does help a little (naive -1.79 -> AIPW -1.06), which is "
            "exactly what makes this dangerous — the numbers move, so it looks "
            "like the method is working. Causal inference cannot adjust for "
            "something it was never given. This is the honest limit of the "
            "method, and why we report an E-value instead of pretending."
        ),
    ),
}

DEFAULT_SCENARIO = "strong"


@dataclass
class Cohort:
    """A generated patient world, plus the answer key and its provenance."""

    data: pd.DataFrame
    scenario: Scenario
    #: The average treatment effect we actually planted. This is the number
    #: every estimator is trying to recover.
    true_ate: float
    seed: int
    notes: dict = field(default_factory=dict)

    # Convenience views ────────────────────────────────────────────────────
    @property
    def X(self) -> np.ndarray:
        """Covariate matrix the analyst is allowed to use."""
        return self.data[COVARIATES].to_numpy(dtype=float)

    @property
    def T(self) -> np.ndarray:
        """Treatment: 1 = SGLT2i, 0 = Metformin."""
        return self.data[TREATMENT].to_numpy(dtype=int)

    @property
    def Y(self) -> np.ndarray:
        """Observed outcome: HbA1c reduction (higher is better)."""
        return self.data[OUTCOME].to_numpy(dtype=float)

    @property
    def true_cate(self) -> np.ndarray:
        """The answer key: each patient's real individual treatment effect."""
        return self.data["true_cate"].to_numpy(dtype=float)

    @property
    def naive_estimate(self) -> float:
        """What you get by just comparing the two groups' averages."""
        y, t = self.Y, self.T
        return float(y[t == 1].mean() - y[t == 0].mean())

    def summary(self) -> str:
        t = self.T
        return (
            f"scenario={self.scenario.name!r}  n={len(self.data)}  "
            f"treated={int(t.sum())} ({t.mean():.0%})  "
            f"TRUE ATE={self.true_ate:+.4f}  naive={self.naive_estimate:+.4f}  "
            f"naive error={self.naive_estimate - self.true_ate:+.4f}"
        )


def authored_cate(bmi, egfr):
    """THE ANSWER KEY, as a function anyone can call.

        true_cate = 1.5 + 0.035*(BMI - 30) - 2.5 * max(0, (70 - eGFR)/25)

    Exposed on its own rather than buried inside the generator for one reason:
    the CDSS demo uses hand-written patients who are not rows in any cohort, and
    being able to print their TRUE effect alongside the model's estimate is what
    makes the demo *checkable* rather than merely plausible.

    Depends on BMI and eGFR only — the outcome noise, the confounding, and the
    hidden frailty all live elsewhere. That separation is deliberate: it means
    the scenario dial can make estimation arbitrarily hard without ever moving
    the target the estimators are aiming at.
    """
    bmi = np.asarray(bmi, dtype=float)
    egfr = np.asarray(egfr, dtype=float)
    renal_penalty = 2.5 * np.maximum(0.0, (70.0 - egfr) / 25.0)
    return 1.5 + 0.035 * (bmi - 30.0) - renal_penalty


def generate_cohort(
    n_patients: int = 4000,
    scenario: str | Scenario = DEFAULT_SCENARIO,
    seed: int = 7,
    violate_positivity: bool = False,
) -> Cohort:
    """Author a synthetic diabetes cohort with a known causal effect.

    Parameters
    ----------
    n_patients
        Number of patients to create.
    scenario
        Key of :data:`SCENARIOS` (or a :class:`Scenario`). Controls *only* how
        treatment was assigned — never the underlying biology.
    seed
        Random seed, so every number in the notebook is reproducible.
    violate_positivity
        If True, apply a hard clinical rule: patients with eGFR < 60 are
        *never* prescribed SGLT2i. This deliberately breaks the positivity
        assumption so Act 4 can show what a broken overlap plot looks like.

    Returns
    -------
    Cohort
        The data plus the answer key.
    """
    sc = SCENARIOS[scenario] if isinstance(scenario, str) else scenario
    rng = np.random.default_rng(seed)

    # ── 1. Who walks into the clinic ────────────────────────────────────────
    age = rng.normal(58, 12, n_patients).clip(25, 85)
    bmi = rng.normal(31, 6, n_patients).clip(18, 55)
    baseline_hba1c = rng.normal(8.5, 1.5, n_patients).clip(6.0, 14.0)
    egfr = rng.normal(75, 20, n_patients).clip(15, 120)
    has_cvd = rng.binomial(1, 0.30, n_patients)
    has_ckd = (egfr < 45).astype(int)  # CKD stage 3b+ by definition

    # ── 2. "How sick is this patient?" ──────────────────────────────────────
    # One standardised index combining the three things a clinician actually
    # eyeballs: glycaemic control, kidney function, and age. This single
    # variable is the engine of the entire confounding story, because it
    # drives BOTH the prescription AND the outcome.
    severity = (
        (baseline_hba1c - 8.5) / 1.5
        + (60.0 - egfr) / 20.0
        + (age - 58.0) / 12.0
    )

    # An unrecorded trait: frailty, health literacy, physician caution,
    # socio-economic status — whatever real-world force never makes it into a
    # structured EHR field. In most scenarios it is inert.
    hidden_frailty = rng.normal(0, 1, n_patients)

    # ── 3. How the doctor chose the drug (THE ONLY THING THAT VARIES) ───────
    # A plain logistic function of severity (and, in one scenario, of the
    # hidden trait). Deliberately NOT clipped: a logistic curve never actually
    # reaches 0 or 1, so every patient keeps a genuine chance of either drug
    # and the positivity assumption holds automatically.
    #
    # (An earlier draft hard-clipped this to [0.05, 0.95]. That looks harmless
    #  and is actively harmful: a clipped curve is a shape no logistic model can
    #  reproduce, so our propensity model over-shot into the tails, weights hit
    #  100, and IPW blew up. Lesson worth keeping: when you simulate data to
    #  test an estimator, simulate something the estimator can actually fit,
    #  or you end up debugging your own scaffolding instead of the method.)
    logit = sc.severity_pull * severity + sc.hidden_pull * hidden_frailty
    propensity_true = 1.0 / (1.0 + np.exp(-logit))

    if violate_positivity:
        # A hard contraindication-style rule. Now there is a whole region of
        # patient space (eGFR < 60) containing zero treated patients, so no
        # honest comparison is possible there.
        propensity_true = np.where(egfr < 60, 0.0, propensity_true)

    treatment = rng.binomial(1, propensity_true)

    # ── 4. THE ANSWER KEY: each patient's true individual effect ────────────
    # This is the formula the whole project is trying to rediscover:
    #
    #     true_cate = 1.5 + 0.035*(BMI - 30) - 2.5 * max(0, (70 - eGFR)/25)
    #
    # Two clinically real gradients, both taken from how SGLT2 inhibitors
    # actually behave:
    #
    #   BMI  ->  bigger benefit in heavier patients. SGLT2i cause glucose (and
    #            therefore calorie) loss through the urine, so heavier patients
    #            get more out of them.
    #
    #   eGFR ->  the benefit COLLAPSES, and eventually reverses, as kidney
    #            function falls. This is not a modelling convenience: the drug
    #            works by making the kidney dump glucose into the urine, so a
    #            kidney that has stopped filtering cannot deliver the mechanism.
    #            Below roughly eGFR 55 the effect crosses zero and the drug
    #            becomes actively worse than Metformin for glycaemic control.
    #
    # The second gradient is what makes this project about DECISIONS rather than
    # averages. About 16% of our patients are genuinely harmed by the drug, so
    # "give it to everyone" is a real clinical error, and a method that only
    # recovers the average (+0.95, helpful) cannot tell you which patients to
    # leave alone. That is precisely the gap a CDSS has to fill.
    true_cate = authored_cate(bmi, egfr)
    # ── 5. Both potential outcomes ─────────────────────────────────────────
    # y0 = what happens on Metformin.  y1 = what happens on SGLT2i.
    # We compute BOTH for every patient. In reality you only ever see one —
    # that is the Fundamental Problem of Causal Inference, and Act 1 shows it
    # by physically hiding one column.
    noise = rng.normal(0, 0.3, n_patients)
    y0 = (
        0.5                                        # everyone improves a little
        - 1.4 * severity                           # sicker patients do worse
        - sc.hidden_outcome_effect * hidden_frailty  # ...and so do frail ones
        + noise
    )
    y1 = y0 + true_cate

    # The observed outcome: we see y1 for the treated, y0 for everyone else.
    observed = np.where(treatment == 1, y1, y0)

    # ── 6. Extra structure for the DAG demonstrations in Act 3 ─────────────
    # A MEDIATOR: the drug works partly by being taken. Adjusting for a
    # mediator destroys the very effect you are trying to measure.
    adherence = np.clip(
        0.75 + 0.10 * treatment - 0.05 * severity + rng.normal(0, 0.10, n_patients),
        0.0,
        1.0,
    )
    # A side effect caused by the treatment.
    adverse_event = rng.binomial(
        1, np.clip(0.05 + 0.10 * treatment + 0.15 * (egfr < 45), 0.01, 0.95)
    )
    # A COLLIDER: hospitalisation is caused by side effects AND by bad glucose
    # control. Filtering on it manufactures a correlation that does not exist.
    hosp_logit = -2.0 + 1.8 * adverse_event + 1.5 * (observed < 0.0)
    hospitalised = rng.binomial(1, 1.0 / (1.0 + np.exp(-hosp_logit)))

    df = pd.DataFrame(
        {
            "patient_id": np.arange(1, n_patients + 1),
            # ── covariates the analyst may use ──
            "age": np.round(age, 1),
            "bmi": np.round(bmi, 1),
            "baseline_hba1c": np.round(baseline_hba1c, 2),
            "egfr": np.round(egfr, 1),
            "has_cvd": has_cvd,
            "has_ckd": has_ckd,
            # ── treatment and outcome ──
            TREATMENT: treatment,
            OUTCOME: np.round(observed, 4),
            # ── downstream structure (mediator / collider) ──
            "adherence": np.round(adherence, 3),
            "adverse_event": adverse_event,
            "hospitalised": hospitalised,
            # ── ORACLE columns: only exist because we built the world ──
            "severity": np.round(severity, 4),
            "hidden_frailty": np.round(hidden_frailty, 4),
            "propensity_true": np.round(propensity_true, 4),
            "y0": np.round(y0, 4),
            "y1": np.round(y1, 4),
            "true_cate": np.round(true_cate, 4),
        }
    )

    return Cohort(
        data=df,
        scenario=sc,
        true_ate=float(true_cate.mean()),
        seed=seed,
        notes={
            "violate_positivity": violate_positivity,
            "true_cate_formula": "1.5 + 0.035*(bmi-30) - 2.5*max(0,(70-egfr)/25)",
            "fraction_harmed": float((true_cate < 0).mean()),
            "min_true_propensity": float(propensity_true.min()),
            "max_true_propensity": float(propensity_true.max()),
        },
    )


def confounding_table(cohort: Cohort) -> pd.DataFrame:
    """*Who* actually got the new drug? The evidence that groups differ.

    This is the single most persuasive table in the whole project. Before any
    mathematics, it shows that the two groups being compared were never
    comparable in the first place.
    """
    df = cohort.data
    grouped = df.groupby(TREATMENT)[COVARIATES + ["severity"]].mean().T
    grouped.columns = ["Metformin (T=0)", "SGLT2i (T=1)"]
    grouped["difference"] = grouped["SGLT2i (T=1)"] - grouped["Metformin (T=0)"]

    # Standardised mean difference: the difference expressed in pooled standard
    # deviations, so variables on different scales stay comparable.
    # Convention: |SMD| > 0.1 means the groups are meaningfully unbalanced.
    smd = []
    for col in grouped.index:
        a = df.loc[df[TREATMENT] == 1, col]
        b = df.loc[df[TREATMENT] == 0, col]
        pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2.0)
        smd.append(0.0 if pooled == 0 else (a.mean() - b.mean()) / pooled)
    grouped["SMD"] = smd
    grouped["balanced?"] = np.where(np.abs(grouped["SMD"]) < 0.1, "yes", "NO")
    return grouped.round(3)


def scenario_comparison(
    n_patients: int = 4000, seed: int = 7
) -> pd.DataFrame:
    """The headline table: what the naive answer says in each of the four worlds.

    Deliberately uses only the naive estimator, so it can be shown in Act 2
    *before* any adjustment method has been introduced.
    """
    rows = []
    for key, sc in SCENARIOS.items():
        c = generate_cohort(n_patients=n_patients, scenario=key, seed=seed)
        naive = c.naive_estimate
        rows.append(
            {
                "scenario": key,
                "treated %": round(100 * c.T.mean(), 1),
                "naive answer": round(naive, 3),
                "TRUE answer": round(c.true_ate, 3),
                "naive error": round(naive - c.true_ate, 3),
                "sign flipped?": "YES — says the drug HARMS" if naive < 0 < c.true_ate else "no",
            }
        )
    return pd.DataFrame(rows)


def load_pima(path: str = "Datasets/diabetes.csv") -> pd.DataFrame:
    """Load the real Pima Indians dataset — used ONLY in the honesty appendix.

    Important caveat, stated up front: this dataset has **no treatment column**.
    `Outcome` is a diagnosis (does this person have diabetes?), not an
    intervention someone chose to give. It is a *prediction* dataset. Running a
    treatment-effect estimator on it produces a number, but that number is not
    a causal effect of anything. Act 9 explains why in detail.
    """
    return pd.read_csv(path)
