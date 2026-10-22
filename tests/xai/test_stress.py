"""The pre-registered stress test (docs/XAI_PLAN.md section 10; diacausal/xai/stress.py, scripts/xai_stress.py, results/xai_stress.csv)."""

import csv
import re
from pathlib import Path

import numpy as np
import pytest

from diacausal.causal_inference.cohort import generate_cohort, true_propensity
from diacausal.config import load_params
from diacausal.xai import stress

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"


def rows(name):
    return list(csv.DictReader((RESULTS / name).read_text(encoding="utf-8").splitlines()))


def test_the_multiplier_is_a_team_set_parameter_and_one_changes_nothing():
    params = load_params()
    entry = params.entry("generator.assignment.confounding_multiplier")
    assert entry["value"] == 1.0 and entry["status"] == "TEAM-SET" and entry["source"]
    a = generate_cohort(params, n=800, seed=3)
    b = generate_cohort(stress.with_multiplier(params, 1.0), n=800, seed=3)
    assert a.equals(b)  # 1.0 is today's generator, bit for bit
    assert not a.equals(generate_cohort(stress.with_multiplier(params, 2.0), n=800, seed=3))


def test_the_multiplier_scales_the_coefficients_and_never_the_intercepts():
    params = load_params()
    cohort = generate_cohort(params, n=500, seed=5)
    centre = params.group("generator.assignment.centre")
    at_centre = cohort.iloc[:1].copy()
    for var, value in centre.items():
        at_centre[var] = value
    for var in ("ascvd", "hf", "hypo_history", "dka_history", "pancreatitis_history", "low_income"):
        at_centre[var] = 0
    p1, p2 = true_propensity(params, at_centre), true_propensity(stress.with_multiplier(params, 2.0), at_centre)
    assert np.allclose(p1, p2)  # with every detail at its centring point only the intercepts act
    off = cohort.iloc[:200]
    assert not np.allclose(true_propensity(params, off), true_propensity(stress.with_multiplier(params, 2.0), off))
    assert np.allclose(true_propensity(params, off), true_propensity(stress.with_multiplier(params, 1.0), off), rtol=0, atol=0)


def test_the_plan_was_committed_before_the_code_and_fixes_the_runs():
    plan = (ROOT / "docs" / "XAI_PLAN.md").read_text(encoding="utf-8")
    section = plan[plan.index("## 10. Pre-registered stress test"):]
    for must in ("1.0, 1.5 and 2.0", "seeds 7, 8, 9", "3 replicates", "Hypotheses, written before running", "Reporting rule", "none is dropped"):
        assert must in section, must
    assert [m for m in stress.MULTIPLIERS] == [1.0, 1.5, 2.0] and (stress.REPS, stress.N, stress.N_TEST) == (3, 1500, 1000)


def test_at_multiplier_one_the_stress_rows_equal_the_committed_quick_ablation():
    """The pre-registered check: versions 0, A and B and the paired rows at 1.0 are exactly the ablation's quick-mode numbers."""
    quick = {(r["version"], r["metric"], r["comparison"]): r for r in rows("xai_ablation_quick.csv")}
    one = [r for r in rows("xai_stress.csv") if r["multiplier"] == "1" and r["version"] in ("0", "A", "B", "B-A")]
    checked = 0
    for r in one:
        key = (r["version"], r["metric"], r["comparison"])
        if key in quick:
            assert all(quick[key][c] == r[c] for c in ("mean", "ci_low", "ci_high")), key
            checked += 1
    assert checked >= 80  # rows (each compared in mean, ci_low and ci_high): every 0, A, B and B-A row the ablation also has


def test_the_results_file_holds_every_multiplier_version_and_reported_metric():
    data = rows("xai_stress.csv")
    assert list(data[0]) == stress.COLUMNS
    assert {r["multiplier"] for r in data} == {"1", "1.5", "2"} and {r["version"] for r in data} == {"cohort", "0", "A", "B", "B-A"}
    have = {(r["multiplier"], r["version"], r["metric"], r["comparison"]) for r in data}
    for m in ("1", "1.5", "2"):
        assert (m, "cohort", "thin_share", "all") in have and (m, "B", "abstention_rate", "all") in have
        for v in ("0", "A", "B"):
            assert (m, v, "regret", "all") in have and (m, v, "pred_rmse", "all") in have and (m, v, "best_pick_rate", "all") in have
            assert all((m, v, k, c) in have for k in ("effect_bias", "abs_effect_bias", "pehe") for c in ("SGLT2i-DPP4i", "SU-DPP4i", "SGLT2i-SU"))
        assert all((m, "B-A", k, "all") in have for k in ("regret", "pred_rmse", "best_pick_rate", "answered_when_thin_pairs"))
    assert all(r["n_reps"] == "3" for r in data if r["version"] != "B-A" or r["mean"])


def test_the_xai_plan_records_the_results_against_each_hypothesis():
    plan = (ROOT / "docs" / "XAI_PLAN.md").read_text(encoding="utf-8")
    section = plan[plan.index("## 10. Pre-registered stress test"):]
    assert "Results (22 Oct 2026" in section
    for n in range(1, 6):
        assert re.search(rf"\bH{n}\b", section[section.index("Results (22 Oct 2026"):]), n


@pytest.mark.slow
def test_a_rerun_equals_the_committed_stress_file(tmp_path):
    out = tmp_path / "s.csv"
    stress.run(out=out)
    assert out.read_text(encoding="utf-8") == (RESULTS / "xai_stress.csv").read_text(encoding="utf-8")
