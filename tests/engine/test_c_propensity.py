"""Step (c): cross-fitted multinomial propensity model and overlap check."""

import numpy as np
import pytest

from diacausal_engine import ARMS
from diacausal_engine.cohort import features, observed_view, treatment_index
from diacausal_engine.propensity import (
    clip,
    crossfit_propensity,
    fit_full,
    overlap_check,
    predict,
    support_check,
)


@pytest.fixture(scope="module")
def fitted(params, cohort):
    obs = observed_view(cohort)
    X, T = features(params, obs), treatment_index(obs)
    oof = crossfit_propensity(X, T, folds=5, seed=0)
    return X, T, oof, fit_full(X, T)


def test_three_probabilities_that_add_up_to_one(fitted):
    _, _, oof, _ = fitted
    assert oof.shape[1] == 3
    assert np.allclose(oof.sum(axis=1), 1.0)
    assert (oof > 0).all()


def test_scores_are_out_of_fold(fitted):
    """Cross-fitted scores differ from a model that has seen every patient."""
    X, _, oof, full = fitted
    assert not np.allclose(oof, predict(full, X))


def test_the_model_recovers_the_true_assignment_probabilities(fitted, cohort):
    """The generator's propensities are known, so we can check the fit directly."""
    _, _, oof, _ = fitted
    truth = cohort[[f"e_true_{a}" for a in ARMS]].to_numpy()
    assert np.abs(oof - truth).mean() < 0.03


def test_viva_example_first_option_has_insufficient_evidence():
    """Propensities 0.03, 0.55, 0.42 with threshold 0.05 -> the first gets 'insufficient evidence'."""
    assert overlap_check([0.03, 0.55, 0.42], 0.05) == {"SGLT2i": False, "DPP4i": True, "SU": True}


def test_threshold_comes_from_params(params):
    assert params.get("engine.overlap_min_propensity") == 0.05


def test_rare_patient_types_fall_below_the_threshold(params, fitted):
    """An older patient with past hypoglycaemia and heart disease almost never got a sulfonylurea."""
    _, _, _, full = fitted
    import pandas as pd

    from diacausal_engine.dag import load_dag

    cols = load_dag(params).adjustment_set
    row = {c: 0 for c in cols} | {"age": 80, "duration_years": 15, "hba1c": 8.0, "egfr": 38, "bmi": 24, "hypo_history": 1, "ascvd": 1}
    p = predict(full, pd.DataFrame([row])[cols].to_numpy(float))[0]
    ok = overlap_check(p, params.get("engine.overlap_min_propensity"))
    assert ok["SU"] is False


def test_clipping_keeps_weights_finite():
    p = clip(np.array([[0.0, 0.3, 0.7]]), 0.01)
    assert p.min() >= 0.0099 and np.isclose(p.sum(), 1.0)


def test_support_check_flags_patients_outside_the_cohort(params, cohort):
    base = cohort.iloc[0].to_dict()
    assert support_check(base, cohort, params) == []
    assert any("type 1" in r for r in support_check(base | {"t1d": 1}, cohort, params))
    assert any("egfr" in r for r in support_check(base | {"egfr": 15}, cohort, params))
