"""diacausal/xai/truth.py: the generator's true effect modifiers, derived from params.yaml and nothing else."""

import copy

import numpy as np
import pytest

from diacausal.causal_inference.cohort import generate_cohort, true_expected_outcomes
from diacausal.causal_inference.dag import load_dag
from diacausal.config import ARMS, CONTRASTS, Params
from diacausal.xai import truth


def edited(params, path: str, value):
    """A copy of params with one entry changed (the real file is never touched)."""
    raw = copy.deepcopy(params.raw)
    node = raw
    for part in path.split("."):
        node = node[part]
    node["value"] = value
    return Params(raw=raw, version=params.version, fingerprint="edited")


def test_modifiers_come_from_params_and_match_the_xai_plan(params):
    """docs/XAI_PLAN.md section 2.1, derived by subtraction from the generator's effects."""
    assert {c: set(m) for c, m in truth.modifiers(params).items()} == {
        "SGLT2i-DPP4i": {"hba1c", "egfr"}, "SU-DPP4i": {"hba1c", "duration_years"}, "SGLT2i-SU": {"hba1c", "egfr", "duration_years"}}


def test_slopes_are_the_differences_of_the_arms_parameters_per_original_unit(params):
    s = truth.true_slopes(params)
    g = lambda arm, key: params.get(f"generator.outcome.effects.{arm}.{key}")  # noqa: E731
    assert s["SGLT2i-DPP4i"]["hba1c"] == pytest.approx(g("SGLT2i", "per_hba1c_pct") - g("DPP4i", "per_hba1c_pct"))
    assert s["SGLT2i-DPP4i"]["egfr"] == pytest.approx((g("SGLT2i", "per_10_egfr") - g("DPP4i", "per_10_egfr")) / 10)  # per 10 -> per unit
    assert s["SU-DPP4i"]["duration_years"] == pytest.approx(g("SU", "per_duration_year") - g("DPP4i", "per_duration_year"))
    assert s["SGLT2i-SU"]["hba1c"] == pytest.approx(g("SGLT2i", "per_hba1c_pct") - g("SU", "per_hba1c_pct"))


def test_every_feature_of_the_adjustment_set_has_a_slope_and_the_others_are_exactly_zero(params):
    features = load_dag(params).adjustment_set
    for c, slopes in truth.true_slopes(params).items():
        assert list(slopes) == features
        assert all(slopes[f] == 0.0 for f in features if f not in ("hba1c", "egfr", "duration_years")), c


def test_common_terms_cancel_so_changing_them_changes_nothing(params):
    base = truth.true_slopes(params)
    for path, value in (("generator.outcome.drift", 5.0), ("generator.outcome.regression_to_mean", -3.0), ("generator.outcome.female", 2.0)):
        assert truth.true_slopes(edited(params, path, value)) == base, path


def test_changing_an_arms_effect_changes_the_truth(params):
    changed = truth.true_slopes(edited(params, "generator.outcome.effects.DPP4i.per_10_egfr", -0.2))
    assert changed["SGLT2i-DPP4i"]["egfr"] == pytest.approx((-0.06 + 0.2) / 10)
    assert "egfr" in truth.modifiers(edited(params, "generator.outcome.effects.DPP4i.per_10_egfr", -0.2))["SU-DPP4i"]
    assert "egfr" not in truth.modifiers(edited(params, "generator.outcome.effects.SGLT2i.per_10_egfr", 0.0))["SGLT2i-DPP4i"]


def test_the_linear_truth_reproduces_the_cohorts_true_effect(params):
    """truth.py describes cohort.true_expected_outcomes exactly: base difference + slopes x (feature - centre)."""
    df = generate_cohort(params, n=300, seed=3)
    mu = true_expected_outcomes(params, df)
    centre = params.group("generator.outcome.centre")
    for (a, b), c in zip(CONTRASTS, truth.COMPARISONS):
        base = params.get(f"generator.outcome.effects.{a}.base") - params.get(f"generator.outcome.effects.{b}.base")
        slopes = truth.true_slopes(params)[c]
        by_hand = base + sum(slopes[f] * (df[f].to_numpy(float) - centre[f]) for f in centre)
        assert np.allclose(by_hand, mu[:, ARMS.index(a)] - mu[:, ARMS.index(b)], atol=1e-12), c


def test_true_effect_is_the_difference_of_the_true_expected_outcomes(params):
    mu = np.array([[-1.0, -0.5, -0.8], [-0.2, -0.4, 0.1]])
    e = truth.true_effect(params, mu)
    assert np.allclose(e["SGLT2i-DPP4i"], [-0.5, 0.2]) and np.allclose(e["SU-DPP4i"], [-0.3, 0.5]) and np.allclose(e["SGLT2i-SU"], [-0.2, -0.3])


def test_true_importance_is_the_absolute_slope_times_the_spread(params):
    sd = {f: 2.0 for f in load_dag(params).adjustment_set}
    imp = truth.true_importance(params, sd)
    assert imp["SGLT2i-DPP4i"]["hba1c"] == pytest.approx(abs(truth.true_slopes(params)["SGLT2i-DPP4i"]["hba1c"]) * 2.0)
    assert imp["SGLT2i-DPP4i"]["age"] == 0.0
