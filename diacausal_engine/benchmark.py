"""Step (g): run the whole causal pipeline many times on fresh synthetic cohorts and grade it.

    python -m diacausal_engine.benchmark            # full: 20 repeats x 5,000 patients
    python -m diacausal_engine.benchmark --quick    # quick check: 3 repeats x 1,500 patients

Writes to results/ (or --out):
    benchmark_summary.csv, results_table.tex, run_info.json, refutation.csv, evalues.csv,
    figures/overlap.png, love_plot.png, ate_vs_truth.png, cate_recovery.png, calibration.png

SYNTHETIC DATA ONLY: the numbers show whether the METHODS recover a known truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import time
from pathlib import Path

import numpy as np

from diacausal_engine import ARMS, CONTRASTS, INTENDED_USE, __version__
from diacausal_engine import figures as fig
from diacausal_engine.cohort import features, generate_cohort, observed_view, treatment_index, true_population_effects
from diacausal_engine.config import ROOT, load_params
from diacausal_engine.dag import load_dag
from diacausal_engine.estimators import (
    aipw,
    by_target,
    ipw,
    levels_to_targets,
    matching,
    naive,
    s_learner,
    t_learner,
)
from diacausal_engine.fitting import fit_all
from diacausal_engine.guardrails import load_rules
from diacausal_engine.metrics import abstention_rate, balance_table, bias, coverage, pehe, policy_regret, rmse
from diacausal_engine.propensity import predict
from diacausal_engine.refute import e_value, refute

METHODS = ("naive", "IPW", "matching", "AIPW")
LEARNERS = ("DR-learner", "T-learner", "S-learner", "naive")
SUMMARY_COLUMNS = [
    "section", "method", "target", "true_value", "mean_estimate", "bias", "rmse", "coverage_95",
    "mean_ci_width", "pehe", "policy_regret", "abstention_rate", "smd_max_before", "smd_max_after", "n_reps",
]


def allowed_matrix(params, rules, test, propensity_model) -> np.ndarray:
    """(n, 3): option not excluded by data/rules.csv AND propensity >= overlap threshold."""
    fields = ["age", "egfr", "t1d", "dka_history", "pancreatitis_history", "hf", "hypo_history"]
    safe = np.array(
        [[not v.excluded for v in rules.apply(row).values()] for row in test[fields].to_dict("records")]
    )
    p = predict(propensity_model, features(params, test))
    return safe & (p >= params.get("engine.overlap_min_propensity"))


def run_once(params, rules, n: int, n_test: int, seed: int, n_boot: int) -> dict:
    z = params.get("engine.ci_z")
    settings = params.group("engine.outcome_model")
    cohort = generate_cohort(params, n=n, seed=seed)
    f = fit_all(params, cohort, seed)
    ate = {
        "naive": by_target(naive(f.Y, f.T, z)),
        "IPW": by_target(ipw(f.Y, f.T, f.e, z)),
        "matching": by_target(matching(f.Y, f.T, f.e, z, n_boot, seed)),
        "AIPW": by_target(aipw(f.phi, z)),
    }
    test = generate_cohort(params, n=n_test, seed=seed + 100_000)
    Xt = features(params, test)
    true_levels = test[[f"mu_true_{a}" for a in ARMS]].to_numpy()
    dr = f.dr.predict(Xt, z)
    naive_means = np.array([f.Y[f.T == j].mean() for j in range(len(ARMS))])
    levels = {
        "DR-learner": np.column_stack([dr[a][:, 0] for a in ARMS]),
        "T-learner": t_learner(f.X, f.T, f.Y, Xt, settings, seed),
        "S-learner": s_learner(f.X, f.T, f.Y, Xt, settings, seed),
        "naive": np.tile(naive_means, (len(test), 1)),
    }
    allowed = allowed_matrix(params, rules, test, f.propensity)
    return {
        "ate": ate,
        "levels": levels,
        "dr": dr,
        "true_levels": true_levels,
        "allowed": allowed,
        "balance": balance_table(f.X, load_dag(params).adjustment_set, f.T, f.e),
        "e": f.e,
        "T": f.T,
    }


def summarise(runs: list[dict], truth: dict) -> list[dict]:
    rows = []
    for m in METHODS:
        for a, b in CONTRASTS:
            t = f"{a}-{b}"
            ests = [r["ate"][m][t] for r in runs]
            rows.append({
                "section": "average_effect", "method": m, "target": t, "true_value": truth[t],
                "mean_estimate": np.mean([e.value for e in ests]),
                "bias": bias([e.value for e in ests], truth[t]),
                "rmse": rmse([e.value for e in ests], truth[t]),
                "coverage_95": coverage([e.low for e in ests], [e.high for e in ests], [truth[t]] * len(ests)),
                "mean_ci_width": np.mean([e.high - e.low for e in ests]),
                "n_reps": len(runs),
            })
    for learner in LEARNERS:
        for a, b in CONTRASTS:
            t = f"{a}-{b}"
            p = [pehe(levels_to_targets(r["levels"][learner])[t], levels_to_targets(r["true_levels"])[t]) for r in runs]
            row = {"section": "patient_effect", "method": learner, "target": t, "pehe": np.mean(p), "n_reps": len(runs)}
            if learner == "DR-learner":
                tr = [levels_to_targets(r["true_levels"])[t] for r in runs]
                row["coverage_95"] = np.mean([coverage(r["dr"][t][:, 1], r["dr"][t][:, 2], x) for r, x in zip(runs, tr)])
                row["mean_ci_width"] = np.mean([np.mean(r["dr"][t][:, 2] - r["dr"][t][:, 1]) for r in runs])
            rows.append(row)
        regret = [policy_regret(r["levels"][learner], r["true_levels"], r["allowed"])[0] for r in runs]
        rows.append({
            "section": "policy", "method": learner, "target": "choose lowest predicted HbA1c among allowed options",
            "policy_regret": np.nanmean(regret),
            "abstention_rate": np.mean([abstention_rate(r["allowed"]) for r in runs]),
            "n_reps": len(runs),
        })
    rows.append({
        "section": "balance", "method": "IPW weights", "target": "largest |SMD| over covariates and pairs",
        "smd_max_before": np.mean([max(x["smd_before"] for x in r["balance"]) for r in runs]),
        "smd_max_after": np.mean([max(x["smd_after"] for x in r["balance"]) for r in runs]),
        "n_reps": len(runs),
    })
    return rows


def _fmt(x) -> str:
    if x is None or x == "" or (isinstance(x, float) and np.isnan(x)):
        return ""
    return f"{x:.4f}" if isinstance(x, (float, np.floating)) else str(x)


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_COLUMNS)
        w.writeheader()
        for row in rows:
            w.writerow({c: _fmt(row.get(c)) for c in SUMMARY_COLUMNS})


def _tex(x: float, digits: int = 3) -> str:
    s = f"{x:.{digits}f}"
    return f"${s}$" if s.startswith("-") else s


def write_tex(rows: list[dict], n_reps: int, n: int, path: Path) -> None:
    label = {f"{a}-{b}": f"{fig.LABEL[a]} vs {fig.LABEL[b]}" for a, b in CONTRASTS}
    lines = [
        f"% DiaCausal causal engine v{__version__} benchmark: {n_reps} synthetic cohorts x {n} patients.",
        "% SYNTHETIC DATA ONLY. Made by the benchmark script (see README); do not edit by hand.",
        "\\begin{tabular}{llrrrr}",
        "\\hline",
        "Contrast & Method & Truth & Bias & RMSE & 95\\% CI coverage \\\\",
        "\\hline",
    ]
    for a, b in CONTRASTS:
        t = f"{a}-{b}"
        for r in (r for r in rows if r["section"] == "average_effect" and r["target"] == t):
            lines.append(
                f"{label[t]} & {r['method']} & {_tex(r['true_value'])} & {_tex(r['bias'])} & "
                f"{_tex(r['rmse'])} & {_tex(r['coverage_95'], 2)} \\\\"
            )
        lines.append("\\hline")
    lines += ["\\end{tabular}", "", "\\vspace{1em}", "",
              "\\begin{tabular}{lrrrr}", "\\hline",
              "Learner & " + " & ".join(f"PEHE {label[f'{a}-{b}']}" for a, b in CONTRASTS) + " & Policy regret \\\\",
              "\\hline"]
    for learner in LEARNERS:
        pehes = [next(r for r in rows if r["section"] == "patient_effect" and r["method"] == learner and r["target"] == f"{a}-{b}")["pehe"] for a, b in CONTRASTS]
        reg = next(r for r in rows if r["section"] == "policy" and r["method"] == learner)["policy_regret"]
        lines.append(f"{learner} & " + " & ".join(_tex(p) for p in pehes) + f" & {_tex(reg)} \\\\")
    lines += ["\\hline", "\\end{tabular}", ""]
    path.write_text("\n".join(lines))


def write_refutation(rows, path: Path) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["check", "contrast", "original_estimate", "original_se", "new_estimate", "new_ci_low",
                    "new_ci_high", "criterion", "passed"])
        for r in rows:
            w.writerow([r.check, r.contrast, _fmt(r.original), _fmt(r.original_se), _fmt(r.new_estimate),
                        _fmt(r.new_ci_low), _fmt(r.new_ci_high), r.criterion, "yes" if r.passed else "NO"])


def write_evalues(aipw_estimates: dict, outcome_sd: float, params, path: Path) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["contrast", "aipw_estimate", "ci_low", "ci_high", "e_value_estimate", "e_value_ci"])
        for a, b in CONTRASTS:
            est = aipw_estimates[f"{a}-{b}"]
            point, ci = e_value(est, outcome_sd, params)
            w.writerow([f"{a}-{b}", _fmt(est.value), _fmt(est.low), _fmt(est.high), _fmt(point), _fmt(ci)])


def run(reps: int, n: int, n_test: int, out: Path, n_boot: int | None = None, seed: int | None = None) -> list[dict]:
    started = time.time()
    params, rules = load_params(), load_rules()
    seed = int(params.get("engine.random_seed") if seed is None else seed)
    n_boot = int(params.get("engine.psm_bootstrap") if n_boot is None else n_boot)
    truth = true_population_effects(params)
    runs = []
    for r in range(reps):
        runs.append(run_once(params, rules, n, n_test, seed + r, n_boot))
        print(f"  repeat {r + 1}/{reps} done ({time.time() - started:.0f} s)", flush=True)
    rows = summarise(runs, truth)
    out.mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(exist_ok=True)
    write_csv(rows, out / "benchmark_summary.csv")
    write_tex(rows, reps, n, out / "results_table.tex")

    first = runs[0]
    fig.overlap(first["e"], first["T"], params.get("engine.overlap_min_propensity"), out / "figures/overlap.png")
    fig.love_plot(first["balance"], params.get("engine.smd_threshold"), out / "figures/love_plot.png")
    ate_summary = {
        m: {
            f"{a}-{b}": (
                np.mean([x["ate"][m][f"{a}-{b}"].value for x in runs]),
                np.mean([x["ate"][m][f"{a}-{b}"].low for x in runs]),
                np.mean([x["ate"][m][f"{a}-{b}"].high for x in runs]),
                next(row["coverage_95"] for row in rows if row["section"] == "average_effect"
                     and row["method"] == m and row["target"] == f"{a}-{b}"),
            )
            for a, b in CONTRASTS
        }
        for m in METHODS
    }
    fig.ate_vs_truth(ate_summary, truth, out / "figures/ate_vs_truth.png")
    true_targets = levels_to_targets(first["true_levels"])
    fig.cate_recovery(first["dr"], true_targets, out / "figures/cate_recovery.png")
    fig.calibration(first["dr"], true_targets, out / "figures/calibration.png")

    # Refutation and sensitivity, on the first repeat's cohort.
    obs = observed_view(generate_cohort(params, n=n, seed=seed))
    X0, T0, Y0 = features(params, obs), treatment_index(obs), obs["y"].to_numpy(float)
    ref_rows = refute(params, X0, T0, Y0, seed)
    write_refutation(ref_rows, out / "refutation.csv")
    write_evalues(runs[0]["ate"]["AIPW"], float(Y0.std(ddof=1)), params, out / "evalues.csv")

    info = {
        "engine_version": __version__,
        "intended_use": INTENDED_USE,
        "data": "synthetic India-calibrated cohort (data/params.yaml); no real patients",
        "reps": reps, "n_patients": n, "n_test_patients": n_test, "base_seed": seed, "psm_bootstrap": n_boot,
        "params_version": params.version, "params_sha": params.fingerprint, "rules_sha": rules.version,
        "true_population_effects": truth,
        "refutation_checks_passed": f"{sum(r.passed for r in ref_rows)} of {len(ref_rows)}",
        "python": platform.python_version(),
        "seconds": round(time.time() - started, 1),
    }
    (out / "run_info.json").write_text(json.dumps(info, indent=2))
    return rows


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true", help="3 repeats x 1,500 patients (about a minute)")
    ap.add_argument("--reps", type=int, default=None)
    ap.add_argument("--n", type=int, default=None, help="patients per cohort")
    ap.add_argument("--out", type=Path, default=ROOT / "results")
    a = ap.parse_args(argv)
    reps = a.reps or (3 if a.quick else 20)
    n = a.n or (1500 if a.quick else 5000)
    n_test = 1000 if a.quick else 2000
    print(f"DiaCausal benchmark: {reps} repeats x {n} patients (synthetic) -> {a.out}")
    rows = run(reps, n, n_test, a.out)
    for r in rows:
        if r["section"] == "average_effect":
            print(f"  {r['method']:9s} {r['target']:13s} bias {r['bias']:+.3f}  RMSE {r['rmse']:.3f}  coverage {r['coverage_95']:.2f}")
    print(f"Saved results to {a.out}")


if __name__ == "__main__":
    main()
