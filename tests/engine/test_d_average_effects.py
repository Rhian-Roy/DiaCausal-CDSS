"""Step (d): naive, IPW, matching and AIPW average effects with 95% CIs."""

import numpy as np
import pytest

from diacausal_engine import CONTRASTS
from diacausal_engine.cohort import features, observed_view, treatment_index, true_population_effects
from diacausal_engine.estimators import (
    aipw,
    aipw_scores,
    by_target,
    crossfit_outcomes,
    ipw,
    ipw_mean,
    matching,
    naive,
)
from diacausal_engine.propensity import clip, crossfit_propensity

Z = 1.959964


def test_build_guide_worked_example_naive_is_three_times_too_big():
    """High HbA1c: 300 SGLT2i at -1.2, 100 SU at -1.0. Lower: 100 SGLT2i at -0.6, 300 SU at -0.5."""
    y_s = np.r_[np.full(300, -1.2), np.full(100, -0.6)]
    y_u = np.r_[np.full(100, -1.0), np.full(300, -0.5)]
    assert round(y_s.mean() - y_u.mean(), 3) == -0.425  # naive
    # re-weighting by 1 / P(drug | group) compares like with like
    Y = np.r_[y_s, y_u]
    got_s = np.r_[np.ones(400), np.zeros(400)]
    high = np.r_[np.ones(300), np.zeros(100), np.ones(100), np.zeros(300)].astype(bool)
    e_s = np.where(high, 0.75, 0.25)
    fair = ipw_mean(Y, got_s, e_s)[0] - ipw_mean(Y, 1 - got_s, 1 - e_s)[0]
    assert round(fair, 3) == -0.15


def test_viva_ipw_example_weights_1_25_and_5():
    """Two patients (-1.0 and -0.4, naive mean -0.70) with weights 1.25 and 5 -> -0.52."""
    Y = np.array([-1.0, -0.4])
    mean, _ = ipw_mean(Y, np.ones(2), np.array([0.8, 0.2]))
    assert round(Y.mean(), 2) == -0.70
    assert round(mean, 2) == -0.52


@pytest.fixture(scope="module")
def results(params, cohort):
    obs = observed_view(cohort)
    X, T, Y = features(params, obs), treatment_index(obs), obs["y"].to_numpy()
    e = clip(crossfit_propensity(X, T, 5, 0), params.get("engine.propensity_clip"))
    mu = crossfit_outcomes(X, T, Y, 5, params.group("engine.outcome_model"), 0)
    return {
        "naive": by_target(naive(Y, T, Z)),
        "IPW": by_target(ipw(Y, T, e, Z)),
        "matching": by_target(matching(Y, T, e, Z, n_boot=30, seed=0)),
        "AIPW": by_target(aipw(aipw_scores(Y, T, e, mu), Z)),
        "truth": true_population_effects(params),
    }


def test_every_estimate_has_a_95_percent_interval(results):
    for method in ("naive", "IPW", "matching", "AIPW"):
        for est in results[method].values():
            assert est.low < est.value < est.high
            assert np.isclose(est.high - est.value, Z * est.se)


def test_naive_comparison_is_biased(results):
    truth = results["truth"]["SGLT2i-DPP4i"]
    assert abs(results["naive"]["SGLT2i-DPP4i"].value - truth) > 0.1
    assert not results["naive"]["SGLT2i-DPP4i"].covers(truth)


@pytest.mark.parametrize("a,b", CONTRASTS)
def test_aipw_recovers_the_truth_and_its_interval_covers_it(results, a, b):
    truth = results["truth"][f"{a}-{b}"]
    est = results["AIPW"][f"{a}-{b}"]
    assert abs(est.value - truth) < 0.08
    assert est.covers(truth)


@pytest.mark.parametrize("a,b", CONTRASTS)
def test_ipw_and_matching_are_close_to_the_truth(results, a, b):
    truth = results["truth"][f"{a}-{b}"]
    assert abs(results["IPW"][f"{a}-{b}"].value - truth) < 0.10
    assert abs(results["matching"][f"{a}-{b}"].value - truth) < 0.15


def test_aipw_is_less_biased_than_naive(results):
    truth = results["truth"]
    err = lambda m: sum(abs(results[m][f"{a}-{b}"].value - truth[f"{a}-{b}"]) for a, b in CONTRASTS)  # noqa: E731
    assert err("AIPW") < err("naive") / 2
