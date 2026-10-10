"""Step (g): the benchmark writes every results file the report and slides need."""

import csv
import json

import pytest

from diacausal.causal_inference.benchmark import run, SUMMARY_COLUMNS

FIGURES = ("overlap.png", "love_plot.png", "ate_vs_truth.png", "cate_recovery.png", "calibration.png")


pytestmark = pytest.mark.slow  # the module's fixture runs the benchmark: 45 s or more


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    path = tmp_path_factory.mktemp("results")
    run(reps=2, n=1200, n_test=400, out=path, n_boot=10)
    return path


def test_all_results_files_are_written(out):
    assert (out / "benchmark_summary.csv").exists()
    assert (out / "results_table.tex").exists()
    assert (out / "run_info.json").exists()
    for name in FIGURES:
        f = out / "figures" / name
        assert f.exists() and f.stat().st_size > 10_000, name
        assert f.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_summary_csv_has_every_method_and_metric(out):
    rows = list(csv.DictReader((out / "benchmark_summary.csv").open()))
    assert list(rows[0]) == SUMMARY_COLUMNS
    avg = [r for r in rows if r["section"] == "average_effect"]
    assert {r["method"] for r in avg} == {"naive", "IPW", "matching", "AIPW"}
    assert all(r["bias"] and r["rmse"] and r["coverage_95"] for r in avg)
    assert {r["method"] for r in rows if r["section"] == "patient_effect"} == {"DR-learner", "T-learner", "S-learner", "naive"}
    assert all(r["policy_regret"] for r in rows if r["section"] == "policy")
    assert any(r["section"] == "balance" and r["smd_max_after"] for r in rows)


def test_latex_table_is_a_self_contained_tabular(out):
    tex = (out / "results_table.tex").read_text()
    assert tex.count("\\begin{tabular}") == tex.count("\\end{tabular}") == 2
    assert "SYNTHETIC DATA ONLY" in tex and "AIPW" in tex and "PEHE" in tex
    assert "_" not in tex.replace("\\_", "")  # no raw underscores to break LaTeX


def test_run_info_records_versions_and_says_synthetic(out):
    info = json.loads((out / "run_info.json").read_text())
    assert info["reps"] == 2 and info["params_sha"] and info["rules_sha"]
    assert "synthetic" in info["data"]
    assert info["intended_use"].startswith("Research prototype")


def test_interval_coverage_is_reported_by_evidence_level(out):
    """P24 (plan 8.11): per-patient 95% interval coverage of the true 6-month change, for each evidence level; never High."""
    import csv

    rows = list(csv.DictReader((out / "evidence_level_coverage.csv").open()))
    assert [(r["level"], r["option"]) for r in rows] == [(lv, o) for lv in ("Moderate", "Low", "Insufficient") for o in ("SGLT2i", "DPP4i", "SU", "all")]
    every = [r for r in rows if r["option"] == "all"]
    assert abs(sum(float(r["share"]) for r in every) - 1) < 1e-3 and sum(int(r["n"]) for r in every) > 0
    for r in rows:
        if int(r["n"]):
            assert 0 <= float(r["coverage_95"]) <= 1 and float(r["mean_ci_width"]) > 0
        assert sum(int(x["n"]) for x in rows if x["level"] == r["level"] and x["option"] != "all") == int(next(x for x in every if x["level"] == r["level"])["n"])
