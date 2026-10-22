"""The Analysis tab's three panels (diacausal/causal_inference/analysis_panels.py): every number is read from a results file, nothing is typed,
and the rows where B is not better say so in words. Also version 0 (naive) and the paired B-A rows of results/xai_ablation.csv."""

import csv
import json
import re
import shutil
from pathlib import Path

import pytest

from diacausal.causal_inference import analysis_panels

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
FILES = ("xai_ablation.csv", "rag_eval_summary.csv", "llm/bench_summary.csv")


def rows(path):
    return list(csv.DictReader(Path(path).read_text(encoding="utf-8").splitlines()))


def num(text):
    return float(text) if text not in ("", "nan") else float("nan")


def copy_results(tmp_path):
    for name in FILES:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(RESULTS / name, tmp_path / name)
    return tmp_path


def edit_csv(path, match, column, new):
    data = rows(path)
    hits = [r for r in data if all(r[k] == v for k, v in match.items())]
    assert len(hits) == 1, match
    hits[0][column] = new
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)


def test_the_website_and_the_report_text_hold_exactly_what_the_results_files_give():
    built = analysis_panels.build()
    assert json.loads((ROOT / "web/results.json").read_text())["analysis_panels"] == json.loads(json.dumps(built)), \
        "run: python -m diacausal.causal_inference.export_web"
    assert analysis_panels.TEXT_FILE.read_text(encoding="utf-8") == analysis_panels.text(built), "run: python -m diacausal.causal_inference.analysis_panels"
    assert [p["title"] for p in built["panels"]] == ["From records to causal estimates", "What C adds", "What D adds"]
    for p in built["panels"]:
        assert p["sentence"] and p["sources"] and all(len(r["cells"]) == len(p["columns"]) - 1 for r in p["rows"])


def test_every_cell_of_panel_a_changes_when_its_source_number_changes(tmp_path):
    """Proof that nothing is typed: edit one mean in a copy of the CSV and the matching cell (and only that version's) changes."""
    base = analysis_panels.build(copy_results(tmp_path))["panels"][0]["rows"]
    for i, (metric, comp, _, _) in enumerate(analysis_panels.PANEL_A):
        for j, version in enumerate(("0", "A", "B")):
            d = copy_results(tmp_path / f"{i}{version}")
            try:
                edit_csv(d / "xai_ablation.csv", {"version": version, "metric": metric, "comparison": comp}, "mean", "0.4321")
            except AssertionError:
                assert version == "A" and metric == "coverage"  # A gives no interval: that row has no number to edit
                continue
            after = analysis_panels.build(d)["panels"][0]["rows"][i]["cells"]
            assert after[j] != base[i]["cells"][j] and ("0.4321" in after[j] or "43.2%" in after[j]), (metric, comp, version)


def test_panels_b_and_c_change_when_their_source_numbers_change(tmp_path):
    d = copy_results(tmp_path)
    edit_csv(d / "xai_ablation.csv", {"version": "C", "metric": "false_driver_rate", "comparison": "SU-DPP4i"}, "mean", "0.4321")
    edit_csv(d / "rag_eval_summary.csv", {"metric": "dose_leaks"}, "value", "7")
    edit_csv(d / "llm/bench_summary.csv", {"model_key": "candidate_a"}, "fallback_pct", "12.5")
    b, c = analysis_panels.build(d)["panels"][1:]
    assert any("43.2%" in r["cells"][1] for r in b["rows"] if r["metric"] == "false_driver_rate")
    assert "7 of 60" in next(r for r in c["rows"] if r["metric"] == "dose_leaks")["cells"][0]
    assert "12.5%" in next(r for r in c["rows"] if r["metric"] == "fallback_pct")["cells"][0] and "7 answers contained dose text" in c["sentence"]


def test_rows_where_b_is_not_better_say_no_improvement_and_unclear_ones_say_so():
    panel = analysis_panels.build()["panels"][0]
    ab = {(r["version"], r["metric"], r["comparison"]): r for r in rows(RESULTS / "xai_ablation.csv")}
    for metric, comp, label, kind in analysis_panels.PANEL_A:
        row = next(r for r in panel["rows"] if r["metric"] == metric and r["comparison"] == comp)
        if kind == "coverage":
            assert row["verdict"] == "not comparable" and row["cells"][1] == "no interval"
            continue
        a, b = num(ab["A", metric, comp]["mean"]), num(ab["B", metric, comp]["mean"])
        b_better = abs(b) < abs(a) if kind == "bias" else (b > a if kind == "share_up" else b < a)
        if not b_better:
            assert row["verdict"] == "no improvement" and "no improvement" in row["cells"][3], label
        paired = ab.get(("B-A", metric, comp))
        if b_better and paired and num(paired["ci_low"]) <= 0 <= num(paired["ci_high"]):
            assert row["verdict"] == "not a clear difference" and "not a clear difference" in row["cells"][3], label
    # the guide's example: regret's 16% is a point estimate whose paired interval includes 0, and the tab says so
    regret = next(r for r in panel["rows"] if r["metric"] == "regret")
    assert regret["cells"][3].startswith("16% lower") and regret["verdict"] == "not a clear difference"
    assert sum(r["verdict"] == "no improvement" for r in panel["rows"] if r["metric"] == "pehe") >= 1
    for bar in panel["chart"]:
        assert bar["worse"] == (bar["value"] <= 0) and abs(bar["value"]) <= panel["chart_max"]
        assert bar["clear"] == (next(r for r in panel["rows"] if r["label"] == bar["label"])["verdict"] == "better")


def test_the_naive_column_is_computed_on_the_same_cohorts_as_the_benchmark():
    """Version 0 is the benchmark's naive comparison on the same 20 cohorts: its PEHE equals results/benchmark_summary.csv's."""
    ab = {(r["version"], r["metric"], r["comparison"]): r for r in rows(RESULTS / "xai_ablation.csv")}
    bench = {(r["section"], r["method"], r["target"]): r for r in rows(RESULTS / "benchmark_summary.csv")}
    for c in ("SGLT2i-DPP4i", "SU-DPP4i", "SGLT2i-SU"):
        assert abs(num(ab["0", "pehe", c]["mean"]) - num(bench["patient_effect", "naive", c]["pehe"])) < 6e-5, c
        assert ab["0", "pehe", c]["n_reps"] == "20"
    assert num(ab["0", "answered_when_thin_pairs", "all"]["mean"]) == 1.0 and num(ab["0", "abstention_rate", "all"]["mean"]) == 0.0
    # the naive interval misses most patients' true effect; B's covers about 95%
    assert num(ab["0", "coverage", "SGLT2i-DPP4i"]["mean"]) < 0.5 < num(ab["B", "coverage", "SGLT2i-DPP4i"]["mean"])


def test_the_paired_rows_are_b_minus_a_on_the_same_cohorts():
    ab = {(r["version"], r["metric"], r["comparison"]): r for r in rows(RESULTS / "xai_ablation.csv")}
    paired = [k for k in ab if k[0] == "B-A"]
    assert {(m, c) for _, m, c in paired} == set(__import__("diacausal.xai.ablation", fromlist=["PAIRED"]).PAIRED)
    for _, m, c in paired:
        r = ab["B-A", m, c]
        assert r["n_reps"] == "20" and num(r["ci_low"]) <= num(r["mean"]) <= num(r["ci_high"])
        assert abs(num(r["mean"]) - (num(ab["B", m, c]["mean"]) - num(ab["A", m, c]["mean"]))) < 1e-5, (m, c)


def test_the_panel_code_types_no_result_number():
    """The module holds labels and rules, not results: no decimal literal of the kind the results files contain."""
    source = (ROOT / "diacausal/causal_inference/analysis_panels.py").read_text(encoding="utf-8")
    code = "\n".join(line.split("#")[0] for line in source.splitlines() if not line.lstrip().startswith(('"', "'")))
    assert not re.findall(r"(?<![\w.])\d+\.\d{2,}", code)
    app = (ROOT / "web/app.js").read_text(encoding="utf-8")
    panel_js = app[app.index("function renderPanels"):app.index("function renderAblation")]
    assert not re.findall(r"(?<![\w.])\d+\.\d{2,}", panel_js), "web/app.js must not type a result into the panels"


@pytest.mark.parametrize("name", ["xai_ablation.csv", "xai_ablation_quick.csv"])
def test_versions_0_and_b_minus_a_are_in_both_ablation_files(name):
    versions = {r["version"] for r in rows(RESULTS / name)}
    assert {"0", "A", "B", "C", "D", "B-A"} <= versions
