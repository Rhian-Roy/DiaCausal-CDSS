"""Refutation tests and E-value sensitivity (viva question 16)."""

import csv

import numpy as np
import pytest

from diacausal_engine.cohort import features, observed_view, treatment_index
from diacausal_engine.estimators import Estimate
from diacausal_engine.refute import _evalue_from_rr, e_value, refute


@pytest.fixture(scope="module")
def rows(params, cohort):
    obs = observed_view(cohort)
    return refute(params, features(params, obs), treatment_index(obs), obs["y"].to_numpy(float), seed=3)


def test_three_refuters_for_each_of_the_three_contrasts(rows):
    assert len(rows) == 9
    assert {r.check for r in rows} == {"placebo treatment", "random common cause", "data subset"}


def test_placebo_treatment_makes_the_effect_vanish(rows):
    """Average over 20 shuffles is about 0, and at least 85% of placebo CIs contain 0."""
    for r in (r for r in rows if r.check == "placebo treatment"):
        assert r.passed and abs(r.new_estimate) < 0.05, r
        assert "of 20 placebo CIs contain 0" in r.criterion


def test_random_common_cause_and_subset_do_not_move_the_answer(rows):
    for r in (r for r in rows if r.check != "placebo treatment"):
        assert r.passed, r


def test_evalue_formula_matches_vanderweele_and_ding():
    assert _evalue_from_rr(2.0) == pytest.approx(2 + np.sqrt(2))
    assert _evalue_from_rr(0.5) == pytest.approx(2 + np.sqrt(2))  # protective effects: use 1/RR
    assert _evalue_from_rr(1.0) == pytest.approx(1.0)


def test_evalue_is_one_when_the_interval_crosses_zero(params):
    point, ci = e_value(Estimate("AIPW", "x", 0.05, 0.05, -0.05, 0.15), outcome_sd=0.8, params=params)
    assert ci == 1.0 and point > 1.0


def test_evalue_uses_the_interval_bound_nearest_zero(params):
    est = Estimate("AIPW", "x", -0.30, 0.05, -0.40, -0.20)
    point, ci = e_value(est, outcome_sd=0.8, params=params)
    near, _ = e_value(Estimate("AIPW", "x", -0.20, 0.05, -0.30, -0.10), outcome_sd=0.8, params=params)
    assert 1.0 < ci < point
    assert ci == pytest.approx(near)


def test_benchmark_writes_refutation_and_evalue_files(tmp_path):
    from diacausal_engine.benchmark import run

    run(reps=1, n=1000, n_test=300, out=tmp_path, n_boot=5)
    ref = list(csv.DictReader((tmp_path / "refutation.csv").open()))
    ev = list(csv.DictReader((tmp_path / "evalues.csv").open()))
    assert len(ref) == 9 and {r["passed"] for r in ref} <= {"yes", "NO"}
    assert len(ev) == 3 and all(float(r["e_value_ci"]) >= 1.0 for r in ev)
