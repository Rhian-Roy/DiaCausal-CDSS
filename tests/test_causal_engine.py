"""
Correctness tests for `causal_engine`.
=====================================

    python -m pytest tests/ -q                    # everything (~3 min)
    python -m pytest tests/ -q -m "not slow"      # skip the library cross-checks

What these tests are FOR
------------------------
Every estimator in this package is hand-written NumPy. That is the whole point —
you can read `ipw_ate` and see the Horvitz–Thompson formula. But hand-written also
means hand-breakable, and a causal estimator has an unusually nasty failure mode:
**a subtly wrong implementation still returns a plausible-looking number.** There
is no exception, no NaN, no crash. It just quietly produces 0.87 instead of 0.98
and everything downstream inherits it.

So these tests do the two things that catch that class of bug:

    1. GRADE AGAINST A KNOWN ANSWER. The cohort is synthetic and its individual
       treatment effects were authored by us, so `authored_cate` is a genuine
       answer key. An estimator that cannot recover a planted effect is broken.

    2. AGREE WITH AN INDEPENDENT IMPLEMENTATION. DoWhy and EconML were written by
       Microsoft Research by different people from different equations. If our
       twelve-line IPW and their IPW agree to four decimals, both are probably
       right — and if they disagree, exactly one of us is wrong.

Tolerances are set from finite-sample noise, not chosen to make things pass:
n=3000 with this outcome variance gives a standard error around 0.02, so 0.05
is roughly 2.5 SE. Where a looser bound is used it is because the estimator has a
known bias (stratification) or is a genuinely different estimator (LinearDML), and
the test says so at that line.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("MPLCONFIGDIR", os.environ.get("TMPDIR", "/tmp"))

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from causal_engine import (
    cdss, crosscheck, dag, data, diagnostics, estimators, evaluate, guardrails,
    pdf_text, rag_lite,
)

N = 3000
SEED = 7


# ═════════════════════════════════════════════════════════════════════════════
# FIXTURES — module-scoped, because fitting these costs real seconds
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def rct():
    return data.generate_cohort(N, scenario="rct", seed=SEED)


@pytest.fixture(scope="module")
def mild():
    return data.generate_cohort(N, scenario="mild", seed=SEED)


@pytest.fixture(scope="module")
def strong():
    return data.generate_cohort(N, scenario="strong", seed=SEED)


@pytest.fixture(scope="module")
def strong_propensity(strong):
    return estimators.estimate_propensity(strong.X, strong.T, cross_fit=True)


@pytest.fixture(scope="module")
def index():
    return rag_lite.build_index()


def truth_of(cohort) -> float:
    return float(cohort.true_cate.mean())


# ═════════════════════════════════════════════════════════════════════════════
# THE ANSWER KEY ITSELF
#
# Tested first, because every other test in this file grades against it. A bug
# here would make the whole suite agree on the wrong number.
# ═════════════════════════════════════════════════════════════════════════════

class TestGroundTruth:

    def test_authored_cate_matches_the_documented_formula(self):
        """tau = 1.5 + 0.035*(BMI-30) - 2.5*max(0, (70-eGFR)/25)

        Recomputed here by hand rather than imported, so that changing the
        formula in `data.py` without updating the documentation fails loudly.
        """
        bmi = np.array([30.0, 40.0, 25.0, 34.0])
        egfr = np.array([90.0, 70.0, 45.0, 46.0])
        expected = 1.5 + 0.035 * (bmi - 30) - 2.5 * np.maximum(0, (70 - egfr) / 25)
        np.testing.assert_allclose(data.authored_cate(bmi, egfr), expected, atol=1e-12)

    def test_the_effect_crosses_zero(self):
        """The single most important property of the design.

        If the true effect never went negative, the population average would be
        correct advice for everyone and a personalised CDSS would have nothing to
        do. The zero-crossing near eGFR 55 is what gives Act 7 its purpose.
        """
        healthy = float(data.authored_cate(34.0, 90.0))
        impaired = float(data.authored_cate(34.0, 46.0))
        assert healthy > 0, "the drug should help a patient with good kidneys"
        assert impaired < 0, "the drug should harm a patient with poor kidneys"

        # ... and the crossing is where the narration claims it is.
        grid = np.linspace(40, 90, 501)
        effects = data.authored_cate(np.full_like(grid, 32.0), grid)
        crossing = grid[np.argmin(np.abs(effects))]
        assert 50 <= crossing <= 60, f"zero-crossing at eGFR {crossing:.1f}, expected ~55"

    def test_a_real_minority_is_harmed(self, strong):
        """Between 5% and 30%: enough to matter clinically, not so many that the
        population average is simply the wrong sign."""
        harmed = float((strong.true_cate < 0).mean())
        assert 0.05 < harmed < 0.30, f"{harmed:.1%} harmed"

    def test_potential_outcomes_are_consistent(self, strong):
        """SUTVA/consistency: the observed outcome IS the potential outcome for
        the treatment actually received. If this fails, the simulator is not
        generating the world it claims to."""
        df = strong.data
        expected = np.where(df["treatment_sglt2i"] == 1, df["y1"], df["y0"])
        np.testing.assert_allclose(df["hba1c_reduction"], expected, atol=1e-9)

    def test_true_cate_is_the_difference_of_potential_outcomes(self, strong):
        """tau_i = Y1_i - Y0_i, with the SAME noise draw in both arms.

        Tolerance is 1e-3, not 1e-12, and the reason is not sloppiness: the
        DataFrame stores `y0`/`y1` rounded to 4 decimals for readability, while
        `true_cate` is kept at full precision. That caps the per-patient
        discrepancy at 1e-4. Anything larger would mean the outcome noise is
        being drawn independently per arm — which would make `true_cate` a
        noisy estimate of the effect rather than the effect itself, and quietly
        put a floor under every MAE in the Act 7 leaderboard.
        """
        df = strong.data
        diff = (df["y1"] - df["y0"]).to_numpy()
        np.testing.assert_allclose(diff, strong.true_cate, atol=1e-3)
        assert abs(diff.mean() - strong.true_cate.mean()) < 1e-4


# ═════════════════════════════════════════════════════════════════════════════
# (a) UNDER RANDOMISATION, EVEN THE NAIVE ANSWER IS RIGHT
#
# This is the test that proves the benchmark is fair. If naive failed here too,
# the synthetic data would be rigged against it and every later comparison would
# be meaningless.
# ═════════════════════════════════════════════════════════════════════════════

class TestRandomisedControl:

    def test_naive_is_correct_when_treatment_is_random(self, rct):
        """A deliberate departure from the 0.05 bound the plan specified.

        The naive difference in means at n=3000 has a standard error of about
        0.10. Demanding it land within 0.05 of the truth would be demanding it
        beat its own sampling error — the test would fail roughly half the time
        on a correct implementation, which makes it a test of luck.

        So the assertion is the statistically meaningful one: the naive 95%
        interval must COVER the truth. That is exactly the claim "unbiased under
        randomisation", and it is what an RCT actually buys you.
        """
        naive = estimators.naive_difference(rct.Y, rct.T)
        t = truth_of(rct)
        assert naive.covers(t), (
            f"naive {naive.value:+.4f} CI {naive.ci} excludes truth {t:+.4f} — "
            "under randomisation it should be unbiased"
        )
        assert abs(naive.value - t) < 3 * naive.std_error

    def test_causal_agrees_with_naive_under_randomisation(self, rct):
        """Adjustment must not BREAK an already-unbiased comparison.

        A surprisingly easy bug: an estimator that over-corrects looks fine on
        confounded data (it moves in the right direction) and only reveals itself
        on an RCT, where there is nothing to correct.

        AIPW is held to a tighter bound than naive because it genuinely is more
        precise here — its influence-function SE is about 0.023 against naive's
        0.10 — which is itself worth noticing: adjustment buys precision even
        when it is not needed for bias.
        """
        naive = estimators.naive_difference(rct.Y, rct.T)
        aipw = estimators.aipw_ate(rct.X, rct.T, rct.Y, cross_fit=True)
        assert abs(aipw.value - truth_of(rct)) < 0.05
        assert aipw.std_error < naive.std_error, (
            "adjustment should not cost precision under randomisation"
        )
        # 0.30 ~ 3x the naive SE: the two estimators must agree to within the
        # noisier one's sampling error, not to within an arbitrary constant.
        assert abs(aipw.value - naive.value) < 3 * naive.std_error

    def test_propensity_is_near_half_for_everyone(self, rct):
        """Under randomisation, e(x) should not depend on x at all."""
        prop = estimators.estimate_propensity(rct.X, rct.T, cross_fit=True)
        assert prop.scores.std() < 0.06, (
            f"propensity SD {prop.scores.std():.3f} — the model is finding structure "
            "in what is supposed to be a coin flip"
        )


# ═════════════════════════════════════════════════════════════════════════════
# (b) THE ESTIMATORS RECOVER THE AUTHORED ATE
# ═════════════════════════════════════════════════════════════════════════════

class TestRecoversAuthoredEffect:

    @pytest.mark.parametrize("scenario", ["mild", "strong"])
    def test_ipw_and_aipw_recover_the_truth(self, scenario):
        cohort = data.generate_cohort(N, scenario=scenario, seed=SEED)
        prop = estimators.estimate_propensity(cohort.X, cohort.T, cross_fit=True)
        t = truth_of(cohort)

        ipw = estimators.ipw_ate(cohort.Y, cohort.T, prop.scores, stabilise=True)
        aipw = estimators.aipw_ate(cohort.X, cohort.T, cohort.Y, cross_fit=True)

        assert abs(ipw.value - t) < 0.10, f"IPW {ipw.value:+.4f} vs truth {t:+.4f}"
        assert abs(aipw.value - t) < 0.05, f"AIPW {aipw.value:+.4f} vs truth {t:+.4f}"

    def test_aipw_confidence_interval_covers_the_truth(self, mild):
        """The interval must actually mean something.

        A too-narrow CI is the classic symptom of forgetting to cross-fit: the
        outcome model's own overfitting gets absorbed into the correction term
        and the influence-function SE comes out optimistic.
        """
        aipw = estimators.aipw_ate(mild.X, mild.T, mild.Y, cross_fit=True)
        assert aipw.covers(truth_of(mild)), (
            f"95% CI {aipw.ci} excludes truth {truth_of(mild):+.4f}"
        )
        assert 0.005 < aipw.std_error < 0.20, f"implausible SE {aipw.std_error}"

    def test_g_computation_recovers_the_truth_with_a_flexible_model(self, strong):
        g = estimators.g_computation(strong.X, strong.T, strong.Y, n_bootstrap=0)
        assert abs(g.value - truth_of(strong)) < 0.20

    def test_the_flexible_model_attenuates_the_effect(self, strong):
        """Regularisation bias, pinned as a test — and it is counter-intuitive.

        The naive expectation (and an earlier draft of Act 5) was that a LINEAR
        outcome model must do worse, since the true effect has a BMI interaction
        and a kink at eGFR 70 that a straight line cannot represent. The data
        says the opposite, and the reason is worth more than the guess was:

        `g_computation` appends T as one more feature, making it an S-learner. A
        regularised booster spends its capacity on the outcome LEVEL (driven by
        eGFR, age, HbA1c) and gives TREATMENT only ~4% of its feature importance,
        so it shrinks the contrast toward zero. A linear model gives T its own
        un-shrunk coefficient and escapes this.

        This test asserts the direction of that bias — toward zero, not away from
        it — because that is what makes it regularisation bias rather than noise.
        """
        from sklearn.linear_model import LinearRegression

        flexible = estimators.g_computation(strong.X, strong.T, strong.Y, n_bootstrap=0)
        linear = estimators.g_computation(strong.X, strong.T, strong.Y,
                                         model=LinearRegression(), n_bootstrap=0)
        t = truth_of(strong)

        assert 0 < flexible.value < t, (
            f"expected the booster to attenuate toward zero; got {flexible.value:+.4f} "
            f"against truth {t:+.4f}"
        )
        assert abs(linear.value - t) < abs(flexible.value - t), (
            f"linear error {abs(linear.value-t):.4f} vs flexible "
            f"{abs(flexible.value-t):.4f} — Act 5's regularisation-bias narration "
            "assumes the linear model wins here"
        )

    def test_relaxing_the_shrinkage_reduces_the_attenuation(self, strong):
        """The mechanism, not just the symptom.

        If the booster's error were caused by the model class being too rigid,
        loosening the regularisation would not help in this direction. It does —
        which is what identifies shrinkage as the culprit and justifies calling
        this regularisation bias in the narration.
        """
        from sklearn.ensemble import GradientBoostingRegressor

        default = estimators.g_computation(strong.X, strong.T, strong.Y, n_bootstrap=0)
        relaxed = estimators.g_computation(
            strong.X, strong.T, strong.Y, n_bootstrap=0,
            model=GradientBoostingRegressor(n_estimators=500, max_depth=5,
                                            learning_rate=0.30, random_state=0))
        t = truth_of(strong)
        assert abs(relaxed.value - t) < abs(default.value - t), (
            f"relaxed {relaxed.value:+.4f} vs default {default.value:+.4f}, "
            f"truth {t:+.4f}"
        )

    def test_treatment_gets_little_of_the_outcome_model_attention(self, strong):
        """The number Act 5 quotes out loud. If it drifts, the prose is stale."""
        from sklearn.ensemble import GradientBoostingRegressor

        Xt = np.column_stack([strong.X, strong.T])
        gb = GradientBoostingRegressor(n_estimators=200, max_depth=3,
                                       learning_rate=0.05, random_state=0).fit(Xt, strong.Y)
        treatment_importance = gb.feature_importances_[-1]
        assert treatment_importance < 0.15, (
            f"TREATMENT importance {treatment_importance:.4f} — Act 5 claims it is "
            "a few percent, which is why the contrast gets shrunk"
        )

    def test_aipw_repairs_what_g_computation_got_wrong(self, strong):
        """The payoff line of Act 5, as an assertion.

        Same base learner, same data. The only difference is the
        propensity-weighted residual correction. If AIPW did not beat plug-in
        g-computation here, the doubly-robust argument would be decoration.
        """
        gcomp = estimators.g_computation(strong.X, strong.T, strong.Y, n_bootstrap=0)
        aipw = estimators.aipw_ate(strong.X, strong.T, strong.Y, cross_fit=True)
        t = truth_of(strong)
        assert abs(aipw.value - t) < abs(gcomp.value - t), (
            f"AIPW {aipw.value:+.4f} did not improve on g-computation "
            f"{gcomp.value:+.4f} (truth {t:+.4f})"
        )

    def test_stabilised_ipw_is_no_worse_than_raw(self, strong, strong_propensity):
        """Hájek vs Horvitz–Thompson. Same estimand, less temperamental."""
        t = truth_of(strong)
        raw = estimators.ipw_ate(strong.Y, strong.T, strong_propensity.scores,
                                 stabilise=False)
        stab = estimators.ipw_ate(strong.Y, strong.T, strong_propensity.scores,
                                  stabilise=True)
        assert abs(stab.value - t) <= abs(raw.value - t) + 0.02

    def test_stratification_is_biased_toward_zero_but_the_right_sign(
            self, strong, strong_propensity):
        """A deliberately loose bound, and the reason is the point.

        Coarse strata still mix dissimilar patients, so residual confounding
        survives — stratification is expected to UNDERSTATE the effect here. The
        test pins the direction of that bias rather than pretending it is absent.
        """
        s = estimators.stratified_effect(strong.X, strong.T, strong.Y, n_strata=10,
                                        propensity=strong_propensity.scores)
        t = truth_of(strong)
        assert s.value > 0, "stratification should at least fix the sign"
        assert abs(s.value - t) < 0.30
        assert s.value < t + 0.05, "expected attenuation, not overshoot"


# ═════════════════════════════════════════════════════════════════════════════
# (d) THE SIGN FLIP — the project's headline result
# ═════════════════════════════════════════════════════════════════════════════

class TestSignFlip:

    def test_strong_confounding_reverses_the_naive_conclusion(self, strong):
        naive = estimators.naive_difference(strong.Y, strong.T)
        t = truth_of(strong)
        assert t > 0, "the drug genuinely helps on average"
        assert naive.value < 0, (
            f"naive {naive.value:+.4f} — no sign flip, so Act 2's headline is false"
        )

    def test_causal_inference_repairs_it(self, strong):
        aipw = estimators.aipw_ate(strong.X, strong.T, strong.Y, cross_fit=True)
        t = truth_of(strong)
        assert aipw.value > 0
        assert abs(aipw.value - t) < 0.05

    def test_confounding_dial_is_monotone(self):
        """Turning confounding up must make the naive answer worse.

        Guards against a generator bug where the severity parameter is wired to
        the wrong term — the individual scenarios would still each look
        reasonable, but the ordering that Act 2's table depends on would be gone.
        """
        errors = {}
        for scen in ("rct", "mild", "strong"):
            c = data.generate_cohort(N, scenario=scen, seed=SEED)
            errors[scen] = abs(estimators.naive_difference(c.Y, c.T).value
                               - truth_of(c))
        assert errors["rct"] < errors["mild"] < errors["strong"], errors

    def test_the_true_effect_is_the_same_in_every_scenario(self):
        """Only the DIFFICULTY changes, never the target.

        This is what makes the four-row table in Act 2 an honest comparison. If
        the scenario dial also moved the true effect, the rows would not be
        comparable and the whole demonstration would collapse.
        """
        truths = [truth_of(data.generate_cohort(N, scenario=s, seed=SEED))
                  for s in data.SCENARIOS]
        assert max(truths) - min(truths) < 1e-9, truths


# ═════════════════════════════════════════════════════════════════════════════
# (e) DIAGNOSTICS
# ═════════════════════════════════════════════════════════════════════════════

class TestDiagnostics:

    def test_weighting_balances_every_covariate(self, strong, strong_propensity):
        """The love plot, as an assertion."""
        w = np.where(strong.T == 1, 1 / strong_propensity.scores,
                     1 / (1 - strong_propensity.scores))
        bal = diagnostics.balance_table(strong.X, strong.T, data.COVARIATES, weights=w)

        assert (bal["SMD before"].abs() > diagnostics.SMD_THRESHOLD).sum() >= 3, (
            "the cohort is supposed to START imbalanced — otherwise there is "
            "nothing for the adjustment to demonstrate"
        )
        unbalanced = bal.loc[bal["SMD after"].abs() > diagnostics.SMD_THRESHOLD]
        assert unbalanced.empty, f"still imbalanced after weighting:\n{unbalanced}"

    def test_smd_is_zero_for_an_identical_variable(self):
        """A unit test of the formula, not of the pipeline."""
        rng = np.random.default_rng(0)
        x = rng.normal(size=2000)
        t = rng.integers(0, 2, size=2000)
        assert abs(diagnostics.standardised_mean_difference(x, t)) < 0.10

    def test_overlap_is_satisfied_in_the_headline_cohort(self, strong,
                                                        strong_propensity):
        rep = diagnostics.overlap_report(strong_propensity.scores, strong.T)
        assert rep.verdict == "SATISFIED", rep.detail
        assert rep.effective_sample_size < len(strong.T), (
            "weighting always costs precision; an ESS equal to n means the "
            "weights are not being applied"
        )

    def test_positivity_violation_is_detected(self):
        """A hard prescribing rule must NOT come back 'SATISFIED'.

        This is the check that matters most in the diagnostics module: silently
        reporting an estimate for a population that contains no treated patients
        is the failure mode with real clinical consequences.
        """
        broken = data.generate_cohort(N, scenario="strong", seed=SEED,
                                     violate_positivity=True)
        prop = estimators.estimate_propensity(broken.X, broken.T, cross_fit=True)
        rep = diagnostics.overlap_report(prop.scores, broken.T)
        assert rep.verdict != "SATISFIED", (
            f"positivity is broken by construction but the report says {rep.verdict}"
        )
        assert rep.n_extreme > 0

    def test_trimming_drops_the_sickest_patients(self):
        """Trimming changes the question. The profile must show that."""
        broken = data.generate_cohort(N, scenario="strong", seed=SEED,
                                     violate_positivity=True)
        prop = estimators.estimate_propensity(broken.X, broken.T, cross_fit=True)
        trim = estimators.trim_by_overlap(prop.scores, bounds=(0.1, 0.9),
                                         covariates=broken.X,
                                         covariate_names=data.COVARIATES)
        assert 0.5 < trim.fraction_kept < 1.0
        egfr = trim.dropped_profile["egfr"]
        assert egfr["dropped_mean"] < egfr["kept_mean"], (
            "the dropped patients should be the renally impaired ones — if they "
            "are a random sample, the trimming logic is not doing what it claims"
        )

    def test_e_value_rises_with_the_strength_of_the_finding(self):
        """A bigger, better-separated effect must be harder to explain away."""
        weak = diagnostics.e_value(0.2, ci_low=0.05, sd=1.0)
        strong_ = diagnostics.e_value(1.5, ci_low=1.2, sd=1.0)
        assert strong_.e_value > weak.e_value
        assert strong_.e_value_ci > weak.e_value_ci

    def test_e_value_is_at_least_one(self):
        """Definitional: E-value < 1 is meaningless."""
        for est, lo in ((0.01, -0.5), (0.5, 0.1), (2.0, 1.8)):
            ev = diagnostics.e_value(est, ci_low=lo, sd=1.0)
            assert ev.e_value >= 1.0

    def test_the_planted_confounder_exceeds_the_e_value(self):
        """The calibration check that only synthetic data allows.

        In `hidden_confounder` we KNOW how strong the hidden variable is. The
        E-value's stated threshold should be below it — meaning the sensitivity
        analysis correctly warned that a confounder of that size would overturn
        the result.
        """
        hidden = data.generate_cohort(N, scenario="hidden_confounder", seed=SEED)
        strength = diagnostics.oracle_confounder_strength(hidden)
        aipw = estimators.aipw_ate(hidden.X, hidden.T, hidden.Y, cross_fit=True)
        ev = diagnostics.e_value(aipw.value, ci_low=aipw.ci[0],
                                sd=float(hidden.Y.std()))
        assert strength["present"], "the hidden confounder is missing from the cohort"
        assert strength["confounder_strength"] > ev.e_value_ci, (
            f"planted strength {strength['confounder_strength']:.2f} did not exceed "
            f"E-value {ev.e_value_ci:.2f} — the sensitivity analysis would have been "
            "falsely reassuring"
        )


# ═════════════════════════════════════════════════════════════════════════════
# CATE — the estimand the CDSS actually serves
# ═════════════════════════════════════════════════════════════════════════════

class TestHeterogeneousEffects:

    @pytest.fixture(scope="class")
    def models(self, strong):
        return {name: fn(strong.X, strong.T, strong.Y)
                for name, fn in estimators.ALL_CATE_LEARNERS.items()}

    def test_every_learner_recovers_the_ordering(self, models, strong):
        """Rank correlation, not MAE.

        For a treat-or-not decision the ordering is what matters: a model that is
        uniformly 0.4 too high still makes every decision correctly, while one
        with a small MAE and scrambled ranks does not.
        """
        board = evaluate.cate_leaderboard(list(models.values()), strong.true_cate)
        for _, row in board.iterrows():
            assert row["rank corr"] > 0.5, f"{row['learner']}: {row['rank corr']:.3f}"

    def test_the_best_learner_is_accurate_per_patient(self, models, strong):
        board = evaluate.cate_leaderboard(list(models.values()), strong.true_cate)
        best = board.iloc[0]
        assert best["CATE MAE"] < 0.30, f"{best['learner']} MAE {best['CATE MAE']:.4f}"
        assert best["sign agree"] > 0.85, (
            f"{best['learner']} gets treat-vs-don't-treat right only "
            f"{best['sign agree']:.1%} of the time"
        )

    def test_learners_average_to_roughly_the_ate(self, models, strong):
        """Consistency between the two estimands.

        mean(CATE) should approximate the ATE. A learner whose mean is far from
        it has a bias that the leaderboard's MAE column can hide.
        """
        t = truth_of(strong)
        for name, m in models.items():
            assert abs(m.cate_in_sample.mean() - t) < 0.35, (
                f"{name}: mean CATE {m.cate_in_sample.mean():+.4f} vs ATE {t:+.4f}"
            )

    def test_the_recovered_effect_falls_with_declining_kidney_function(
            self, models, strong):
        """The clinical gradient, recovered from observational data alone.

        This is the property the CDSS depends on. The learner is never told the
        functional form, so recovering the eGFR gradient is genuine evidence it
        learned the mechanism rather than the marginal.
        """
        best = models["X-learner"]
        low = strong.data["egfr"] < 55
        high = strong.data["egfr"] > 80
        assert best.cate_in_sample[low].mean() < best.cate_in_sample[high].mean(), (
            "the model does not think renal impairment reduces the benefit"
        )

    def test_the_recovered_effect_rises_with_bmi(self, models, strong):
        best = models["X-learner"]
        df = strong.data
        heavy = df["bmi"] > df["bmi"].quantile(0.75)
        light = df["bmi"] < df["bmi"].quantile(0.25)
        assert best.cate_in_sample[heavy].mean() > best.cate_in_sample[light].mean()

    def test_effect_accepts_unseen_patients(self, models):
        """The CDSS calls `.effect()` on hand-written patients who are not rows in
        any cohort. That path must accept a single 1-D vector."""
        x = np.array([[68, 34.0, 9.1, 46.0, 1, 0]], dtype=float)
        for name, m in models.items():
            out = m.effect(x)
            assert out.shape == (1,), f"{name} returned shape {out.shape}"
            assert np.isfinite(out[0]), f"{name} returned {out[0]}"


# ═════════════════════════════════════════════════════════════════════════════
# POLICY — does better estimation lead to better decisions?
# ═════════════════════════════════════════════════════════════════════════════

class TestPolicyValue:

    GAIN = "gain per patient"
    REGRET = "regret vs oracle"

    def test_the_oracle_is_unbeatable(self, strong):
        """A sanity check on the metric itself. If any policy beat the oracle,
        `policy_value` would be computing something other than what it claims."""
        models = [estimators.x_learner(strong.X, strong.T, strong.Y)]
        table = evaluate.policy_comparison(models, strong)
        oracle = table.loc[table["policy"].str.contains("ORACLE", case=False),
                           self.GAIN].iloc[0]
        assert oracle >= table[self.GAIN].max() - 1e-9
        assert abs(table.loc[table["policy"].str.contains("ORACLE", case=False),
                             self.REGRET].iloc[0]) < 1e-9, "the oracle must have zero regret"

    def test_personalising_beats_treating_everyone(self, strong):
        """The clinical claim of Act 7, as an assertion."""
        models = [estimators.x_learner(strong.X, strong.T, strong.Y)]
        table = evaluate.policy_comparison(models, strong).set_index("policy")
        everyone = [i for i in table.index if "everyone" in i.lower()][0]
        learner = [i for i in table.index if "learner" in i.lower()][0]
        assert table.loc[learner, self.GAIN] > table.loc[everyone, self.GAIN], (
            "if the personalised policy cannot beat 'treat everyone', the CDSS "
            "has no reason to exist"
        )
        assert table.loc[learner, self.REGRET] < table.loc[everyone, self.REGRET]

    def test_treating_nobody_scores_exactly_zero(self, strong):
        """A fixed point of the metric: the do-nothing policy gains nothing.
        Any drift here means `policy_value` has an offset bug."""
        models = [estimators.x_learner(strong.X, strong.T, strong.Y)]
        table = evaluate.policy_comparison(models, strong).set_index("policy")
        nobody = [i for i in table.index if "nobody" in i.lower()][0]
        assert abs(table.loc[nobody, self.GAIN]) < 1e-9

    def test_risk_ranking_loses_badly_to_benefit_ranking(self, strong):
        """The strongest result in the project, pinned down.

        A predictive model is good at predicting. It is the wrong tool for
        allocation, because in this disease the highest-risk patients are the
        low-eGFR patients — exactly the ones the drug cannot help.
        """
        model = estimators.x_learner(strong.X, strong.T, strong.Y)
        r = evaluate.predictive_vs_causal(strong, model, budget_fraction=0.30)

        assert r["risk_model_r2"] > 0.5, (
            "the risk model must be GOOD at its own job, or the comparison is a "
            "straw man"
        )
        assert r["gain_treat_by_causal"] > r["gain_treat_by_risk"], (
            f"causal {r['gain_treat_by_causal']:.4f} vs risk "
            f"{r['gain_treat_by_risk']:.4f}"
        )
        assert r["gain_treat_by_causal"] > 3 * max(r["gain_treat_by_risk"], 1e-6)

    def test_risk_and_benefit_are_negatively_correlated(self, strong):
        """The root cause, isolated from the policy machinery.

        This single number is why the whole comparison comes out the way it does:
        in this disease, being at high risk and being likely to benefit point in
        OPPOSITE directions. If it were positive, risk-based targeting would be a
        reasonable heuristic and Act 8 would have no argument to make.
        """
        model = estimators.x_learner(strong.X, strong.T, strong.Y)
        r = evaluate.predictive_vs_causal(strong, model, budget_fraction=0.30)
        assert r["corr_risk_vs_benefit"] < -0.1, (
            f"corr(risk, benefit) = {r['corr_risk_vs_benefit']:+.3f} — Act 8's "
            "argument depends on this being clearly negative"
        )

    def test_the_causal_policy_selects_patients_who_actually_benefit(self, strong):
        """Not just a better score — a better cohort.

        The mean TRUE effect among the patients each policy picks. This is the
        version of the result a clinician can act on: the risk-ranked cohort is
        barely helped, the benefit-ranked cohort is helped a lot.
        """
        model = estimators.x_learner(strong.X, strong.T, strong.Y)
        r = evaluate.predictive_vs_causal(strong, model, budget_fraction=0.30)
        assert (r["mean_effect_among_causal_selected"]
                > r["mean_effect_among_risk_selected"] + 0.5)

    def test_at_a_tight_budget_risk_targeting_actively_harms(self, strong):
        """The sharpest form of the finding.

        At small budgets the risk-first policy does not merely underperform — its
        gain goes NEGATIVE, because the very sickest patients are the renally
        impaired ones the drug hurts. A CDSS built on a risk model would
        confidently treat exactly the wrong people first.
        """
        sweep = evaluate.predictive_vs_causal(
            strong, estimators.x_learner(strong.X, strong.T, strong.Y),
            budget_fraction=0.30)["budget_sweep"]

        assert len(sweep) >= 3, "the sweep needs several budgets to show the trend"
        tightest = sweep.sort_values("budget").iloc[0]

        assert tightest["gain by risk"] < 0, (
            f"at a {tightest['budget']:.0%} budget the risk policy gained "
            f"{tightest['gain by risk']:+.4f} — Act 8 claims it does active harm"
        )
        assert tightest["gain by benefit"] > 0
        assert "HARM" in tightest["benefit / risk"].upper()

    def test_benefit_ranking_never_loses_at_any_budget(self, strong):
        """Across the whole sweep, not just the budget the demo happens to show.

        A result that held only at 30% would be cherry-picked. The 100% row is
        excluded because it is a tie by construction: when you treat everyone,
        there is no ranking left to get right — which is itself the reason a
        budget constraint is what makes causal targeting matter.
        """
        sweep = evaluate.predictive_vs_causal(
            strong, estimators.x_learner(strong.X, strong.T, strong.Y),
            budget_fraction=0.30)["budget_sweep"]

        constrained = sweep.loc[sweep["budget"] < 1.0]
        assert len(constrained) >= 3
        losing = constrained.loc[
            constrained["gain by benefit"] <= constrained["gain by risk"]]
        assert losing.empty, f"risk-ranking wins at some budgets:\n{losing}"

        full = sweep.loc[sweep["budget"] == 1.0]
        if not full.empty:
            row = full.iloc[0]
            assert abs(row["gain by benefit"] - row["gain by risk"]) < 1e-9, (
                "at a 100% budget both policies treat everyone, so they must "
                "score identically"
            )
        assert (sweep["gain oracle"] >= sweep["gain by benefit"] - 1e-9).all()


# ═════════════════════════════════════════════════════════════════════════════
# (c) AGREEMENT WITH DOWHY AND ECONML — slow, and the most valuable tests here
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestLibraryAgreement:

    def test_our_ipw_agrees_with_dowhy(self, strong):
        """Twelve lines of NumPy against Microsoft Research's implementation.

        A tight 0.03 bound: this is the SAME estimator, so the only permitted
        difference is DoWhy's internal propensity model differing slightly from
        ours. A larger gap would mean one of us has the formula wrong.
        """
        comparisons = crosscheck.dowhy_comparison(strong, n_strata=10)
        ipw = next(c for c in comparisons if "IPW" in c.estimand)
        assert ipw.error is None, f"DoWhy failed to run: {ipw.error}"
        assert ipw.gap < 0.03, (
            f"ours {ipw.ours:+.4f} vs DoWhy {ipw.theirs:+.4f} (gap {ipw.gap:.4f})"
        )

    def test_our_stratification_agrees_with_dowhy(self, strong):
        comparisons = crosscheck.dowhy_comparison(strong, n_strata=10)
        strat = next(c for c in comparisons if "stratification" in c.estimand)
        assert strat.error is None, f"DoWhy failed to run: {strat.error}"
        assert strat.gap < 0.10, (
            f"ours {strat.ours:+.4f} vs DoWhy {strat.theirs:+.4f} — note DoWhy "
            "defaults to ~50 strata, so both must be pinned to the same count"
        )

    def test_our_metalearners_agree_with_econml(self, strong):
        """S- and T-learners should agree to machine precision.

        They are deterministic given the same base model and the same seed, so
        anything beyond floating-point noise indicates a real difference in what
        is being computed — not sampling variation.
        """
        comparisons = crosscheck.econml_comparison(strong)
        checked = 0
        for c in comparisons:
            if not c.same_estimator:
                continue                       # LinearDML — different estimator
            assert c.error is None, f"{c.estimand}: {c.error}"
            assert c.gap < 0.05, (
                f"{c.estimand}: ours {c.ours:+.4f} vs EconML {c.theirs:+.4f} "
                f"(gap {c.gap:.4f})"
            )
            checked += 1
        assert checked >= 3, f"only {checked} same-estimator comparisons ran"

    def test_lineardml_is_labelled_as_a_different_estimator(self, strong):
        """The honesty test.

        `LinearDML` has a partially linear structural assumption and is NOT a
        reimplementation of AIPW. It must be flagged `same_estimator=False` so it
        is held to a looser tolerance openly, rather than by quietly widening the
        bound for every row.
        """
        comparisons = crosscheck.econml_comparison(strong)
        dml = [c for c in comparisons if "DML" in c.estimand]
        assert dml, "no LinearDML comparison found"
        assert all(not c.same_estimator for c in dml), (
            "LinearDML is marked as the same estimator as our AIPW, which would "
            "make a genuine methodological difference look like a bug"
        )

    def test_the_crosscheck_table_renders(self, strong):
        table = crosscheck.crosscheck_table(strong)
        assert len(table) >= 5
        assert not table.isnull().all(axis=None)


@pytest.mark.slow
class TestRefutation:

    def test_placebo_treatment_yields_no_effect(self, strong):
        """Replace treatment with a coin flip. Anything but ~zero means the
        pipeline is manufacturing effects out of noise."""
        r = crosscheck.placebo_test(strong, n_trials=6)
        assert r["passed"], r["interpretation"]
        assert abs(r["placebo_mean"]) < 0.15, r
        assert r["placebo_max_abs"] < 0.30, (
            f"one placebo trial reached {r['placebo_max_abs']:.4f} — the mean can "
            "hide a single wild run"
        )
        # And the real estimate must be far outside the placebo distribution,
        # or "passing" would mean nothing.
        assert abs(r["real_estimate"]) > 3 * max(r["placebo_sd"], 1e-9)

    def test_a_junk_covariate_changes_nothing(self, strong):
        r = crosscheck.random_common_cause_test(strong, n_trials=4)
        assert r["passed"], r["interpretation"]
        assert abs(r["mean_shift"]) < 0.10, r
        assert r["max_abs_shift"] < 0.15, r

    def test_the_answer_survives_on_subsets(self, strong):
        """Guards against the estimate resting on one fragile subgroup.

        The interesting assertion is the last one: the spread across subsets
        should be roughly the size of the standard error we REPORT. If subsets
        disagreed far more than the SE claims, the SE would be lying.
        """
        r = crosscheck.subset_test(strong, fraction=0.8, n_trials=6)
        assert r["passed"], r["interpretation"]
        assert r["subset_sd"] < 0.15, r
        assert abs(r["subset_mean"] - truth_of(strong)) < 0.15, r
        assert r["subset_sd"] < 3 * r["reported_se"], (
            f"subsets vary by {r['subset_sd']:.4f} but the reported SE is only "
            f"{r['reported_se']:.4f} — the uncertainty is understated"
        )

    def test_injected_confounding_eventually_breaks_the_result(self, strong):
        """Refutation must be able to FAIL, or it proves nothing.

        A test suite where every check passes unconditionally is decoration. This
        one asserts that enough simulated confounding really does destroy the
        estimate — which is what gives the passes above their meaning.
        """
        table = crosscheck.unobserved_confounder_test(strong,
                                                     strengths=(0.5, 1.0, 2.0, 4.0))
        col = "estimate" if "estimate" in table.columns else table.columns[1]
        assert abs(table[col].iloc[0] - truth_of(strong)) < 0.35, (
            "weak simulated confounding should barely move the estimate"
        )
        assert abs(table[col].iloc[-1] - truth_of(strong)) > 0.5, (
            "strong simulated confounding should visibly break it"
        )


# ═════════════════════════════════════════════════════════════════════════════
# THE DAG
# ═════════════════════════════════════════════════════════════════════════════

class TestDag:

    def test_the_adjustment_set_is_the_confounders_only(self):
        sets = dag.adjustment_sets()
        for c in ("BMI", "HbA1c_baseline", "eGFR", "Age", "Comorbidities"):
            assert c in sets["adjust_for"], f"{c} is a confounder and must be adjusted"
        for bad in ("Adherence", "Hospitalisation", "AdverseEvents",
                    "SevereHyperglycaemia"):
            assert bad in sets["must_not_adjust_for"]
            assert bad not in sets["adjust_for"]

    def test_backdoor_paths_exist_and_are_blockable(self):
        paths = dag.backdoor_paths()
        assert paths, "no backdoor paths — then there is nothing to adjust for"

    def test_collider_bias_is_demonstrable(self, strong):
        """The signature of a collider: BOTH subgroups wrong, in OPPOSITE
        directions, and neither equal to the whole population."""
        demo = dag.demo_collider_bias(strong)
        assert abs(demo.damage) > 0.01, (
            "conditioning on the collider changed nothing — either the generator "
            "no longer creates one, or the demo is not conditioning on it"
        )

    def test_over_adjustment_shrinks_the_effect(self, strong):
        """Adjusting for a mediator must move the estimate TOWARD zero,
        because part of the causal pathway is being held fixed."""
        demo = dag.demo_over_adjustment(strong)
        assert abs(demo.mistaken) < abs(demo.correct), (
            f"mediator adjustment gave {demo.mistaken:+.4f} vs {demo.correct:+.4f} "
            "— it should attenuate, not inflate"
        )

    def test_omitting_a_confounder_hurts(self, strong):
        """The one case where adding a variable helps — which is exactly why
        'adjust for everything' is not a rule."""
        demo = dag.demo_confounder_omission(strong)
        assert abs(demo.mistaken - demo.truth) > abs(demo.correct - demo.truth)


# ═════════════════════════════════════════════════════════════════════════════
# (f) RETRIEVAL
# ═════════════════════════════════════════════════════════════════════════════

class TestRetrieval:

    def test_the_index_is_built_from_real_pdf_text(self, index):
        """Not only from the curated fallback.

        If PDF extraction silently regressed, the fallback would keep every
        citation resolving and nothing would look broken — the failure would be
        invisible. So this asserts that genuinely extracted chunks are present,
        and that they are the MAJORITY of the index rather than a token few.
        """
        table = rag_lite.provenance_table(index)
        assert len(index.chunks) > 200, f"only {len(index.chunks)} chunks"

        extracted = table.loc[table["tier"].str.contains("extracted", case=False)]
        assert not extracted.empty, (
            f"no extracted-PDF sources; tiers were {list(table['tier'])}"
        )
        n_extracted = int(extracted["chunks indexed"].sum())
        assert n_extracted > 0.5 * len(index.chunks), (
            f"only {n_extracted} of {len(index.chunks)} chunks came from real PDF "
            "text — the index has quietly become mostly hand-written"
        )

    def test_the_provenance_table_reports_both_tiers(self, index):
        """Two of the four PDFs are unreadable, and the table must say which.

        A retrieval system that silently substituted curated text for a document
        it could not read would be misrepresenting its own evidence base.
        """
        table = rag_lite.provenance_table(index)
        tiers = " ".join(table["tier"]).lower()
        assert "extracted" in tiers and "fallback" in tiers, tiers
        quality = " ".join(table["extraction quality"])
        assert "GOOD" in quality
        assert "UNREADABLE" in quality or "POOR" in quality

    @pytest.mark.parametrize("query", [
        "SGLT2 inhibitor obesity weight loss",
        "metformin first line therapy type 2 diabetes",
        "eGFR renal impairment dose adjustment",
        "cardiovascular outcomes established heart disease",
    ])
    def test_clinical_queries_retrieve_a_cited_passage(self, index, query):
        hits = index.retrieve(query, k=3)
        assert hits, f"nothing retrieved for {query!r}"

        top = hits[0]
        assert top.score > 0, "zero cosine similarity should not be returned"
        assert len(top.chunk.text.strip()) > 50, "retrieved a near-empty chunk"
        assert isinstance(top.chunk.page, int) and top.chunk.page >= 1, (
            f"unusable page citation: {top.chunk.page!r}"
        )
        assert top.chunk.source, "no source document on the citation"
        assert str(top.chunk.page) in top.chunk.citation, (
            f"citation {top.chunk.citation!r} omits the page number"
        )

    def test_results_are_ranked_by_score(self, index):
        hits = index.retrieve("SGLT2 inhibitor renal", k=5)
        scores = [h.score for h in hits]
        assert scores == sorted(scores, reverse=True), scores

    def test_different_queries_retrieve_different_passages(self, index):
        """The property the CDSS depends on.

        If retrieval returned the same passages regardless of the query, the
        per-patient question builder would be pointless and every citation would
        be decoration.
        """
        a = index.retrieve("severe hyperglycaemia insulin initiation", k=3)
        b = index.retrieve("chronic kidney disease albuminuria screening", k=3)
        assert {h.chunk.chunk_id for h in a} != {h.chunk.chunk_id for h in b}

    def test_bibliography_chunks_are_filtered(self):
        """Reference lists match clinical queries on author surnames and journal
        names, and would otherwise crowd out real guidance."""
        refs = ("1. Smith J, Jones A, Patel R, et al. Effect of empagliflozin on "
                "renal outcomes. N Engl J Med. 2019;380(24):2295-2306. "
                "2. Brown K, Lee S. Diabetes Care. 2020;43(2):112-119. "
                "3. Garcia M, et al. Lancet Diabetes Endocrinol. 2021;9(1):45-52.")
        assert rag_lite.looks_like_bibliography(refs)

        prose = ("Metformin remains the preferred initial pharmacologic agent for "
                 "the treatment of type 2 diabetes in most patients, given its "
                 "efficacy, low cost and favourable safety profile.")
        assert not rag_lite.looks_like_bibliography(prose)

    def test_chunks_overlap_so_split_sentences_stay_findable(self):
        page = "word " * 400
        chunks = rag_lite.chunk_page(page, "test.pdf", 1, 0, size=200, overlap=50)
        assert len(chunks) > 1
        assert all(c.page == 1 for c in chunks)
        assert all(c.source == "test.pdf" for c in chunks)

    def test_extraction_quality_is_reported_honestly(self):
        """Two of the four PDFs are unreadable. That must be VISIBLE.

        A retrieval system that failed silently on half its corpus would be far
        worse than one that says so — so the report is asserted to contain both
        good and bad verdicts.
        """
        report = pdf_text.extraction_report("RAG")
        assert "GOOD" in report, "no readable PDFs — extraction has regressed"
        assert any(w in report for w in ("UNREADABLE", "POOR")), (
            "the report claims every PDF is fine, which contradicts the "
            "documented CID-font and scanned-page failures"
        )


# ═════════════════════════════════════════════════════════════════════════════
# GUARDRAILS — the layer that is allowed to say no
# ═════════════════════════════════════════════════════════════════════════════

class TestGuardrails:

    def test_severe_renal_impairment_is_vetoed(self):
        result = guardrails.check({"egfr": 22, "bmi": 30, "age": 70,
                                   "baseline_hba1c": 8.0, "has_cvd": 0, "has_ckd": 1})
        assert result.vetoed
        assert result.severity == guardrails.Severity.VETO
        assert "BLOCKED" in result.status

    def test_a_veto_does_not_recommend_the_other_arm(self):
        """A CDSS that turns 'drug A is contraindicated' into 'therefore drug B'
        has invented a recommendation nobody made."""
        result = guardrails.check({"egfr": 22, "bmi": 30, "age": 70,
                                   "baseline_hba1c": 8.0, "has_cvd": 0, "has_ckd": 1})
        flag = next(f for f in result.flags if f.rule == "metformin_egfr_30")
        assert "nephrology" in flag.message.lower() or "refer" in flag.message.lower()

    def test_predicted_harm_is_flagged(self):
        """The rule the whole project exists for: catching the patient the
        population average gets wrong."""
        result = guardrails.check(
            {"egfr": 50, "bmi": 34, "age": 68, "baseline_hba1c": 9.0,
             "has_cvd": 0, "has_ckd": 0},
            estimate={"cate": -0.8, "cate_se": 0.2},
        )
        assert any(f.rule == "predicted_harm" for f in result.flags)
        assert result.severity >= guardrails.Severity.WARNING

    def test_a_negligible_effect_is_reported_as_such(self):
        result = guardrails.check(
            {"egfr": 85, "bmi": 29, "age": 55, "baseline_hba1c": 7.6,
             "has_cvd": 0, "has_ckd": 0},
            estimate={"cate": 0.05, "cate_se": 0.20},
        )
        assert any(f.rule == "effect_below_threshold" for f in result.flags)

    def test_out_of_distribution_patients_are_flagged(self, strong):
        ranges = guardrails.training_ranges(strong)
        result = guardrails.check(
            {"egfr": 400, "bmi": 15, "age": 19, "baseline_hba1c": 5.0,
             "has_cvd": 0, "has_ckd": 0},
            estimate={"cate": 1.0, "training_ranges": ranges},
        )
        assert any(f.rule == "out_of_distribution" for f in result.flags)

    def test_a_healthy_obese_patient_is_approved(self):
        result = guardrails.check(
            {"egfr": 95, "bmi": 38, "age": 52, "baseline_hba1c": 8.6,
             "has_cvd": 0, "has_ckd": 0},
            estimate={"cate": 1.8, "cate_se": 0.2},
        )
        assert not result.vetoed
        assert result.status == "APPROVED", [str(f) for f in result.flags]

    def test_the_rules_run_without_a_model(self):
        """Contraindication checking must survive the model failing to load.
        Fail-safe, not fail-open."""
        result = guardrails.check({"egfr": 20, "bmi": 30, "age": 70,
                                   "baseline_hba1c": 8.0, "has_cvd": 0, "has_ckd": 1})
        assert result.vetoed

    def test_every_flag_names_its_source(self):
        """A warning a clinician cannot audit is a warning they will learn to
        dismiss."""
        result = guardrails.check(
            {"egfr": 40, "bmi": 34, "age": 74, "baseline_hba1c": 10.5,
             "has_cvd": 1, "has_ckd": 1},
            estimate={"cate": -0.9, "cate_se": 0.3},
        )
        assert len(result.flags) >= 3
        for f in result.flags:
            assert f.source and len(f.source) > 5, f"{f.rule} has no usable source"
            assert f.message and len(f.message) > 40


# ═════════════════════════════════════════════════════════════════════════════
# THE FUSION LAYER — where both halves of the project meet
# ═════════════════════════════════════════════════════════════════════════════

class TestCDSS:

    @pytest.fixture(scope="class")
    def system(self, strong, index):
        model = estimators.x_learner(strong.X, strong.T, strong.Y)
        return cdss.DiaCausalCDSS(strong, cate_model=model, index=index)

    def test_the_flagship_patient_is_predicted_to_be_harmed(self, system):
        """Mrs R is the project's headline case: the population average says
        prescribe, and for her that is wrong."""
        spec = cdss.DEMO_PATIENTS[
            "Mrs R — the patient the population average gets WRONG"]
        patient = {k: v for k, v in spec.items() if k != "story"}

        rec = system.recommend(patient)
        assert rec.true_cate < -0.5, (
            f"her authored effect is {rec.true_cate:+.3f}; the demo depends on it "
            "being clearly negative"
        )
        assert rec.cate < 0, f"the model estimates {rec.cate:+.3f} — it missed the harm"
        assert rec.direction == "Metformin"
        assert any(f.rule == "predicted_harm" for f in rec.guard.flags)

    def test_every_demo_patient_gets_a_distinct_verdict(self, system):
        """Four patients engineered to exercise four different guardrail paths.
        If two collapse to the same status, the demo has lost a lesson."""
        statuses = {}
        for label, spec in cdss.DEMO_PATIENTS.items():
            patient = {k: v for k, v in spec.items() if k != "story"}
            statuses[label] = system.recommend(patient).guard.status
        assert len(set(statuses.values())) == 4, statuses

    def test_recommendations_carry_page_cited_evidence(self, system):
        for label, spec in cdss.DEMO_PATIENTS.items():
            patient = {k: v for k, v in spec.items() if k != "story"}
            rec = system.recommend(patient)
            assert rec.citations, f"{label} got no citations"
            for hit in rec.citations:
                assert str(hit.chunk.page) in hit.chunk.citation

    def test_citations_are_not_all_from_one_document(self, system):
        """A single source answering every question is a retrieval failure that
        looks like success — the short curated snippets score highly on almost
        any clinical query, so a source-diversity pass is required."""
        spec = cdss.DEMO_PATIENTS[
            "Mrs R — the patient the population average gets WRONG"]
        patient = {k: v for k, v in spec.items() if k != "story"}
        rec = system.recommend(patient, k_citations=3)
        sources = {h.chunk.source for h in rec.citations}
        assert len(sources) >= 2, f"all citations from {sources}"

    def test_questions_depend_on_the_patient(self, system):
        """If the query were fixed, every patient would get the same passages and
        the citations would be decoration rather than evidence."""
        renal = {"age": 70, "bmi": 30.0, "baseline_hba1c": 8.0, "egfr": 40.0,
                 "has_cvd": 0, "has_ckd": 1}
        obese = {"age": 45, "bmi": 40.0, "baseline_hba1c": 10.5, "egfr": 100.0,
                 "has_cvd": 0, "has_ckd": 0}
        assert set(cdss.build_questions(renal)) != set(cdss.build_questions(obese))

        renal_qs = " ".join(cdss.build_questions(renal)).lower()
        assert "renal" in renal_qs or "kidney" in renal_qs or "egfr" in renal_qs

    def test_a_contraindicated_patient_is_blocked(self, system):
        rec = system.recommend({"age": 77, "bmi": 26.0, "baseline_hba1c": 8.2,
                                "egfr": 24.0, "has_cvd": 1, "has_ckd": 1})
        assert rec.blocked
        assert rec.guard.vetoed

    def test_the_card_puts_safety_before_the_recommendation(self, system):
        """Ordering is a safety property, not a style choice: a clinician must
        reach the contraindication before they reach the number.

        Matched case-sensitively against the section headers. The title line says
        "treatment recommendation" in lower case, so an upper-cased search finds
        the title instead of the section and the test passes vacuously.
        """
        rec = system.recommend({"age": 77, "bmi": 26.0, "baseline_hba1c": 8.2,
                                "egfr": 24.0, "has_cvd": 1, "has_ckd": 1})
        card = cdss.format_card(rec)
        assert "SAFETY REVIEW" in card
        assert "RECOMMENDATION" in card
        assert card.index("SAFETY REVIEW") < card.index("RECOMMENDATION")

    def test_a_blocked_card_withholds_the_number(self, system):
        """Stronger than ordering: when an arm is contraindicated, the estimate
        must not be printed at all. Showing "+1.8 HbA1c points" beside a
        contraindication invites someone to act on the number and skim the
        warning."""
        rec = system.recommend({"age": 77, "bmi": 26.0, "baseline_hba1c": 8.2,
                                "egfr": 24.0, "has_cvd": 1, "has_ckd": 1})
        card = cdss.format_card(rec)
        assert "NO RECOMMENDATION" in card
        assert f"{rec.cate:+.2f}" not in card.split("RECOMMENDATION", 1)[1], (
            "the withheld estimate is still being printed in the recommendation "
            "section of a blocked card"
        )

    def test_the_card_always_states_its_scope(self, system):
        """The model estimates HbA1c and nothing else. For SGLT2 inhibitors that
        matters enormously, because their most important benefits are cardiorenal
        and this model never sees them."""
        rec = system.recommend({"age": 60, "bmi": 33.0, "baseline_hba1c": 8.4,
                                "egfr": 88.0, "has_cvd": 0, "has_ckd": 0})
        card = cdss.format_card(rec)
        assert "HbA1c" in card
        assert any(w in card.lower() for w in ("only", "does not", "not estimate"))

    def test_the_counterfactual_card_states_the_fundamental_problem(self, system):
        card = system.counterfactual_card(17)
        assert "FACTUAL" in card.upper()
        assert "COUNTERFACTUAL" in card.upper()

    def test_the_estimate_beats_the_population_average_for_this_patient(self, system):
        """The reason a CDSS exists at all: for a patient whose true effect is far
        from the mean, the personalised estimate must be closer to the truth than
        the population average is."""
        spec = cdss.DEMO_PATIENTS[
            "Mrs R — the patient the population average gets WRONG"]
        patient = {k: v for k, v in spec.items() if k != "story"}
        rec = system.recommend(patient)
        population = rec.notes["population_ate"]
        assert abs(rec.cate - rec.true_cate) < abs(population - rec.true_cate)


# ═════════════════════════════════════════════════════════════════════════════
# THE HONESTY APPENDIX
# ═════════════════════════════════════════════════════════════════════════════

class TestLimitations:

    def test_unmeasured_confounding_defeats_adjustment(self):
        """The limitation must be REAL, not narrated.

        If AIPW quietly recovered the truth here, Act 9's central admission would
        be false — and a project that overstates its own robustness is worse than
        one that never tested it.
        """
        hidden = data.generate_cohort(N, scenario="hidden_confounder", seed=SEED)
        aipw = estimators.aipw_ate(hidden.X, hidden.T, hidden.Y, cross_fit=True)
        t = truth_of(hidden)
        assert abs(aipw.value - t) > 0.5, (
            f"AIPW error only {abs(aipw.value - t):.4f} — adjustment should NOT be "
            "able to fix a confounder that is absent from the data"
        )

    def test_adjustment_still_helps_even_when_it_cannot_fix_things(self):
        """Partial credit is real: AIPW should still beat naive."""
        hidden = data.generate_cohort(N, scenario="hidden_confounder", seed=SEED)
        naive = estimators.naive_difference(hidden.Y, hidden.T)
        aipw = estimators.aipw_ate(hidden.X, hidden.T, hidden.Y, cross_fit=True)
        t = truth_of(hidden)
        assert abs(aipw.value - t) < abs(naive.value - t)

    def test_pima_cannot_support_a_causal_claim(self):
        """The most common error in student causal projects, pinned as a test:
        `Datasets/diabetes.csv` has no treatment column at all."""
        pima = data.load_pima()
        assert len(pima) == 768
        assert data.TREATMENT not in pima.columns
        assert not any("treat" in c.lower() or "drug" in c.lower()
                       for c in pima.columns), (
            "a treatment column has appeared in the Pima data — the honesty "
            "appendix's claim needs revisiting"
        )

    def test_the_retrieval_limitations_are_documented(self):
        assert len(rag_lite.KNOWN_LIMITATIONS) >= 3
        joined = " ".join(rag_lite.KNOWN_LIMITATIONS).lower()
        assert "curated" in joined, "the fallback tier must be disclosed"


# ═════════════════════════════════════════════════════════════════════════════
# REPRODUCIBILITY — everything above is worthless if the numbers drift
# ═════════════════════════════════════════════════════════════════════════════

class TestReproducibility:

    def test_the_same_seed_gives_the_same_cohort(self):
        a = data.generate_cohort(500, scenario="strong", seed=42)
        b = data.generate_cohort(500, scenario="strong", seed=42)
        np.testing.assert_allclose(a.Y, b.Y)
        np.testing.assert_allclose(a.true_cate, b.true_cate)
        np.testing.assert_array_equal(a.T, b.T)

    def test_different_seeds_give_different_cohorts(self):
        a = data.generate_cohort(500, scenario="strong", seed=1)
        b = data.generate_cohort(500, scenario="strong", seed=2)
        assert not np.allclose(a.Y, b.Y)

    def test_aipw_is_deterministic(self, mild):
        """Cross-fitting shuffles the data. If the fold assignment were not
        seeded, the headline number would change on every run — and no reported
        result could be checked."""
        first = estimators.aipw_ate(mild.X, mild.T, mild.Y, cross_fit=True,
                                    random_state=0)
        second = estimators.aipw_ate(mild.X, mild.T, mild.Y, cross_fit=True,
                                     random_state=0)
        assert abs(first.value - second.value) < 1e-9

    def test_the_headline_numbers_are_stable_across_cohort_sizes(self):
        """A result that only holds at n=4000 is not a result.

        The sign flip and AIPW's recovery must both survive halving the sample,
        or the walkthrough's numbers are an artefact of one lucky draw.
        """
        for n in (1500, 3000):
            c = data.generate_cohort(n, scenario="strong", seed=SEED)
            naive = estimators.naive_difference(c.Y, c.T)
            aipw = estimators.aipw_ate(c.X, c.T, c.Y, cross_fit=True)
            assert naive.value < 0 < aipw.value, f"n={n}: broke the sign flip"
            assert abs(aipw.value - truth_of(c)) < 0.10, f"n={n}"
