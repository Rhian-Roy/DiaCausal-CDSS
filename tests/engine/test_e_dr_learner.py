"""Step (e): DR-learner patient-level effects with 95% intervals."""

import numpy as np
import pytest

from diacausal_engine import ARMS, CONTRASTS
from diacausal_engine.cohort import features, generate_cohort, observed_view, treatment_index
from diacausal_engine.estimators import (
    TARGETS,
    DRLearner,
    aipw_scores,
    crossfit_outcomes,
    levels_to_targets,
    s_learner,
    t_learner,
)
from diacausal_engine.propensity import clip, crossfit_propensity

Z = 1.959964


@pytest.fixture(scope="module")
def fitted(params, cohort):
    obs = observed_view(cohort)
    X, T, Y = features(params, obs), treatment_index(obs), obs["y"].to_numpy()
    e = clip(crossfit_propensity(X, T, 5, 0), params.get("engine.propensity_clip"))
    settings = params.group("engine.outcome_model")
    mu = crossfit_outcomes(X, T, Y, 5, settings, 0)
    dr = DRLearner().fit(X, aipw_scores(Y, T, e, mu))
    test = generate_cohort(params, n=1500, seed=99)  # fresh patients the models never saw
    Xt = features(params, test)
    truth = levels_to_targets(test[[f"mu_true_{a}" for a in ARMS]].to_numpy())
    return {
        "dr": dr.predict(Xt, Z),
        "t": levels_to_targets(t_learner(X, T, Y, Xt, settings, 0)),
        "s": levels_to_targets(s_learner(X, T, Y, Xt, settings, 0)),
        "truth": truth,
        "naive": {k: np.full(len(test), v) for k, v in _naive_levels(obs).items()},
    }


def _naive_levels(obs):
    means = obs.groupby("treatment")["y"].mean()
    out = {a: means[a] for a in ARMS}
    for a, b in CONTRASTS:
        out[f"{a}-{b}"] = means[a] - means[b]
    return out


def pehe(est, truth):
    return float(np.sqrt(np.mean((est - truth) ** 2)))


def test_every_patient_estimate_has_an_interval(fitted):
    for target in TARGETS:
        v = fitted["dr"][target]
        assert v.shape[1] == 3
        assert (v[:, 1] < v[:, 0]).all() and (v[:, 0] < v[:, 2]).all()


@pytest.mark.parametrize("a,b", CONTRASTS)
def test_dr_learner_recovers_patient_level_effects(fitted, a, b):
    k = f"{a}-{b}"
    err = pehe(fitted["dr"][k][:, 0], fitted["truth"][k])
    assert err < 0.12
    assert err < pehe(fitted["naive"][k], fitted["truth"][k])


@pytest.mark.parametrize("a,b", CONTRASTS)
def test_intervals_contain_the_true_effect_for_most_patients(fitted, a, b):
    k = f"{a}-{b}"
    v, truth = fitted["dr"][k], fitted["truth"][k]
    coverage = np.mean((v[:, 1] <= truth) & (truth <= v[:, 2]))
    assert coverage >= 0.85


def test_expected_change_under_each_option_is_close_to_the_truth(fitted):
    for a in ARMS:
        assert pehe(fitted["dr"][a][:, 0], fitted["truth"][a]) < 0.12


def test_simpler_learners_are_built_for_comparison(fitted):
    for learner in ("t", "s"):
        for a, b in CONTRASTS:
            assert pehe(fitted[learner][f"{a}-{b}"], fitted["truth"][f"{a}-{b}"]) < 0.5
