"""Step (f): metrics against the true effects, checked on tiny hand-worked examples."""

import numpy as np
import pytest

from diacausal_engine.cohort import features, observed_view, treatment_index
from diacausal_engine.dag import load_dag
from diacausal_engine.metrics import (
    abstention_rate,
    balance_table,
    bias,
    coverage,
    pehe,
    policy_regret,
    rmse,
    smd,
)
from diacausal_engine.propensity import clip, crossfit_propensity


def test_bias_and_rmse():
    assert bias([-0.3, -0.1], truth=-0.2) == pytest.approx(0.0)
    assert bias([-0.1, -0.1], truth=-0.2) == pytest.approx(0.1)
    assert rmse([-0.3, -0.1], -0.2) == pytest.approx(0.1)


def test_coverage():
    assert coverage([-1, -1, 0.5], [0, 0, 1], [-0.5, -0.5, -0.5]) == pytest.approx(2 / 3)


def test_pehe_is_patient_level_rmse():
    assert pehe([0.0, 0.0, 0.0, 0.0], [0.1, -0.1, 0.1, -0.1]) == pytest.approx(0.1)


def test_policy_regret_counts_only_allowed_options():
    true = np.array([[-1.0, -0.8, -0.5], [-0.2, -0.9, -0.4]])
    pred = np.array([[-0.9, -1.0, -0.1], [-0.2, -0.9, -0.4]])  # wrong for patient 1, right for 2
    allowed = np.ones((2, 3), bool)
    regret, n = policy_regret(pred, true, allowed)
    assert n == 2 and regret == pytest.approx((0.2 + 0.0) / 2)
    allowed[0, 1] = False  # the wrongly preferred option was excluded -> no regret
    assert policy_regret(pred, true, allowed)[0] == pytest.approx(0.0)


def test_patients_with_no_allowed_option_are_not_decided():
    regret, n = policy_regret(np.zeros((2, 3)), np.zeros((2, 3)), np.array([[0, 0, 0], [1, 0, 0]], bool))
    assert n == 1


def test_abstention_rate():
    assert abstention_rate(np.array([[1, 1, 0], [1, 0, 0]], bool)) == pytest.approx(0.5)


def test_smd_of_identical_groups_is_zero_and_of_shifted_groups_is_one():
    x = np.r_[np.arange(10.0), np.arange(10.0)]
    T = np.r_[np.zeros(10, int), np.ones(10, int)]
    assert smd(x, T, 0, 1) == pytest.approx(0.0)
    y = np.r_[np.arange(10.0), np.arange(10.0) + np.arange(10.0).std(ddof=1)]
    assert smd(y, T, 1, 0) == pytest.approx(1.0)


def test_weighting_improves_balance_on_the_cohort(params, cohort):
    obs = observed_view(cohort)
    X, T = features(params, obs), treatment_index(obs)
    e = clip(crossfit_propensity(X, T, 5, 0), params.get("engine.propensity_clip"))
    rows = balance_table(X, load_dag(params).adjustment_set, T, e)
    threshold = params.get("engine.smd_threshold")
    assert max(r["smd_before"] for r in rows) > threshold  # confounded before
    assert max(r["smd_after"] for r in rows) < threshold  # balanced after weighting
