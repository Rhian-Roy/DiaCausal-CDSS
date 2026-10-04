"""The metric formulas of docs/XAI_PLAN.md section 6, checked by hand on tiny examples."""

import numpy as np
import pytest

from diacausal.causal_inference.metrics import policy_regret
from diacausal.xai import baseline as b


def test_top_k_takes_the_largest_and_breaks_ties_by_position():
    assert b.top_k([0.1, 0.9, 0.5, 0.7], 2) == {1, 3}
    assert b.top_k([1.0, 1.0, 1.0, 0.5], 2) == {0, 1}  # a tie never depends on hash order
    assert b.top_k([3, 2, 1], 5) == {0, 1, 2}


def test_jaccard_is_the_overlap_over_the_union():
    assert b.jaccard({1, 2, 3}, {2, 3, 4}) == pytest.approx(2 / 4)
    assert b.jaccard({1, 2}, {1, 2}) == 1.0 and b.jaccard({1}, {2}) == 0.0 and b.jaccard(set(), set()) == 1.0


def test_spearman_is_the_rank_correlation_and_nan_for_a_constant():
    assert b.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert b.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert b.spearman([1, 2, 3, 4], [1, 3, 2, 4]) == pytest.approx(0.8)  # 1 - 6*2/(4*15)
    assert np.isnan(b.spearman([1, 1, 1], [1, 2, 3]))


def test_precision_at_k_uses_k_equal_to_the_number_of_true_modifiers():
    importance = {"hba1c": 0.9, "egfr": 0.2, "age": 0.5, "bmi": 0.1}
    assert b.precision_at_k(importance, ["hba1c", "egfr"]) == 0.5  # top 2 = hba1c, age: one of two is a modifier
    assert b.precision_at_k(importance, ["hba1c"]) == 1.0
    assert b.precision_at_k(importance, ["hba1c", "age"]) == 1.0
    assert np.isnan(b.precision_at_k(importance, []))


def test_mean_ci_is_the_t_interval():
    mean, lo, hi, n = b.mean_ci([1.0, 2.0, 3.0])
    assert (mean, n) == (2.0, 3) and lo == pytest.approx(2 - 4.302653 / np.sqrt(3), abs=1e-5) and hi == pytest.approx(2 + 4.302653 / np.sqrt(3), abs=1e-5)
    assert b.mean_ci([5.0]) == (5.0, float("nan"), float("nan"), 1) or np.isnan(b.mean_ci([5.0])[1])
    assert b.mean_ci([1.0, float("nan"), 3.0])[3] == 2  # a missing replicate is left out, not counted
    assert b.mean_ci([float("nan")])[3] == 0


def test_pick_is_the_lowest_prediction_among_the_allowed_options():
    levels = np.array([[-1.0, -0.5, -0.8], [-1.0, -0.5, -0.8], [0.0, 0.0, 0.0]])
    allowed = np.array([[True, True, True], [False, True, True], [False, False, False]])
    assert list(b.pick(levels, allowed)) == [0, 2, -1]  # SGLT2i; then SU (SGLT2i is excluded); no option: -1


def test_regret_and_best_pick_on_a_hand_checked_example():
    """Two patients. Truth: patient 1 best = option 1 (-1.2); patient 2 best allowed = option 2 (-0.6)."""
    true = np.array([[-1.0, -1.2, -0.5], [-0.9, -0.2, -0.6]])
    pred = np.array([[-1.1, -0.7, -0.4], [-0.3, -0.1, -0.5]])  # picks option 0, then option 2
    allowed = np.array([[True, True, True], [False, True, True]])
    regret, decided = policy_regret(pred, true, allowed)
    assert decided == 2 and regret == pytest.approx(((-1.0 - -1.2) + 0.0) / 2)  # patient 1 loses 0.2, patient 2 loses 0
    assert list(b.pick(pred, allowed)) == [0, 2] and list(b.pick(true, allowed)) == [1, 2]


def test_thin_patients_are_defined_by_the_smallest_TRUE_propensity(params, cohorts):
    """thin = min over the three options of the true propensity is below engine.overlap_min_propensity (0.05)."""
    _, test = cohorts
    from diacausal.guards.rules_loader import load_rules
    from diacausal.xai.baseline import evaluate_replicate

    expected = float((test[[f"e_true_{a}" for a in ("SGLT2i", "DPP4i", "SU")]].min(axis=1) < params.get("engine.overlap_min_propensity")).mean())
    m = evaluate_replicate(params, load_rules(), 7, 1500, 800, 0, with_lime=False)
    assert m["thin_share", "all"] == pytest.approx(expected) and 0 < expected < 0.5
    assert m["answered_when_thin", "all"] >= 0.98  # version A answers thin patients too (only the rules can leave nothing)


def test_version_a_never_abstains_and_the_exclusion_rate_is_the_rules_only(params, rules, cohorts):
    m = b.evaluate_replicate(params, rules, 7, 1500, 800, 0, with_lime=False)
    _, test = cohorts
    assert m["abstention_rate", "all"] == 0.0
    assert m["excluded_by_rules_rate", "all"] == pytest.approx(float(1 - b.rule_allowed(rules, test).mean()))
