"""Step (a): the synthetic cohort, params.yaml and the DAG."""

import copy
import re
from pathlib import Path

import numpy as np
import pytest
import yaml

from diacausal_engine import ARMS
from diacausal_engine.cohort import (
    features,
    generate_cohort,
    load_dataset,
    observed_view,
    true_population_effects,
)
from diacausal_engine.config import PARAMS_PATH, STATUSES, ParamsError, load_params, validate
from diacausal_engine.dag import DagError, load_dag

ROOT = Path(__file__).resolve().parents[2]


def raw():
    return yaml.safe_load(PARAMS_PATH.read_text())


# ── params.yaml: every number has a source and a status ──────────────────────


def test_every_parameter_has_a_source_and_a_valid_status(params):
    entries = params.entries()
    assert len(entries) > 60
    for where, entry in entries:
        assert entry["source"].strip(), where
        assert entry["status"] in STATUSES, where


def test_a_parameter_without_a_source_is_refused():
    r = raw()
    del r["generator"]["outcome"]["noise_sd"]["source"]
    with pytest.raises(ParamsError, match="noise_sd: no source"):
        validate(r)


def test_a_parameter_with_an_invented_status_is_refused():
    r = raw()
    r["generator"]["outcome"]["effects"]["SU"]["base"]["status"] = "VERIFIED-BY-ME"
    with pytest.raises(ParamsError, match="status must be one of"):
        validate(r)


def test_a_bare_number_is_refused():
    r = raw()
    r["engine"]["overlap_min_propensity"] = 0.05
    with pytest.raises(ParamsError, match="bare value"):
        validate(r)


def test_the_loader_refuses_a_broken_file(tmp_path):
    r = raw()
    r["generator"]["n_patients"].pop("status")
    bad = tmp_path / "params.yaml"
    bad.write_text(yaml.safe_dump(r))
    with pytest.raises(ParamsError):
        load_params(bad)


def test_effect_sizes_are_not_labelled_as_cited(params):
    """Drug effects are ASSUMED-DIRECTIONAL: say so openly in the viva."""
    for arm in ARMS:
        assert params.entry(f"generator.outcome.effects.{arm}.base")["status"] == "ASSUMED-DIRECTIONAL"


def test_asian_indian_bmi_cutoffs_match_the_backend(params):
    """Overweight >= 23, obese >= 25 (Misra 2009) — same as backend/app/patient_ranges.py."""
    assert params.get("display.bmi_overweight_from") == 23.0
    assert params.get("display.bmi_obese_from") == 25.0
    text = (ROOT / "backend/app/patient_ranges.py").read_text()
    limits = [float(x) for x in re.findall(r"\((\d+\.\d+), \"", text)]
    assert limits == [18.5, 23.0, 25.0]
    assert params.get("display.bmi_underweight_below") == 18.5


def test_plausibility_ranges_match_the_backend(params):
    text = (ROOT / "backend/app/patient_ranges.py").read_text()
    backend = {
        "age": "age_years",
        "duration_years": "diabetes_duration_years",
        "hba1c": "hba1c_percent",
        "egfr": "egfr_ml_min_1_73m2",
        "bmi": "bmi_kg_m2",
    }
    for ours, theirs in backend.items():
        m = re.search(rf'"{theirs}": Range\(([\d.]+), ([\d.]+),', text)
        assert m, theirs
        assert params.get(f"display.input_ranges.{ours}") == [float(m.group(1)), float(m.group(2))]


def test_pima_is_not_used_anywhere_in_the_engine():
    for f in (ROOT / "diacausal_engine").glob("*.py"):
        assert "diabetes.csv" not in f.read_text(), f.name


# ── the DAG ──────────────────────────────────────────────────────────────────


def test_dag_adjustment_set_excludes_mediators(params):
    dag = load_dag(params)
    assert "weight_change_6m" in dag.mediators
    assert "weight_change_6m" not in dag.adjustment_set
    assert {"hba1c", "egfr", "duration_years"} <= set(dag.adjustment_set)


def test_generator_only_uses_arrows_drawn_in_the_dag(params):
    dag = load_dag(params)
    for arm in ("SGLT2i", "SU"):
        for var in params.group(f"generator.assignment.{arm}"):
            if var != "intercept":
                assert (var, "treatment") in dag.edges, var
    for var in ("hba1c", "egfr", "duration_years", "female"):
        assert (var, dag.outcome) in dag.edges, var


def test_a_role_that_contradicts_the_arrows_is_refused(params):
    bad = copy.deepcopy(params.raw)
    bad["dag"]["nodes"]["bmi"] = "confounder"  # bmi has no arrow to the outcome
    from diacausal_engine.config import Params

    with pytest.raises(DagError):
        load_dag(Params(raw=bad, version="x", fingerprint="x"))


# ── the cohort ───────────────────────────────────────────────────────────────


def test_same_seed_same_cohort(params):
    a = generate_cohort(params, n=500, seed=3)
    b = generate_cohort(params, n=500, seed=3)
    assert a.equals(b)
    assert not a.equals(generate_cohort(params, n=500, seed=4))


def test_all_three_options_appear(cohort):
    shares = cohort["treatment"].value_counts(normalize=True)
    assert set(shares.index) == set(ARMS)
    assert shares.min() > 0.15


def test_true_potential_outcomes_are_stored_and_match_the_observed_one(cohort):
    for arm in ARMS:
        assert f"y_true_{arm}" in cohort and f"mu_true_{arm}" in cohort
    picked = np.array([cohort.loc[i, f"y_true_{t}"] for i, t in cohort["treatment"].items()])
    assert np.allclose(picked, cohort["y"])


def test_observed_view_hides_the_truth(cohort):
    obs = observed_view(cohort)
    assert not [c for c in obs.columns if "true" in c]
    assert {"treatment", "y", "hba1c", "egfr"} <= set(obs.columns)


def test_units_and_inclusion(params, cohort):
    assert cohort["egfr"].min() >= params.get("generator.inclusion.egfr_min")
    assert cohort["hba1c"].min() >= params.get("generator.inclusion.hba1c_min")
    assert 5 < cohort["hba1c"].mean() < 12  # HbA1c in %, not mmol/mol
    assert 30 < cohort["egfr"].mean() < 120  # mL/min/1.73m2
    assert (cohort["t1d"] == 0).all()
    assert ((cohort["ckd"] == 1) == (cohort["egfr"] < 60)).all()


def test_confounding_by_indication_exists(params, cohort):
    """The naive comparison is clearly wrong, and the groups differ at baseline."""
    truth = true_population_effects(params)
    naive = cohort.groupby("treatment")["y"].mean()
    naive_diff = naive["SGLT2i"] - naive["DPP4i"]
    assert abs(naive_diff - truth["SGLT2i-DPP4i"]) > 0.1
    by_arm = cohort.groupby("treatment")["hba1c"].mean()
    pooled_sd = cohort["hba1c"].std()
    assert abs(by_arm["SGLT2i"] - by_arm["DPP4i"]) / pooled_sd > 0.1


def test_south_asian_calibration_of_sglt2i_vs_dpp4i(params):
    """Gudemann 2026: about 2.1 mmol/mol (~0.19 points) average SGLT2i benefit over DPP-4i."""
    truth = true_population_effects(params)
    assert -0.30 < truth["SGLT2i-DPP4i"] < -0.10


def test_features_follow_the_dag(params, cohort):
    X = features(params, cohort)
    assert X.shape == (len(cohort), len(load_dag(params).adjustment_set))


def test_a_real_csv_can_be_ingested(params, cohort, tmp_path):
    path = tmp_path / "records.csv"
    observed_view(cohort).drop(columns=["ckd"]).to_csv(path, index=False)
    df = load_dataset(path, params)
    assert len(df) == len(cohort) and "ckd" in df
    observed_view(cohort).drop(columns=["y"]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="missing columns"):
        load_dataset(path, params)
