"""
ACT 6 — Prove the hand-written maths is actually correct.
========================================================

Everything in `estimators.py` was written from scratch in NumPy so it could be
explained line by line. That transparency is worth nothing if the code is wrong.

So this module puts our ~15-line functions next to Microsoft's DoWhy and EconML
— libraries with hundreds of contributors and years of testing — and checks they
agree. Two independent implementations landing on the same number to three
decimal places is strong evidence that both are right, because there is no
plausible way for two different codebases to be wrong in the same direction.

    "My 12-line IPW function agrees with DoWhy's to 4 decimal places"

is a much better sentence in a viva than "I called DoWhy and it returned 1.22".
It means you can explain the number AND you have checked it.

--------------------------------------------------------------------------------
REFUTATION TESTS — the other half of this act
--------------------------------------------------------------------------------
Agreement between libraries only proves we computed the estimand correctly. It
says nothing about whether the estimand answers our question. Refutation tests
attack that, by feeding the pipeline data where the right answer is KNOWN:

    PLACEBO TREATMENT     Replace treatment with a random coin flip.
                          A correct pipeline must now return ~0. If it still
                          reports a large effect, it is manufacturing findings.

    RANDOM COMMON CAUSE   Add an irrelevant random covariate.
                          A correct pipeline must barely move. Large movement
                          means the estimate is unstable to arbitrary choices.

    SUBSET REFUTER        Re-estimate on random 80% subsets.
                          The estimate should wobble a little, not lurch.

    UNOBSERVED CONFOUNDER Simulate a confounder of known strength and watch the
                          estimate bend. This is the E-value's story, run
                          forwards.

Passing these does not prove the answer is right. Failing any of them proves it
is wrong. That asymmetry is what makes them worth running.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import COVARIATES, OUTCOME, TREATMENT


@dataclass
class Comparison:
    """One of our numbers, next to a library's number for the same estimand."""

    estimand: str
    ours: float
    theirs: float | None
    library: str
    truth: float
    error: str | None = None
    #: True when both sides implement the SAME estimator, so they should agree
    #: to numerical precision. False when we are comparing two different
    #: estimators of the same quantity, where "close" is the correct
    #: expectation and exact agreement would be surprising.
    same_estimator: bool = True

    @property
    def gap(self) -> float | None:
        if self.theirs is None:
            return None
        return abs(self.ours - self.theirs)

    @property
    def agree(self) -> bool:
        g = self.gap
        if g is None:
            return False
        return g < (0.02 if self.same_estimator else 0.10)



def _quiet():
    """DoWhy and EconML are chatty and emit deprecation noise. Silence it, so
    the table is readable in a live demo."""
    import logging

    warnings.filterwarnings("ignore")
    for name in ("dowhy", "econml", "sklearn", "py4j", "numba"):
        logging.getLogger(name).setLevel(logging.ERROR)


# ═════════════════════════════════════════════════════════════════════════════
# DoWhy — the 4-step causal workflow, compared against our hand-rolled IPW
# ═════════════════════════════════════════════════════════════════════════════

def dowhy_comparison(cohort, n_strata: int = 10) -> list[Comparison]:
    """Run DoWhy's IPW and stratification, and compare with ours.

    DoWhy's contribution is the *discipline*, not the arithmetic: it forces you
    to declare a graph, derive an estimand from it, choose an estimator, and then
    refute the result. Our code does the same arithmetic but skips the paperwork,
    which is fine for teaching and not fine for a real study.

    A fair comparison needs matched settings. DoWhy's stratification defaults to
    `num_strata='auto'` (which picks ~50); ours defaults to 5. Comparing those
    two would look like a disagreement between implementations when it is really
    a disagreement about a tuning knob. So we pin both to `n_strata` and let
    :func:`strata_sensitivity` show the knob's effect separately.
    """
    from .estimators import estimate_propensity, ipw_ate, stratified_effect

    _quiet()
    results: list[Comparison] = []
    df = cohort.data
    X, T, Y = cohort.X, cohort.T, cohort.Y

    # ── our numbers ──────────────────────────────────────────────────────────
    ps = estimate_propensity(X, T)
    our_ipw = ipw_ate(Y, T, ps.scores, stabilise=True).value
    our_strat = stratified_effect(X, T, Y, n_strata=n_strata).value

    try:
        from dowhy import CausalModel

        # A graph in DOT form. Only the confounders appear: adherence and
        # hospitalisation are deliberately absent, per Act 3.
        confounders = " ".join(f"{c};" for c in COVARIATES)
        edges = " ".join(
            f"{c} -> {TREATMENT}; {c} -> {OUTCOME};" for c in COVARIATES
        )
        graph = f"digraph {{ {confounders} {TREATMENT}; {OUTCOME}; {edges} "\
                f"{TREATMENT} -> {OUTCOME}; }}"

        model = CausalModel(
            data=df[COVARIATES + [TREATMENT, OUTCOME]],
            treatment=TREATMENT,
            outcome=OUTCOME,
            graph=graph,
        )
        estimand = model.identify_effect(proceed_when_unidentifiable=True)

        dw_ipw = model.estimate_effect(
            estimand,
            method_name="backdoor.propensity_score_weighting",
            target_units="ate",
            method_params={"weighting_scheme": "ips_stabilized_weight"},
        )
        results.append(
            Comparison("ATE via IPW", our_ipw, float(dw_ipw.value), "DoWhy",
                       cohort.true_ate)
        )

        dw_strat = model.estimate_effect(
            estimand,
            method_name="backdoor.propensity_score_stratification",
            target_units="ate",
            method_params={"num_strata": n_strata, "clipping_threshold": 1},
        )
        results.append(
            Comparison(f"ATE via stratification ({n_strata} strata)", our_strat,
                       float(dw_strat.value), "DoWhy", cohort.true_ate)
        )
    except Exception as exc:  # pragma: no cover - environment dependent
        results.append(
            Comparison("ATE via IPW", our_ipw, None, "DoWhy", cohort.true_ate,
                       error=f"{type(exc).__name__}: {exc}")
        )
    return results


def strata_sensitivity(cohort, counts=(5, 10, 20, 50)) -> pd.DataFrame:
    """How much does the answer depend on how many buckets you chose?

    Worth its own table, because it makes a bias-variance trade-off visible in
    a single column of numbers:

        TOO FEW strata   Each bucket still contains a wide range of patients, so
                         confounding survives *inside* the bucket. Biased.
        TOO MANY strata  Each bucket contains a handful of people, so the
                         within-bucket comparison is mostly noise. Noisy.

    On the `strong` cohort the pattern is textbook: 5 strata under-recovers the
    effect (+0.79 vs a truth of +0.96), 10-20 strata land on it, and 50 strata
    start to overshoot as the buckets thin out.

    The second thing this table shows is *why* our 5-strata number differs from
    DoWhy's. With coarse buckets, small choices about how to weight the strata
    matter a lot; with finer buckets those choices wash out and the two
    implementations converge to within 0.003. Disagreement at 5 strata is not a
    bug in either codebase — it is the estimator being genuinely unstable there,
    which is itself the reason to prefer a method that does not need the knob.
    """
    from .estimators import stratified_effect

    rows = []
    for k in counts:
        est = stratified_effect(cohort.X, cohort.T, cohort.Y, n_strata=k)
        rows.append(
            {
                "n_strata": k,
                "estimate": round(est.value, 4),
                "truth": round(cohort.true_ate, 4),
                "error": round(est.value - cohort.true_ate, 4),
                "avg patients/stratum": len(cohort.Y) // k,
            }
        )
    return pd.DataFrame(rows)



# ═════════════════════════════════════════════════════════════════════════════
# EconML — metalearners and DML, compared against our hand-rolled versions
# ═════════════════════════════════════════════════════════════════════════════

def econml_comparison(cohort) -> list[Comparison]:
    """Compare our S/T/X-learners and AIPW against EconML's implementations.

    The T-learner is the sharpest test, because it is the simplest: fit one
    model per arm, subtract. If our number and EconML's disagree there, one of
    us has a bug, and it is almost certainly us.
    """
    from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
    from sklearn.linear_model import LogisticRegressionCV

    from .estimators import aipw_ate, s_learner, t_learner, x_learner

    _quiet()
    results: list[Comparison] = []
    X, T, Y = cohort.X, cohort.T, cohort.Y
    truth = cohort.true_ate

    ours = {
        "S-learner": s_learner(X, T, Y).cate_in_sample.mean(),
        "T-learner": t_learner(X, T, Y).cate_in_sample.mean(),
        "X-learner": x_learner(X, T, Y).cate_in_sample.mean(),
    }
    our_aipw = aipw_ate(X, T, Y, cross_fit=True).value

    def gbr():
        return GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.05, random_state=0
        )

    try:
        from econml.metalearners import SLearner, TLearner, XLearner

        pairs = [
            ("S-learner", SLearner(overall_model=gbr())),
            ("T-learner", TLearner(models=gbr())),
            (
                "X-learner",
                XLearner(
                    models=gbr(),
                    propensity_model=GradientBoostingClassifier(
                        n_estimators=100, max_depth=3, random_state=0
                    ),
                ),
            ),
        ]
        for name, learner in pairs:
            try:
                learner.fit(Y, T, X=X)
                theirs = float(np.mean(learner.effect(X)))
                results.append(
                    Comparison(f"CATE mean, {name}", float(ours[name]), theirs,
                               "EconML", truth)
                )
            except Exception as exc:  # pragma: no cover
                results.append(
                    Comparison(f"CATE mean, {name}", float(ours[name]), None,
                               "EconML", truth, error=str(exc)[:90])
                )
    except Exception as exc:  # pragma: no cover
        for name, val in ours.items():
            results.append(
                Comparison(f"CATE mean, {name}", float(val), None, "EconML",
                           truth, error=f"import failed: {exc}")
            )

    # LinearDML is a different estimator, not a reimplementation of AIPW, so we
    # expect closeness rather than agreement. Flagged as such rather than
    # quietly scored against a threshold it was never meant to meet.
    try:
        from econml.dml import LinearDML

        dml = LinearDML(
            model_y=gbr(),
            model_t=LogisticRegressionCV(max_iter=3000),
            discrete_treatment=True,
            cv=5,
            random_state=0,
        )
        dml.fit(Y, T, X=X, W=None)
        results.append(
            Comparison("ATE: our AIPW vs LinearDML", our_aipw,
                       float(dml.ate(X)), "EconML", truth, same_estimator=False)
        )
    except Exception as exc:  # pragma: no cover
        results.append(
            Comparison("ATE: our AIPW vs LinearDML", our_aipw, None, "EconML",
                       truth, error=str(exc)[:90], same_estimator=False)
        )
    return results


def crosscheck_table(cohort, n_strata: int = 10) -> pd.DataFrame:
    """The full side-by-side. This is the table to put in the report.

    Read the `verdict` column, not the `gap` column, because the rows are not
    all asking the same question:

        same estimator, two codebases
            Our code and theirs implement the identical formula. They should
            agree to numerical precision, and the bar is a gap under 0.02. A
            failure here means one of us has a bug.

        different estimators, same target
            Our AIPW and EconML's LinearDML both estimate the ATE, by different
            routes with different nuisance models. They should be *close*; exact
            agreement would be a coincidence. The bar is 0.10, and saying so
            openly is better than quietly hoping nobody checks.
    """
    rows = []
    for c in dowhy_comparison(cohort, n_strata=n_strata) + econml_comparison(cohort):
        if c.theirs is None:
            verdict = "could not run"
        elif c.agree:
            verdict = "AGREE" if c.same_estimator else "close (as expected)"
        else:
            verdict = "DISAGREE — investigate"
        rows.append(
            {
                "estimand": c.estimand,
                "ours (hand-written)": round(c.ours, 4),
                "library": c.library,
                "theirs": None if c.theirs is None else round(c.theirs, 4),
                "gap": None if c.gap is None else round(c.gap, 4),
                "comparison": (
                    "same estimator" if c.same_estimator else "different estimator"
                ),
                "verdict": verdict,
                "truth": round(c.truth, 4),
                "note": c.error or "",
            }
        )
    return pd.DataFrame(rows)



# ═════════════════════════════════════════════════════════════════════════════
# REFUTATION — try to break our own result
# ═════════════════════════════════════════════════════════════════════════════

def placebo_test(cohort, n_trials: int = 10, seed: int = 0) -> dict:
    """Replace the real treatment with a coin flip. The effect must vanish.

    This is the single most valuable test in the whole module, because it
    directly checks the failure mode we should fear most: a pipeline that
    reports impressive findings from noise. If our machinery returns +0.98 for
    the real treatment and +0.98 for a random one, the +0.98 was never about
    the drug.
    """
    from .estimators import aipw_ate

    rng = np.random.default_rng(seed)
    X, Y = cohort.X, cohort.Y
    vals = []
    for _ in range(n_trials):
        fake_T = rng.binomial(1, 0.5, len(Y))
        # cross_fit=False here purely for speed: ten cross-fitted AIPW runs is
        # slow enough to hurt in a live demo, and cross-fitting cannot rescue a
        # placebo effect from zero — the two agree to three decimals when
        # checked. The real estimate below IS cross-fitted, as it is reported.
        vals.append(aipw_ate(X, fake_T, Y, cross_fit=False).value)

    vals = np.asarray(vals)
    real = aipw_ate(X, cohort.T, Y, cross_fit=True).value
    passed = bool(abs(vals.mean()) < 0.1 and abs(vals.mean()) < 0.25 * abs(real))
    return {
        "test": "placebo treatment (random coin flip)",
        "real_estimate": real,
        "placebo_mean": float(vals.mean()),
        "placebo_sd": float(vals.std(ddof=1)),
        "placebo_max_abs": float(np.abs(vals).max()),
        "n_trials": n_trials,
        "passed": passed,
        "interpretation": (
            "PASS — a random treatment produces no effect, so the real estimate "
            "is tracking something real."
            if passed else
            "FAIL — the pipeline reports an effect even for a random treatment. "
            "Do not trust any number it produces."
        ),
    }


def random_common_cause_test(cohort, n_trials: int = 5, seed: int = 0) -> dict:
    """Add an irrelevant random covariate. The estimate should barely move.

    Tests stability rather than correctness. A pipeline whose answer swings when
    you hand it noise is telling you the answer was never determined by the
    data in the first place.
    """
    from .estimators import aipw_ate

    rng = np.random.default_rng(seed)
    X, T, Y = cohort.X, cohort.T, cohort.Y
    base = aipw_ate(X, T, Y, cross_fit=True).value

    shifts = []
    for _ in range(n_trials):
        noise = rng.normal(0, 1, (len(Y), 1))
        val = aipw_ate(np.hstack([X, noise]), T, Y, cross_fit=True).value
        shifts.append(val - base)

    shifts = np.asarray(shifts)
    passed = bool(np.abs(shifts).max() < 0.1)
    return {
        "test": "random common cause (add a noise covariate)",
        "baseline": base,
        "mean_shift": float(shifts.mean()),
        "max_abs_shift": float(np.abs(shifts).max()),
        "n_trials": n_trials,
        "passed": passed,
        "interpretation": (
            "PASS — irrelevant noise does not move the estimate."
            if passed else
            "FAIL — adding pure noise changed the answer materially. The "
            "estimate is unstable to arbitrary modelling choices."
        ),
    }


def subset_test(cohort, fraction: float = 0.8, n_trials: int = 10, seed: int = 0) -> dict:
    """Re-estimate on random subsets. The answer should wobble, not lurch.

    Distinguishes "we measured something" from "we got lucky with this
    particular sample". Compare the spread across subsets to the standard error
    we reported: if subsets disagree far more than the CI implies, the CI is
    too narrow.
    """
    from .estimators import aipw_ate

    rng = np.random.default_rng(seed)
    X, T, Y = cohort.X, cohort.T, cohort.Y
    full = aipw_ate(X, T, Y, cross_fit=True)
    n = len(Y)
    k = int(fraction * n)

    vals = []
    for _ in range(n_trials):
        idx = rng.choice(n, k, replace=False)
        vals.append(aipw_ate(X[idx], T[idx], Y[idx], cross_fit=True).value)

    vals = np.asarray(vals)
    spread = float(vals.std(ddof=1))
    reported_se = full.std_error or float("inf")
    # Subsets of 80% should disagree by roughly the SE, scaled up for the
    # smaller sample. Allow a factor of 3 before calling it a failure.
    passed = bool(spread < 3.0 * reported_se)
    return {
        "test": f"subset refuter ({fraction:.0%} random subsets)",
        "full_estimate": full.value,
        "reported_se": full.std_error,
        "subset_mean": float(vals.mean()),
        "subset_sd": spread,
        "subset_min": float(vals.min()),
        "subset_max": float(vals.max()),
        "n_trials": n_trials,
        "passed": passed,
        "interpretation": (
            "PASS — subsets agree within roughly the reported uncertainty."
            if passed else
            "FAIL — subsets disagree far more than the confidence interval "
            "implies, so the interval is too narrow."
        ),
    }


def unobserved_confounder_test(cohort, strengths=(0.5, 1.0, 2.0, 3.0), seed=0) -> pd.DataFrame:
    """Simulate a confounder of known strength and watch the estimate bend.

    This is the E-value told forwards. Rather than asking "how strong would a
    confounder have to be?", we build one, dial it up, and record where the
    estimate goes. The row where the sign flips is the honest answer to "how
    much unmeasured confounding can this study tolerate?"

    On the `strong` cohort (truth +0.96) the answer is sobering:

        strength 0.5  ->  +0.78   still helpful, mildly understated
        strength 1.0  ->  +0.46   still the right sign, badly understated
        strength 2.0  ->  -1.07   SIGN FLIPPED. We would now withhold the drug.
        strength 3.0  ->  -3.56   catastrophically wrong

    So the finding survives a weak-to-moderate hidden confounder and does not
    survive a strong one. That is exactly the sentence to say out loud in a
    viva, and it is only sayable because we authored the world — which is the
    whole reason the synthetic cohort exists.
    """
    from .estimators import aipw_ate

    rng = np.random.default_rng(seed)
    X, T, Y = cohort.X, cohort.T, cohort.Y
    n = len(Y)
    rows = []
    for s in strengths:
        # A confounder correlated with treatment, that also shifts the outcome.
        u = rng.normal(0, 1, n) + s * (T - T.mean())
        Y_shift = Y - s * u * 0.5
        val = aipw_ate(X, T, Y_shift, cross_fit=True).value
        flipped = np.sign(val) != np.sign(cohort.true_ate)
        rows.append(
            {
                "confounder strength": s,
                "estimate": round(val, 4),
                "truth": round(cohort.true_ate, 4),
                "bias": round(val - cohort.true_ate, 4),
                "sign flipped?": "YES" if flipped else "no",
                "clinical consequence": (
                    "we would WITHHOLD a drug that helps"
                    if flipped
                    else "right decision, understated benefit"
                ),
            }
        )
    return pd.DataFrame(rows)


def refutation_report(cohort) -> str:
    """Run every refutation test and print a readable verdict block."""
    tests = [
        placebo_test(cohort),
        random_common_cause_test(cohort),
        subset_test(cohort),
    ]
    lines = ["REFUTATION TESTS — trying to break our own result", "=" * 74, ""]
    for t in tests:
        mark = "PASS" if t["passed"] else "FAIL"
        lines.append(f"[{mark}]  {t['test']}")
        for k, v in t.items():
            if k in {"test", "passed", "interpretation"}:
                continue
            lines.append(
                f"           {k:<18s} "
                + (f"{v:+.4f}" if isinstance(v, float) else str(v))
            )
        lines.append(f"           -> {t['interpretation']}")
        lines.append("")

    n_pass = sum(t["passed"] for t in tests)
    lines.append(
        f"{n_pass}/{len(tests)} refutation tests passed.\n\n"
        "Passing these does NOT prove the estimate is correct — no test can, "
        "because\nignorability is untestable. It proves the pipeline is not "
        "manufacturing\nfindings from noise, which is a different and weaker "
        "claim, honestly stated."
    )
    return "\n".join(lines)
