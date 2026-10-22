"""The Analysis tab's three panels (Naive vs A vs B; what C adds; what D adds), built from the committed results files only.

Every number on these panels is READ from a results file and every relative change is COMPUTED here from those numbers; the website
(web/app.js) only places the strings, and report/assets/ANALYSIS_TAB_TEXT.md is written from the same data. Nothing is typed:
tests/xai/test_analysis_panels.py rebuilds the panels from the CSVs and compares.

    results/xai_ablation.csv           versions 0 (naive), A, B, C and the paired differences B-A (20 synthetic cohorts)
    results/xai_stress.csv             the pre-registered stress test: the same comparison at 1.0, 1.5 and 2.0 times the confounding
    results/rag_eval_summary.csv       the 60 gold questions with the template writer (citations, dose leaks)
    results/llm/bench_summary.csv      the 20 golden questions with the local model (number check, fallback)

    python -m diacausal.causal_inference.analysis_panels     ->  report/assets/ANALYSIS_TAB_TEXT.md  (run after the ablation; export_web reads build())

SYNTHETIC BENCHMARK. Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

from diacausal import INTENDED_USE
from diacausal.config import ROOT, RESULTS_DIR

TEXT_FILE = ROOT / "report" / "assets" / "ANALYSIS_TAB_TEXT.md"
ABLATION = "results/xai_ablation.csv"
STRESS = "results/xai_stress.csv"
RAG = "results/rag_eval_summary.csv"
LLM = "results/llm/bench_summary.csv"
LLM_MODEL = "candidate_a"  # the model the ablation's D rows use (diacausal/xai/ablation.py retrieval_and_writing_rows)
PAIRS = {"SGLT2i-DPP4i": "SGLT2i vs DPP-4i", "SU-DPP4i": "Sulfonylurea vs DPP-4i", "SGLT2i-SU": "SGLT2i vs sulfonylurea"}

# Panel a: (metric, comparison, label, kind). kind: "hba1c" (lower is better, HbA1c points), "bias" (closer to 0 is better),
# "share_up" (a share, higher is better), "share_down" (a share, lower is safer), "coverage" (a share; 95% is the target)
PANEL_A = [("effect_bias", "SGLT2i-DPP4i", "Bias of the average effect, SGLT2i vs DPP-4i", "bias"),
           ("coverage", "SGLT2i-DPP4i", "Patients whose true effect lies in the 95% interval, SGLT2i vs DPP-4i", "coverage"),
           ("regret", "all", "Regret: extra HbA1c vs the truly best allowed drug", "hba1c"),
           ("pred_rmse", "all", "Error of the predicted HbA1c change (RMSE)", "hba1c"),
           ("best_pick_rate", "all", "Picks the truly best allowed drug", "share_up"),
           ("answered_when_thin_pairs", "all", "Numbers given where similar patients are too few", "share_down"),
           *(("pehe", c, f"Error of each patient's effect (PEHE), {PAIRS[c]}", "hba1c") for c in PAIRS)]


def _rows(path: Path) -> list[dict]:
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


def _num(text: str) -> float:
    return float(text) if text not in ("", "nan") else math.nan


def _hba1c(x: float) -> str:
    return f"{x:.4f}"


def _pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f}%"


def _value(kind: str, x: float) -> str:
    if math.isnan(x):
        return ""
    return _pct(x) if kind in ("share_up", "share_down", "coverage") else _hba1c(x) if kind != "bias" else f"{x:+.4f}"


def _cell(kind: str, r: dict | None, missing: str) -> str:
    if r is None or math.isnan(_num(r["mean"])):
        return missing
    text = _value(kind, _num(r["mean"]))
    if not math.isnan(_num(r["ci_low"])) and _num(r["ci_low"]) != _num(r["ci_high"]):
        text += f" (95% CI {_value(kind, _num(r['ci_low']))} to {_value(kind, _num(r['ci_high']))})"
    return text


def _nice(v: float) -> int:
    """The chart's axis end: v rounded up to one significant digit (87.2 -> 90), in percent."""
    step = 10 ** math.floor(math.log10(v))
    return int(math.ceil(v / step) * step)


def _whole(p: float) -> str:
    """A relative change in whole percent ("16%"); below 1% it says so instead of rounding to 0."""
    return f"{round(abs(p) * 100)}%" if abs(p) >= 5e-3 else "less than 1%"


def change(kind: str, a: float, b: float, paired: dict | None) -> dict:
    """A -> B for one row: the words, the relative change (+ = B better) for the chart, and whether B is better at all.
    `paired` is the B-A row (paired 95% interval of the difference on the same cohorts), when the ablation wrote one."""
    if kind == "coverage":
        words = "A gives no interval, so only B and the naive comparison can be checked against 95%"
        return {"text": words, "words": words, "relative": None, "verdict": "not comparable"}
    if kind == "bias":
        rel = (abs(a) - abs(b)) / abs(a)
        words = f"{_whole(rel)} {'smaller' if rel > 0 else 'larger'} bias"
    elif kind == "hba1c":
        rel = (a - b) / a
        words = f"{_whole(rel)} {'lower' if rel > 0 else 'higher'}"
    elif kind == "share_up":
        rel = (b - a) / a
        words = f"{abs(b - a) * 100:.1f} points {'higher' if b > a else 'lower'} ({_whole(rel)} {'more' if b > a else 'fewer'})"
    else:  # share_down: fewer numbers where data are thin is safer
        rel = (a - b) / a
        words = f"{abs(b - a) * 100:.1f} points {'lower' if b < a else 'higher'} ({_whole(rel)} {'fewer' if b < a else 'more'})"
    better = rel > 0
    clear = None
    if paired is not None and not math.isnan(_num(paired["ci_low"])):
        lo, hi = _num(paired["ci_low"]), _num(paired["ci_high"])
        clear = not (lo <= 0.0 <= hi)
        unit = (lambda v: f"{v * 100:+.1f} points") if kind.startswith("share") else (lambda v: f"{v:+.4f}")
        paired_text = f"paired 95% interval of B minus A {unit(lo)} to {unit(hi)}"
    else:
        paired_text = ""
    verdict = "no improvement" if not better else "not a clear difference" if clear is False else "better"
    text = words + (f": {verdict}" if verdict != "better" else "") + (f"; {paired_text}" if paired_text else "")
    short = {"bias": "smaller bias" if better else "larger bias", "hba1c": "lower" if better else "higher"}.get(
        kind, ("more" if better else "fewer") if kind == "share_up" else ("fewer" if better else "more"))
    short = f"{_whole(rel)} {short}" + {"no improvement": ", no improvement", "not a clear difference": ", not clear"}.get(verdict, "")
    return {"text": text, "words": words, "short": short, "relative": rel, "verdict": verdict}


def panel_a(ab: dict) -> dict:
    rows, chart = [], []
    for metric, comp, label, kind in PANEL_A:
        n, a, b = ab.get(("0", metric, comp)), ab.get(("A", metric, comp)), ab.get(("B", metric, comp))
        ch = change(kind, _num(a["mean"]) if a else math.nan, _num(b["mean"]), ab.get(("B-A", metric, comp)))
        if kind == "bias":  # no paired row: say whether each version's own 95% interval contains 0 (no bias)
            has0 = {v: _num(r["ci_low"]) <= 0.0 <= _num(r["ci_high"]) for v, r in (("A", a), ("B", b))}
            ch["text"] += "; 95% interval " + ", ".join(f"{v} {'includes' if z else 'excludes'} 0" for v, z in has0.items())
        rows.append({"label": label, "metric": metric, "comparison": comp,
                     "cells": [_cell(kind, n, "not measured"), _cell(kind, a, "no interval" if kind == "coverage" else "not measured"),
                               _cell(kind, b, "not measured"), ch["text"]],
                     "verdict": ch["verdict"]})
        if ch["relative"] is not None:
            chart.append({"label": label, "value": round(ch["relative"] * 100, 1), "text": ch["short"],
                          "worse": ch["verdict"] == "no improvement", "clear": ch["verdict"] == "better"})
        rows[-1]["words"] = ch["words"]
    by = {(r["metric"], r["comparison"]): r for r in rows}
    qualify = lambda r: r["words"] + ("" if r["verdict"] == "better" else f" ({r['verdict']})")  # noqa: E731
    thin_a, thin_b = (ab[v, "answered_when_thin_pairs", "all"]["mean"] for v in ("A", "B"))
    pehe_bad = sum(by["pehe", c]["verdict"] != "better" for c in PAIRS)
    sentence = (f"B adjusts for why each patient received their drug instead of only learning from the records as A does: compared with A, "
                f"its regret is {qualify(by['regret', 'all'])}, the average effect has {qualify(by['effect_bias', 'SGLT2i-DPP4i'])}, and it "
                f"gives numbers for {_pct(_num(thin_b))} of the patient-option pairs where similar patients are too few instead of "
                f"{_pct(_num(thin_a))}; its error on each patient's effect (PEHE) shows no clear improvement on {pehe_bad} of {len(PAIRS)} comparisons. "
                f"The naive comparison of group averages has a regret of {_hba1c(_num(ab['0', 'regret', 'all']['mean']))} (A "
                f"{_hba1c(_num(ab['A', 'regret', 'all']['mean']))}, B {_hba1c(_num(ab['B', 'regret', 'all']['mean']))}) and its interval contains "
                f"the true SGLT2i vs DPP-4i effect for {_pct(_num(ab['0', 'coverage', 'SGLT2i-DPP4i']['mean']))} of patients (B "
                f"{_pct(_num(ab['B', 'coverage', 'SGLT2i-DPP4i']['mean']))}).")
    return {"id": "a", "title": "From records to causal estimates", "sentence": sentence,
            "columns": ["Measure", "Naive comparison (version 0)", "A · XAI only", "B · causal engine", "A → B"],
            "rows": rows, "chart": chart, "chart_max": _nice(max(abs(c["value"]) for c in chart)), "sources": [ABLATION, "results/benchmark_summary.csv (the same 20 cohorts; naive PEHE agrees)"],
            "note": "Mean over 20 synthetic cohorts with its 95% interval. The naive comparison uses the plain average HbA1c change in each "
                    "drug group of the records for every patient. C and D do not change B's estimate, so they are not repeated here."}


def panel_b(ab: dict) -> dict:
    rows = []
    for c, pair in PAIRS.items():
        rows.append({"label": f"Contributions add up to the estimate (largest error), {pair}", "metric": "additivity_max_error", "comparison": c,
                     "cells": ["not applicable", f"{_num(ab['C', 'additivity_max_error', c]['mean']):.1e}"]})
    for c, pair in PAIRS.items():
        a, cc = ab["A", "modifier_precision_at_k", c], ab["C", "modifier_precision_at_k", c]
        rows.append({"label": f"Top features that are true effect modifiers, {pair}", "metric": "modifier_precision_at_k", "comparison": c,
                     "cells": [_cell("share_up", a, "not measured"), _cell("share_up", cc, "not measured")],
                     "verdict": "A higher" if _num(a["mean"]) > _num(cc["mean"]) else "C higher or equal"})
    for c, pair in PAIRS.items():
        rows.append({"label": f"Shown drivers that are not true effect modifiers, {pair}", "metric": "false_driver_rate", "comparison": c,
                     "cells": ["A shows no drivers", _cell("share_down", ab["C", "false_driver_rate", c], "not measured")]})
    worst = max(_num(ab["C", "additivity_max_error", c]["mean"]) for c in PAIRS)
    false = [_num(ab["C", "false_driver_rate", c]["mean"]) for c in PAIRS]
    a_higher = sum(r.get("verdict") == "A higher" for r in rows)
    sentence = (f"C splits B's estimate into one contribution per patient detail that adds up to the estimate (largest error {worst:.1e}) and "
                f"shows only the details whose 95% interval excludes zero; {_pct(min(false), 0)} to {_pct(max(false), 0)} of the drivers it shows "
                f"are not true effect modifiers, and A's top features match the true modifiers more often than C's on {a_higher} of "
                f"{len(PAIRS)} comparisons.")
    return {"id": "b", "title": "What C adds", "sentence": sentence, "columns": ["Measure", "A · XAI only", "C · B + exact SHAP"], "rows": rows,
            "sources": [ABLATION], "note": "Drivers describe the estimate, never a cause. A's SHAP explains a prediction model, not an effect. An interval past 100% is "
                    "the t-interval of the 20 cohorts as the ablation wrote it (most cohorts score 100%), not a value above 100%."}


def panel_c(rag: dict, llm: dict) -> dict:
    n_gold, n_golden = int(_num(rag["questions"])), int(_num(llm["n"]))
    rows = [{"label": "Quoted sentences supported by their cited passage (citation precision)", "metric": "citation_precision",
             "cells": [_pct(_num(rag["citation_precision"])), f"{n_gold} gold questions, template writer", RAG]},
            {"label": "Answers that contained dose text (dose leaks)", "metric": "dose_leaks",
             "cells": [f"{int(_num(rag['dose_leaks']))} of {n_gold}", f"{n_gold} gold questions, template writer", RAG]},
            {"label": "Local-model drafts whose every number is in the causal output", "metric": "number_match_pct",
             "cells": [f"{_num(llm['number_match_pct']):.1f}%", f"{n_golden} golden questions, local model ({LLM_MODEL})", LLM]},
            {"label": "Local-model drafts replaced by the template after a failed check", "metric": "fallback_pct",
             "cells": [f"{_num(llm['fallback_pct']):.1f}%", f"{n_golden} golden questions, local model ({LLM_MODEL})", LLM]}]
    sentence = (f"D finds cited passages and writes the explanation, and checks every draft before it is shown: on the {n_gold} gold questions "
                f"{_pct(_num(rag['citation_precision']), 0)} of the quoted sentences were supported by their cited passage and "
                f"{int(_num(rag['dose_leaks']))} answers contained dose text; the local model's drafts failed a check on {_num(llm['fallback_pct']):.0f}% "
                f"of the {n_golden} golden questions, so the template answered instead.")
    return {"id": "c", "title": "What D adds", "sentence": sentence, "columns": ["Measure", "Value", "Measured on", "Source"], "rows": rows,
            "sources": [RAG, LLM], "note": "Fixed question sets, not synthetic cohorts, so these values have no interval."}


# Panel d (stress test): (metric, comparison, label, direction, paired). direction: "lower" or "higher" is better for B; paired: has a B-A row
STRESS_ROWS = [("abs_effect_bias", c, f"Bias of the average effect (absolute), {PAIRS[c]}", "lower", True) for c in PAIRS] + \
              [("pehe", c, f"Error of each patient's effect (PEHE), {PAIRS[c]}", "lower", True) for c in PAIRS] + \
              [("coverage", c, f"Patients whose true effect lies in the 95% interval, {PAIRS[c]}", "higher", False) for c in PAIRS] + \
              [("regret", "all", "Regret: extra HbA1c vs the truly best allowed drug", "lower", True),
               ("pred_rmse", "all", "Error of the predicted HbA1c change (RMSE)", "lower", True),
               ("best_pick_rate", "all", "Picks the truly best allowed drug", "higher", True),
               ("answered_when_thin_pairs", "all", "Numbers given where similar patients are too few", "lower", True),
               ("abstention_rate", "all", "Options the engine withholds (B only)", "higher", False)]
SHARES = {"coverage", "best_pick_rate", "answered_when_thin_pairs", "abstention_rate", "thin_share"}
VERSION_NAMES = {"0": "Naive", "A": "A", "B": "B"}


def _stress_value(metric: str, x: float) -> str:
    return _pct(x) if metric in SHARES else _hba1c(x)


def _stress_pair(metric: str, direction: str, r: dict) -> dict:
    """B minus A for one measure at one multiplier, in words (the same words as panel a)."""
    d, lo, hi = _num(r["mean"]), _num(r["ci_low"]), _num(r["ci_high"])
    better = d < 0 if direction == "lower" else d > 0
    clear = not (lo <= 0.0 <= hi)
    shown = (lambda v: f"{v * 100:+.1f} points") if metric in SHARES else (lambda v: f"{v:+.4f}")
    verdict = "no improvement" if not better else "better" if clear else "not a clear difference"
    words = {"no improvement": "no improvement" + (" (B clearly worse)" if clear else ""), "better": "B clearly better",
             "not a clear difference": "not a clear difference"}[verdict]
    return {"verdict": verdict, "clear": clear, "better": better,
            "text": f"B minus A {shown(d)} (95% interval {shown(lo)} to {shown(hi)}): {words}"}


def panel_d(st: dict, multipliers: list[str]) -> dict:
    rows, tally = [], {"better": 0, "no improvement": 0, "not a clear difference": 0, "clearly worse": 0}
    for metric, comp, label, direction, paired in STRESS_ROWS:
        cells, verdicts = [], []
        for m in multipliers:
            parts = []
            for v in ("0", "A", "B"):
                r = st.get((m, v, metric, comp))
                if r is not None and not math.isnan(_num(r["mean"])):
                    parts.append(f"{VERSION_NAMES[v]} {_stress_value(metric, _num(r['mean']))}")
            text = " · ".join(parts)
            if paired:
                pr = _stress_pair(metric, direction, st[m, "B-A", metric, comp])
                text += f"; {pr['text']}"
                verdicts.append(pr)
                if metric != "answered_when_thin_pairs":  # counted separately: B withholds those numbers by design
                    tally[pr["verdict"]] += 1
                    tally["clearly worse"] += int(pr["verdict"] == "no improvement" and pr["clear"])
            cells.append(text)
        not_better = sum(not v["better"] for v in verdicts)
        rows.append({"label": label, "metric": metric, "comparison": comp, "cells": cells,
                     "verdict": "no improvement" if paired and not_better * 2 > len(verdicts) else "mixed" if paired else "not compared"})
    thin = [_num(st[m, "cohort", "thin_share", "all"]["mean"]) for m in multipliers]
    abst = [_num(st[m, "B", "abstention_rate", "all"]["mean"]) for m in multipliers]
    cov_b = [_num(st[m, "B", "coverage", c]["mean"]) for m in multipliers for c in PAIRS]
    cov_n = {m: [_num(st[m, "0", "coverage", c]["mean"]) for c in PAIRS] for m in multipliers}
    rows.insert(0, {"label": "Patients with too few similar patients (smallest true propensity below 0.05)", "metric": "thin_share", "comparison": "all",
                    "cells": [_pct(x) for x in thin], "verdict": "not compared"})
    n_all = tally["better"] + tally["no improvement"] + tally["not a clear difference"]
    sentence = (f"With the drug choice depending {multipliers[1]} and {multipliers[2]} times as strongly on the patient's details, the share of patients with too few similar patients grows from {_pct(thin[0])} to {_pct(thin[-1])}, B withholds "
                f"{_pct(abst[0])} to {_pct(abst[-1])} of the options, and B's intervals keep containing the true effect ({_pct(min(cov_b))} to "
                f"{_pct(max(cov_b))} of patients) while the naive comparison's fall to {_pct(min(cov_n[multipliers[-1]]))}; but B does not pull ahead of A: "
                f"of {n_all} paired comparisons (3 multipliers x the measures with a paired interval, not counting the numbers B withholds), B is "
                f"clearly better on {tally['better']}, clearly worse on {tally['clearly worse']}, and shows no improvement or no clear difference "
                f"on the other {n_all - tally['better'] - tally['clearly worse']}.")
    return {"id": "d", "title": "When confounding is stronger", "sentence": sentence,
            "columns": ["Measure", *(f"Drug choice x{m}" + (" (today's data)" if m == multipliers[0] else "") for m in multipliers)],
            "rows": rows, "sources": [STRESS],
            "note": "Pre-registered before any run (docs/XAI_PLAN.md section 10): quick mode, 3 synthetic cohorts of 1,500 patients per multiplier "
                    "(fewer and smaller than the 20 cohorts of 5,000 above), so every interval is wide and a single small cohort is a noisy "
                    "judge; a multiplier raises confounding and removes overlap together. Naive = plain group averages; B minus A is paired on the "
                    "same cohorts; absolute bias is the absolute value of each cohort's bias, averaged over the cohorts; every row of the results "
                    "file is shown."}


def build(results_dir: Path = RESULTS_DIR) -> dict:
    """The three panels, from the results files only. Raises KeyError if a file lacks a row the panels need (rerun the ablation)."""
    ab = {(r["version"], r["metric"], r["comparison"]): r for r in _rows(results_dir / "xai_ablation.csv")}
    rag = {r["metric"]: r["value"] for r in _rows(results_dir / "rag_eval_summary.csv")}
    llm = {r["model_key"]: r for r in _rows(results_dir / "llm" / "bench_summary.csv")}[LLM_MODEL]
    panels = [panel_a(ab), panel_b(ab), panel_c(rag, llm)]
    stress_file = results_dir / "xai_stress.csv"
    if stress_file.exists():
        stress = _rows(stress_file)
        panels.append(panel_d({(r["multiplier"], r["version"], r["metric"], r["comparison"]): r for r in stress},
                              sorted({r["multiplier"] for r in stress}, key=float)))
    return {"panels": panels, "synthetic": True}


def text(panels: dict) -> str:
    """report/assets/ANALYSIS_TAB_TEXT.md: the panel sentences and the relative changes, for the report and the slides."""
    out = ["# Analysis tab: the three panels (for the report and the slides)", "",
           f"> {INTENDED_USE}", "",
           "Written by `python -m diacausal.causal_inference.analysis_panels` from `results/xai_ablation.csv`, `results/rag_eval_summary.csv` and "
           "`results/llm/bench_summary.csv`. Do not edit by hand: a test rebuilds it. **Synthetic benchmark**: it tests whether the methods "
           "recover a planted truth, not real-world drug effects.", ""]
    for p in panels["panels"]:
        out += [f"## {p['title']}", "", p["sentence"], ""]
        if p["id"] == "a":
            out += ["| Measure | A → B |", "|---|---|"] + [f"| {r['label']} | {r['cells'][3]} |" for r in p["rows"]]
        else:
            out += ["| " + " | ".join(p["columns"]) + " |", "|" + "---|" * len(p["columns"])]
            out += ["| " + " | ".join([r["label"], *r["cells"]]) + " |" for r in p["rows"]]
        out += ["", f"Source: {', '.join('`' + s.split(' ')[0] + '`' for s in p['sources'])}. {p['note']}", ""]
    return "\n".join(out)


def main() -> None:
    TEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
    TEXT_FILE.write_text(text(build()), encoding="utf-8")
    print(f"wrote {TEXT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
