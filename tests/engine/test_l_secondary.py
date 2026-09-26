"""FR7 secondary outcomes (weight change, hypoglycaemia risk) and the too-uncertain abstention."""

import numpy as np
import pytest
from conftest import OLDER_HYPO, TYPICAL

from diacausal_engine import ARMS
from diacausal_engine.cohort import generate_cohort, observed_view, true_secondary_population
from diacausal_engine.estimators import aipw, by_target
from diacausal_engine.fitting import fit_all
from diacausal_engine.recommend import OutputCheckError, check_output
from diacausal_engine.schemas import PatientIn


def test_secondary_outcomes_never_change_the_primary_cohort(params):
    """Secondary draws use their own random stream, so every primary number stays reproducible."""
    df = generate_cohort(params, n=500, seed=3)
    primary = [c for c in df.columns if c.startswith(("y", "mu_true_", "e_true_")) or c == "treatment"]
    assert df["y"].notna().all() and set(df["treatment"]) <= set(ARMS)
    again = generate_cohort(params, n=500, seed=3)
    assert df[primary].equals(again[primary])
    assert {"weight_change_6m", "hypo_6m"} <= set(observed_view(df).columns)
    assert not any(c.startswith(("w_true_", "wmu_true_", "h_true_", "hp_true_")) for c in observed_view(df).columns)


def test_secondary_parameters_have_sources_and_statuses(params):
    for group in ("generator.secondary.weight", "generator.secondary.hypo"):
        assert params.group(group)  # the loader refuses any number without a source and status


def test_truth_matches_the_direction_in_the_literature(params):
    t = true_secondary_population(params)
    assert t["weight:SGLT2i"] < t["weight:DPP4i"] < t["weight:SU"]  # SGLT2i loses, SU gains weight
    assert t["hypo:SU"] > 3 * t["hypo:DPP4i"]  # sulfonylureas carry the hypoglycaemia risk
    assert abs(t["hypo:SGLT2i"] - t["hypo:DPP4i"]) < 1e-9


def test_aipw_recovers_the_secondary_truth(params, cohort):
    f = fit_all(params, cohort, seed=11)
    t = true_secondary_population(params)
    z = params.get("engine.ci_z")
    w, h = by_target(aipw(f.phi_weight, z)), by_target(aipw(f.phi_hypo, z))
    assert abs(w["SGLT2i-SU"].value - t["weight:SGLT2i-SU"]) < 0.4
    assert w["SGLT2i-SU"].low < t["weight:SGLT2i-SU"] < w["SGLT2i-SU"].high
    assert abs(h["SU-DPP4i"].value - t["hypo:SU-DPP4i"]) < 0.06
    assert h["SU-DPP4i"].value > 0 and h["SU-DPP4i"].low > 0  # clearly more low sugars on SU


def test_estimated_options_carry_both_secondary_outcomes_with_intervals(engine, audit_file):
    r = engine.recommend(PatientIn(**TYPICAL))
    by = {o.arm: o for o in r.options}
    for o in r.options:
        assert o.status == "estimate" and o.secondary is not None
        for iv in (o.secondary.weight_change_kg, o.secondary.hypo_risk_pct):
            assert iv.ci_low <= iv.value <= iv.ci_high and iv.level == 0.95
        assert 0 <= o.secondary.hypo_risk_pct.ci_low and o.secondary.hypo_risk_pct.ci_high <= 100
    assert by["SGLT2i"].secondary.weight_change_kg.value < by["SU"].secondary.weight_change_kg.value
    assert by["SU"].secondary.hypo_risk_pct.value > by["DPP4i"].secondary.hypo_risk_pct.value


def test_excluded_or_uncertain_options_never_get_secondary_numbers(engine, audit_file):
    r = engine.recommend(PatientIn(**OLDER_HYPO))
    for o in r.options:
        if o.status != "estimate":
            assert o.secondary is None and o.effect is None


def test_output_check_refuses_secondary_numbers_on_a_non_estimate(engine, audit_file):
    r = engine.recommend(PatientIn(**TYPICAL))
    sec = r.options[0].secondary
    bad = r.model_copy(deep=True)
    bad.options[1].status = "insufficient_evidence"
    bad.options[1].effect = None
    bad.options[1].insufficient_reason = "test"
    bad.options[1].secondary = sec
    with pytest.raises(OutputCheckError):
        check_output(bad)


def test_too_wide_interval_means_insufficient_evidence_not_a_number(engine, audit_file, monkeypatch):
    monkeypatch.setattr(engine, "max_width", 0.01)
    r = engine.recommend(PatientIn(**TYPICAL))
    for o in r.options:
        assert o.status == "insufficient_evidence" and o.effect is None and o.secondary is None
        assert "Too uncertain" in o.insufficient_reason
    assert r.comparisons == []


def test_width_limit_is_team_set_in_params(params):
    assert params.get("engine.max_interval_width") == 1.5
    assert params.entry("engine.max_interval_width")["status"] == "TEAM-SET"
