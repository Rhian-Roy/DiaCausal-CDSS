"""P26: the A-D ablation (diacausal/xai/ablation.py, scripts/xai_ablation.py, results/xai_ablation.csv)."""

import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"


def rows(name):
    return list(csv.DictReader((RESULTS / name).read_text(encoding="utf-8").splitlines()))


def num(text):
    return float(text) if text not in ("", "nan") else float("nan")


def test_the_table_has_all_four_versions_and_the_plans_columns():
    data = rows("xai_ablation.csv")
    assert list(data[0]) == ["version", "metric", "comparison", "mean", "ci_low", "ci_high", "n_reps"]
    assert [v for v in ("A", "B", "C", "D") if any(r["version"] == v for r in data)] == ["A", "B", "C", "D"]
    have = {(r["version"], r["metric"], r["comparison"]) for r in data}
    for v in "ABCD":
        assert {(v, "pehe", c) for c in ("SGLT2i-DPP4i", "SU-DPP4i", "SGLT2i-SU")} <= have and (v, "regret", "all") in have
    for v in "CD":
        assert (v, "modifier_top3_overlap", "SGLT2i-DPP4i") in have and (v, "false_driver_rate", "SGLT2i-DPP4i") in have
    assert ("A", "shap_lime_spearman", "SGLT2i-DPP4i") in have and ("D", "citation_precision", "all") in have


def test_b_c_and_d_share_the_engines_numbers_because_they_explain_the_same_estimate():
    data = {(r["version"], r["metric"], r["comparison"]): r for r in rows("xai_ablation.csv")}
    for (v, metric, comp), r in data.items():
        if v == "B":
            for other in ("C", "D"):
                assert data[other, metric, comp]["mean"] == r["mean"], (metric, comp)


def test_the_intervals_bracket_the_means_and_the_synthetic_metrics_use_twenty_replicates():
    for r in rows("xai_ablation.csv"):
        mean, lo, hi = num(r["mean"]), num(r["ci_low"]), num(r["ci_high"])
        if lo == lo:
            assert lo - 1e-9 <= mean <= hi + 1e-9, r
        if r["metric"] in ("citation_precision", "retrieval_recall_at_5", "number_match_pass", "fallback_rate", "driver_passage_hit_rate"):
            assert r["version"] == "D" and r["n_reps"] == "0", r  # fixed question sets, not synthetic cohorts
        elif r["metric"] in ("pehe", "regret", "coverage"):
            assert r["n_reps"] == "20", r


def test_the_driver_passage_hit_rate_is_left_empty_until_its_reviewed_table_exists():
    data = {(r["version"], r["metric"]): r for r in rows("xai_ablation.csv")}
    assert data["D", "driver_passage_hit_rate"]["mean"] == "" and not (ROOT / "eval/xai_driver_evidence.csv").exists()


def test_version_b_gives_far_fewer_numbers_where_data_are_thin_than_version_a():
    data = {(r["version"], r["metric"], r["comparison"]): num(r["mean"]) for r in rows("xai_ablation.csv")}
    assert data["A", "answered_when_thin_pairs", "all"] == 1.0 and data["B", "answered_when_thin_pairs", "all"] < 0.5


def test_the_run_record_is_not_stale_and_the_charts_exist():
    from diacausal.config import load_params
    from diacausal.guards.rules_loader import load_rules

    info = json.loads((RESULTS / "xai_ablation_run_info.json").read_text())
    assert info["reps"] == 20 and info["params_sha"] == load_params().fingerprint and info["rules_sha"] == load_rules().version, \
        "params.yaml or rules.csv changed after the ablation was run: rerun python scripts/xai_ablation.py"
    for name in ("ablation_chart.png", "shap_A_vs_C.png"):
        assert (RESULTS / "xai" / name).stat().st_size > 10_000, name
    true = [r for r in info["shap_A_vs_C"] if r["true_modifier"]]
    assert {r["feature"] for r in true} == {"hba1c", "egfr"}


@pytest.mark.slow
def test_a_quick_rerun_equals_the_committed_quick_file(tmp_path):
    from diacausal.xai import ablation

    out = tmp_path / "q.csv"
    ablation.run(3, 1500, 1000, 20, out, figures=False)
    fresh = {(r["version"], r["metric"], r["comparison"]): r for r in csv.DictReader(out.open())}
    saved = {(r["version"], r["metric"], r["comparison"]): r for r in rows("xai_ablation_quick.csv")}
    assert set(fresh) == set(saved)
    for key, r in saved.items():
        for col in ("mean", "ci_low", "ci_high"):
            a, b = num(r[col]), num(fresh[key][col])
            assert (a != a and b != b) or abs(a - b) <= 1e-9 * max(1.0, abs(a)), (key, col)
