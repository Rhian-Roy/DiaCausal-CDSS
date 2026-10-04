"""The committed version A results in results/xai/: schema, sanity, and not stale."""

import csv
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
XAI = ROOT / "results" / "xai"
COMPARISONS = ["SGLT2i-DPP4i", "SU-DPP4i", "SGLT2i-SU"]
PER_COMPARISON = ["effect_bias", "pehe", "pehe_thin", "pehe_not_thin", "shap_lime_spearman", "shap_lime_top3_jaccard",
                  "modifier_precision_at_k", "modifier_spearman", "lime_top3_jaccard", "lime_top_weight_cv"]
OVERALL = ["pred_rmse", "pred_rmse_all_options", "regret", "best_pick_rate", "abstention_rate", "excluded_by_rules_rate",
           "thin_share", "answered_when_thin"]


def rows(name):
    return list(csv.DictReader((XAI / name).read_text(encoding="utf-8").splitlines()))


def number(text):
    return float(text) if text not in ("", "nan") else float("nan")


def test_the_metrics_file_has_the_columns_of_the_ablation_table_and_every_metric_of_section_6():
    data = rows("baseline_metrics.csv")
    assert list(data[0]) == ["version", "metric", "comparison", "mean", "ci_low", "ci_high", "n_reps"]
    assert {r["version"] for r in data} == {"A"}
    have = {(r["metric"], r["comparison"]) for r in data}
    assert {(m, "all") for m in OVERALL} <= have
    assert {(m, c) for m in PER_COMPARISON for c in COMPARISONS} <= have


def test_the_numbers_are_sane_and_the_intervals_bracket_the_means():
    for r in rows("baseline_metrics.csv"):
        mean, lo, hi = number(r["mean"]), number(r["ci_low"]), number(r["ci_high"])
        assert mean == mean, r  # no NaN means
        if lo == lo:
            assert lo - 1e-9 <= mean <= hi + 1e-9, r
        if r["metric"] in ("abstention_rate", "answered_when_thin", "best_pick_rate", "excluded_by_rules_rate", "thin_share",
                           "shap_lime_top3_jaccard", "lime_top3_jaccard", "modifier_precision_at_k"):
            assert 0 <= mean <= 1, r
        if r["metric"].startswith(("pehe", "pred_rmse", "regret")):
            assert mean >= 0, r


def test_version_a_never_abstains_and_answers_thin_patients_and_the_per_replicate_metrics_use_all_twenty():
    data = {(r["metric"], r["comparison"]): r for r in rows("baseline_metrics.csv")}
    assert number(data["abstention_rate", "all"]["mean"]) == 0.0
    assert number(data["answered_when_thin", "all"]["mean"]) == 1.0
    assert data["pehe", "SGLT2i-DPP4i"]["n_reps"] == "20" and data["regret", "all"]["n_reps"] == "20"
    assert number(data["pehe_thin", "SGLT2i-DPP4i"]["mean"]) > number(data["pehe_not_thin", "SGLT2i-DPP4i"]["mean"])  # worse where data are thin


def test_lime_stability_has_ten_seeds_for_each_option_pair_the_rules_leave():
    data = rows("lime_stability.csv")
    assert {(r["preset"], r["comparison"]) for r in data} == {("typical", c) for c in COMPARISONS} | {("egfr40_pancreatitis", "SU-DPP4i"), ("older_hypo", "SU-DPP4i")}
    assert all(r["n_seeds"] == "10" and 0 <= number(r["lime_top3_jaccard"]) <= 1 for r in data)


def test_the_run_record_says_what_was_run_and_the_results_are_not_stale():
    info = json.loads((XAI / "run_info.json").read_text())
    assert (info["reps"], info["n"], info["n_test"], info["lime_seeds_per_preset"], info["shap_mode"]) == (20, 5000, 2000, 10, "tree_path_dependent")
    assert info["shap"] == "0.52.0" and info["lime"] == "0.2.0.1" and "never shown to a doctor" in info["note"]
    from diacausal.config import load_params
    from diacausal.guards.rules_loader import load_rules

    assert info["params_sha"] == load_params().fingerprint and info["rules_sha"] == load_rules().version, (
        "params.yaml or rules.csv changed after results/xai was made: rerun python -m diacausal.xai.baseline")
    assert "SGLT2i" not in info["presets"]["egfr40_pancreatitis"]["allowed"]  # the same rule exclusions as the engine (R01)


def test_the_figures_exist_and_are_real_images():
    import matplotlib.image as mpimg

    names = ["beeswarm_A.png", "lime_stability_A.png"] + [f"waterfall_A_{r['preset']}_{r['comparison']}.png" for r in rows("lime_stability.csv")]
    assert len(names) == 7
    for name in names:
        image = mpimg.imread(XAI / name)
        assert image.shape[0] > 200 and image.shape[1] > 300, name


def test_the_shap_file_has_global_importance_for_every_comparison_and_the_presets():
    data = rows("shap_A.csv")
    glob = [r for r in data if r["scope"] == "global"]
    assert {r["comparison"] for r in glob} == set(COMPARISONS) and len(glob) == 36 and all(number(r["mean_abs_phi"]) >= 0 for r in glob)
    presets = {(r["preset"], r["comparison"]) for r in data if r["scope"] == "preset"}
    assert len(presets) == 5 and all(any(r["feature"] == "drug (prescribing mix)" for r in data if (r["preset"], r["comparison"]) == p) for p in presets)


def test_a_quick_rerun_reproduces_the_committed_quick_file(tmp_path):
    """Catches any change to the code, the data or the settings that would move version A's numbers. Platform tolerance:
    1e-3 (HistGradientBoosting and LIME may differ in the last digits between macOS and Linux)."""
    pytest.importorskip("shap")
    pytest.importorskip("lime")
    from diacausal.xai import baseline as b

    b.run(3, 1500, 1000, 20, tmp_path, samples=2000, draw_figures=False)
    new = {(r["metric"], r["comparison"]): r for r in csv.DictReader((tmp_path / "baseline_metrics.csv").read_text().splitlines())}
    old = {(r["metric"], r["comparison"]): r for r in rows("baseline_metrics_quick.csv")}
    assert new.keys() == old.keys()
    for key in new:
        assert number(new[key]["mean"]) == pytest.approx(number(old[key]["mean"]), abs=1e-3, nan_ok=True), (
            f"{key} moved: regenerate with run(3, 1500, 1000, 20, <folder>, samples=2000) and copy baseline_metrics.csv to "
            "results/xai/baseline_metrics_quick.csv")
    shutil.rmtree(tmp_path, ignore_errors=True)
