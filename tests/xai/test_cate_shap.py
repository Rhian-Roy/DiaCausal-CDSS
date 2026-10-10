"""Version C (P25): exact SHAP on the causal engine's estimate (diacausal/xai/cate_shap.py, docs/XAI_PLAN.md sections 3 and 4)."""

import numpy as np
import pytest

from diacausal.causal_inference.recommend import get_engine
from diacausal.causal_inference.schemas import PatientIn
from diacausal.xai import cate_shap as cs
from diacausal.xai import truth

PRESET_2 = dict(age=60, sex="female", duration_years=8, hba1c=8.2, egfr=40, bmi=25.5, pancreatitis_history=True)


@pytest.fixture(scope="module")
def engine():
    return get_engine()  # the engine the API and the website export use (fitted once on the reference cohort)


def explain(engine, x, target):
    return cs.explain_effect(engine.fitted.dr, x, target, engine.z, engine.adjustment)


def patients(engine, n=60, seed=3):
    """Real rows of the reference cohort (so every value is plausible), plus the three presets."""
    rng = np.random.default_rng(seed)
    X = engine.fitted.X
    return [X[i] for i in rng.choice(len(X), size=n, replace=False)]


# ── exact ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_contributions_plus_base_equal_the_engines_estimate_within_1e_9(engine):
    for x in patients(engine):
        pred = engine.fitted.dr.predict(np.atleast_2d(x), engine.z)
        for target in cs.COMPARISONS:
            e = explain(engine, x, target)
            assert e.additivity_error < 1e-9 and abs(e.estimate - pred[target][0, 0]) < 1e-9


def test_the_plans_worked_example(engine):
    """docs/XAI_PLAN.md 3.2: the eGFR-40 woman, SGLT2i vs DPP-4i: base -0.208, estimate -0.024; eGFR +0.274 (+0.131 to +0.417) and
    HbA1c +0.031 (+0.008 to +0.055) are the clear drivers; past pancreatitis (-0.159) is NOT clear and NOT shown."""
    x = engine.feature_vector(PatientIn(**PRESET_2))
    e = explain(engine, x, "SGLT2i-DPP4i")
    assert (round(e.base, 3), round(e.estimate, 3)) == (-0.208, -0.024)
    shown = cs.drivers(e, 3)
    assert [(c.feature, round(c.phi, 3), round(c.ci_low, 3), round(c.ci_high, 3)) for c in shown] == [
        ("egfr", 0.274, 0.131, 0.417), ("hba1c", 0.031, 0.008, 0.055)]
    pancreatitis = next(c for c in e.contributions if c.feature == "pancreatitis_history")
    assert round(pancreatitis.phi, 3) == -0.159 and not pancreatitis.clear


def test_matches_the_formula_by_hand(engine):
    dr, x = engine.fitted.dr, patients(engine, n=1)[0]
    k = cs.TARGETS.index("SU-DPP4i")
    e = explain(engine, x, "SU-DPP4i")
    for j, c in enumerate(e.contributions):
        assert c.slope_per_unit == pytest.approx(dr.beta_[j + 1, k] / dr.scale_[j], abs=1e-15)
        assert c.phi == pytest.approx(c.slope_per_unit * (x[j] - dr.mean_[j]), abs=1e-12)
    assert e.base == dr.beta_[0, k]


def test_a_patient_at_the_cohort_mean_has_no_contribution_and_one_feature_moves_only_its_own(engine):
    dr = engine.fitted.dr
    at_mean = explain(engine, dr.mean_.copy(), "SGLT2i-DPP4i")
    assert all(c.phi == 0.0 for c in at_mean.contributions) and at_mean.estimate == pytest.approx(at_mean.base, abs=1e-15)
    assert cs.drivers(at_mean, 3) == []  # nothing about this patient differs from the average one
    j = engine.adjustment.index("egfr")
    moved = dr.mean_.copy()
    moved[j] -= 20.0
    e = explain(engine, moved, "SGLT2i-DPP4i")
    for i, c in enumerate(e.contributions):
        assert c.phi == (pytest.approx(c.slope_per_unit * -20.0, abs=1e-12) if i == j else 0.0)


def test_matches_shap_linearexplainer_with_the_full_cohort_as_background(engine):
    """Cross-check with the shap package itself. The full cohort must be the background (max_samples=len(X)): SHAP's default masker
    subsamples 100 rows and shifts the base value (docs/XAI_PLAN.md finding 7)."""
    shap = pytest.importorskip("shap")
    dr, X = engine.fitted.dr, engine.fitted.X
    rows = np.array(patients(engine, n=50, seed=9))
    masker = shap.maskers.Independent(X, max_samples=len(X))
    for target in cs.COMPARISONS:
        k = cs.TARGETS.index(target)
        coef = dr.beta_[1:, k] / dr.scale_
        intercept = dr.beta_[0, k] - float(coef @ dr.mean_)
        explained = shap.LinearExplainer((coef, intercept), masker)(rows)
        for i, x in enumerate(rows):
            e = explain(engine, x, target)
            assert np.allclose(explained.values[i], [c.phi for c in e.contributions], atol=1e-9, rtol=0)
            assert abs(float(np.ravel(explained.base_values)[i]) - e.base) < 1e-9


# ── the interval of a contribution (HC3, no bootstrap) ───────────────────────────────────────────────────────────
def test_the_interval_is_the_hc3_formula(engine):
    dr, x = engine.fitted.dr, patients(engine, n=1, seed=4)[0]
    for target in cs.COMPARISONS:
        k = cs.TARGETS.index(target)
        e = explain(engine, x, target)
        for j, c in enumerate(e.contributions):
            se = abs((x[j] - dr.mean_[j]) / dr.scale_[j]) * np.sqrt(dr.cov_[k][j + 1, j + 1])
            assert c.se == pytest.approx(se, abs=1e-15)
            assert (c.ci_low, c.ci_high) == (pytest.approx(c.phi - engine.z * se, abs=1e-15), pytest.approx(c.phi + engine.z * se, abs=1e-15))


def test_clear_means_the_interval_excludes_zero(engine):
    for x in patients(engine, n=20, seed=5):
        for target in cs.COMPARISONS:
            for c in explain(engine, x, target).contributions:
                if c.phi != 0.0:
                    assert c.clear == (c.ci_low > 0 or c.ci_high < 0), (target, c.feature)


# ── the card rule ────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_card_shows_up_to_max_drivers_clear_ones_largest_first_never_padded(engine):
    limit = cs.max_drivers(engine.params)
    assert limit == 3
    for x in patients(engine, n=40, seed=6):
        for target in cs.COMPARISONS:
            e = explain(engine, x, target)
            shown = cs.drivers(e, limit)
            assert len(shown) <= limit and all(c.clear and (c.ci_low > 0 or c.ci_high < 0) for c in shown)
            assert [abs(c.phi) for c in shown] == sorted((abs(c.phi) for c in shown), reverse=True)
            others = [c for c in e.contributions if c.clear and c.phi != 0.0 and c not in shown]
            assert len(shown) == limit or not others  # never fewer than possible


def test_no_clear_driver_means_an_empty_list(engine):
    e = explain(engine, engine.fitted.dr.mean_.copy(), "SU-DPP4i")
    assert cs.drivers(e, 3) == [] and cs.driver_records(e, 3) == []


def test_driver_records_are_driver_v1_rows_rounded_as_the_card_shows_them(engine):
    from diacausal.api.schemas import DriverV1

    e = explain(engine, engine.feature_vector(PatientIn(**PRESET_2)), "SGLT2i-DPP4i")
    rows = [DriverV1(**r) for r in cs.driver_records(e, 3)]
    assert [(r.feature, r.contribution, r.ci95) for r in rows] == [("egfr", 0.274, (0.131, 0.417)), ("hba1c", 0.031, (0.008, 0.055))]


def test_excluded_and_abstained_options_get_no_drivers(engine):
    p = PatientIn(**PRESET_2)  # SGLT2i is removed by rule R01
    r = engine.recommend(p, audit=False)
    out = cs.explain_option_drivers(engine, p, r)
    assert "SGLT2i" not in out and "DPP4i" not in out and set(out) <= {o.arm for o in r.options if o.status == "estimate"}
    older = PatientIn(age=80, sex="male", duration_years=15, hba1c=8.0, egfr=38, bmi=24.0, hypo_history=True, ascvd=True)
    r = engine.recommend(older, audit=False)
    assert set(cs.explain_option_drivers(engine, older, r)) <= {o.arm for o in r.options if o.status == "estimate"}
    outside = PatientIn(age=88, sex="male", duration_years=5, hba1c=8.4, egfr=88, bmi=27.0)
    assert cs.explain_option_drivers(engine, outside, engine.recommend(outside, audit=False)) == {}


def test_on_the_committed_model_the_clear_features_are_exactly_the_true_modifiers(engine):
    """A regression check on THIS synthetic cohort (whose truth is linear), not a claim about the real world (docs/XAI_PLAN.md 3.4)."""
    x = engine.fitted.X[0]
    modifiers = truth.modifiers(engine.params)
    for target in cs.COMPARISONS:
        assert {c.feature for c in explain(engine, x, target).contributions if c.clear} == set(modifiers[target]), target


def test_the_pipeline_module_never_loads_shap():
    import subprocess
    import sys

    r = subprocess.run([sys.executable, "-c", "import sys, diacausal.xai.cate_shap; assert 'shap' not in sys.modules"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
