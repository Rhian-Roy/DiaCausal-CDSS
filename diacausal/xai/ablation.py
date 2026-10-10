"""The A-D ablation (docs/XAI_PLAN.md section 6; plan section 7.1; P26): what each layer adds, measured on the same 20 synthetic cohorts.

    A  XAI-only baseline: a gradient-boosted predictor on factual data, explained with TreeSHAP and LIME (diacausal/xai/baseline.py)
    B  the causal engine: cross-fitted AIPW + DR-learner, 95% intervals, overlap abstention, the same safety rules
    C  B + exact SHAP on its own estimate, with intervals and the clear-driver rule (diacausal/xai/cate_shap.py)
    D  C + retrieval and the explanation writer: the drivers steer the search (P26) and the output guards check every draft

Every replicate uses the benchmark's cohorts (train: seed; test: seed + 100000; diacausal/causal_inference/benchmark.py) and the same
safety-rule exclusions in every version. A cell is the mean over replicates with a 95% t-interval. B's numbers are C's and D's too
(C and D explain or describe B's estimate, they do not change it); the table repeats them under C and D so each version's row is
complete. D's retrieval and writing metrics are not per synthetic cohort: they come from the fixed question sets (the 60 gold
questions, the 20 golden questions of the local-model benchmark); `n_reps` is 0 on those rows and the doc says where each comes from.

    python scripts/xai_ablation.py [--quick]   ->  results/xai_ablation.csv, results/xai/ablation_chart.png, results/xai/shap_A_vs_C.png

SYNTHETIC DATA ONLY. SHAP and LIME explain models, not causes. Version A is never shown to a doctor (it lives only in this table and
the Analysis tab's charts).

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import numpy as np

from diacausal.config import ARMS, CONTRASTS, RESULTS_DIR, load_params
from diacausal.xai import truth

OUT = RESULTS_DIR / "xai_ablation.csv"
FIG_DIR = RESULTS_DIR / "xai"
COLUMNS = ["version", "metric", "comparison", "mean", "ci_low", "ci_high", "n_reps"]
COMPARISONS = truth.COMPARISONS
VERSIONS = ("A", "B", "C", "D")
B_METRICS = ("effect_bias", "pehe", "pehe_thin", "pehe_not_thin", "coverage", "pred_rmse", "regret", "best_pick_rate", "abstention_rate",
             "answered_when_thin", "answered_when_thin_pairs")
CHART = [("pehe", "SGLT2i-DPP4i", "Error of the patient-level effect (PEHE), SGLT2i vs DPP-4i", "HbA1c points (lower is better)"),
         ("regret", "all", "Regret: extra HbA1c vs the truly best allowed drug", "HbA1c points (lower is better)"),
         ("answered_when_thin_pairs", "all", "Numbers given where data are thin", "share of thin patient-option pairs (lower is safer)"),
         ("modifier_precision_at_k", "SGLT2i-DPP4i", "Top features are the true modifiers, SGLT2i vs DPP-4i", "precision at k (higher is better)")]


def engine_metrics(params, rules, f, test) -> dict[tuple[str, str], float]:
    """Version B on one replicate: the DR-learner's estimate against the truth, with the engine's own abstention and the same rules."""
    from diacausal.causal_inference.benchmark import safe_matrix
    from diacausal.causal_inference.cohort import features
    from diacausal.causal_inference.metrics import coverage, pehe, policy_regret
    from diacausal.causal_inference.propensity import predict
    from diacausal.xai.baseline import pick

    z = float(params.get("engine.ci_z"))
    Xt = features(params, test)
    pred = f.dr.predict(Xt, z)
    mu = test[[f"mu_true_{a}" for a in ARMS]].to_numpy(float)
    e_true = test[[f"e_true_{a}" for a in ARMS]].to_numpy(float)
    threshold = params.get("engine.overlap_min_propensity")
    thin = e_true.min(axis=1) < threshold
    safe = safe_matrix(rules, test)
    p_hat = predict(f.propensity, Xt)
    width = np.column_stack([pred[a][:, 2] - pred[a][:, 1] for a in ARMS])
    allowed = safe & (p_hat >= threshold) & (width <= params.get("engine.max_interval_width"))  # what the engine answers
    true_effects = truth.true_effect(params, mu)
    m: dict[tuple[str, str], float] = {}
    for c in COMPARISONS:
        est, lo, hi = pred[c][:, 0], pred[c][:, 1], pred[c][:, 2]
        m["effect_bias", c] = float(np.mean(est - true_effects[c]))
        m["pehe", c] = pehe(est, true_effects[c])
        m["pehe_thin", c] = pehe(est[thin], true_effects[c][thin]) if thin.any() else float("nan")
        m["pehe_not_thin", c] = pehe(est[~thin], true_effects[c][~thin])
        m["coverage", c] = coverage(lo, hi, true_effects[c])
    levels = np.column_stack([pred[a][:, 0] for a in ARMS])
    received = test["treatment"].map({a: j for j, a in enumerate(ARMS)}).to_numpy() if "treatment" in test else None
    if received is not None:
        rows = np.arange(len(test))
        m["pred_rmse", "all"] = float(np.sqrt(np.mean((levels[rows, received] - mu[rows, received]) ** 2)))
    m["regret", "all"] = policy_regret(levels, mu, allowed)[0]
    two = allowed.sum(axis=1) >= 2
    m["best_pick_rate", "all"] = float(np.mean(pick(levels, allowed)[two] == pick(mu, allowed)[two])) if two.any() else float("nan")
    m["abstention_rate", "all"] = float(1.0 - (allowed.sum() / max(safe.sum(), 1)))  # of the options the rules leave
    m["answered_when_thin", "all"] = float(allowed.any(axis=1)[thin].mean()) if thin.any() else float("nan")
    # per (patient, option): an option this patient almost never gets in the cohort (TRUE propensity below the threshold) is
    # "thin"; the share of thin options that get a number. A answers every option the rules leave (so its share is 1 by design).
    thin_pairs = safe & (e_true < threshold)
    m["answered_when_thin_pairs", "all"] = float(allowed[thin_pairs].mean()) if thin_pairs.any() else float("nan")
    m["_A_answered_when_thin_pairs", "all"] = 1.0 if thin_pairs.any() else float("nan")
    return m


def evaluate_replicate(params, rules, seed: int, n: int, n_test: int, n_agree: int) -> dict[tuple[str, str, str], float]:
    from diacausal.causal_inference.cohort import generate_cohort
    from diacausal.causal_inference.fitting import fit_all
    from diacausal.xai import baseline, cate_shap_benchmark

    out: dict[tuple[str, str, str], float] = {}
    for (metric, c), v in baseline.evaluate_replicate(params, rules, seed, n, n_test, n_agree).items():
        out["A", metric, c] = v
    f = fit_all(params, generate_cohort(params, n=n, seed=seed), seed)
    test = generate_cohort(params, n=n_test, seed=seed + 100_000)
    b = engine_metrics(params, rules, f, test)
    out["A", "answered_when_thin_pairs", "all"] = b.pop(("_A_answered_when_thin_pairs", "all"))
    c = cate_shap_benchmark.evaluate_replicate(params, rules, seed, n, n_test, fitted=f, test=test)
    for (metric, comp), v in b.items():
        for version in ("B", "C", "D"):  # C and D explain or describe B's estimate; they never change it
            out[version, metric, comp] = v
    for (metric, comp), v in c.items():
        for version in ("C", "D"):
            out[version, metric, comp] = v
    return out


def retrieval_and_writing_rows() -> list[dict]:
    """Version D's metrics that do not come from the synthetic cohorts (n_reps 0): the committed retrieval evaluation (60 gold
    questions, template writer) and the local-model benchmark (20 golden questions, candidate_a). The driver-to-passage hit rate needs
    eval/xai_driver_evidence.csv, a table Members B and D still have to write and review: until then it is left empty, never guessed."""
    rows = []
    rag = {r["metric"]: r["value"] for r in csv.DictReader((RESULTS_DIR / "rag_eval_summary.csv").open())}
    rows.append(_row("D", "citation_precision", "all", float(rag["citation_precision"])))
    rows.append(_row("D", "retrieval_recall_at_5", "all", float(rag["recall_at_5"])))
    bench = {r["model_key"]: r for r in csv.DictReader((RESULTS_DIR / "llm" / "bench_summary.csv").open())}
    if "candidate_a" in bench:
        a = bench["candidate_a"]
        rows.append(_row("D", "number_match_pass", "all", float(a["number_match_pct"]) / 100))
        rows.append(_row("D", "fallback_rate", "all", float(a["fallback_pct"]) / 100))
    rows.append(_row("D", "driver_passage_hit_rate", "all", float("nan")))
    return rows


def _row(version, metric, comparison, mean, lo=float("nan"), hi=float("nan"), n=0) -> dict:
    return {"version": version, "metric": metric, "comparison": comparison, "mean": mean, "ci_low": lo, "ci_high": hi, "n_reps": n}


def aggregate(replicates: list[dict]) -> list[dict]:
    from diacausal.xai.baseline import mean_ci

    keys = sorted({k for r in replicates for k in r}, key=lambda k: (VERSIONS.index(k[0]), k[1], k[2]))
    rows = [_row(v, m, c, *mean_ci([r.get((v, m, c), float("nan")) for r in replicates])) for v, m, c in keys]
    return rows + retrieval_and_writing_rows()


def _fmt(x) -> str:
    if isinstance(x, float):
        return "" if np.isnan(x) else f"{x:.6g}"
    return str(x)


def write_csv(rows: list[dict], path: Path = OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: _fmt(r[k]) for k in COLUMNS})


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def comparison_chart(rows: list[dict], path: Path) -> None:
    """One chart: four key metrics, versions A to D side by side, each with its 95% interval (synthetic benchmark)."""
    plt = _plt()
    got = {(r["version"], r["metric"], r["comparison"]): r for r in rows}
    fig, axes = plt.subplots(1, len(CHART), figsize=(4.2 * len(CHART), 3.8))
    for ax, (metric, comp, title, unit) in zip(axes, CHART):
        means, errs, labels = [], [[], []], []
        for v in VERSIONS:
            r = got.get((v, metric, comp))
            mean = float(r["mean"]) if r and not np.isnan(float(r["mean"])) else float("nan")
            lo = float(r["ci_low"]) if r and not np.isnan(float(r["ci_low"])) else mean
            hi = float(r["ci_high"]) if r and not np.isnan(float(r["ci_high"])) else mean
            means.append(mean)
            errs[0].append(max(0.0, mean - lo) if not np.isnan(mean) else 0.0)
            errs[1].append(max(0.0, hi - mean) if not np.isnan(mean) else 0.0)
            labels.append(v if not np.isnan(mean) else f"{v}\n(n/a)")
        ax.bar(range(len(VERSIONS)), [0 if np.isnan(x) else x for x in means], yerr=errs, capsize=4, color=["#9FB0A6", "#0E5049", "#0E5049", "#0E5049"])
        ax.set_xticks(range(len(VERSIONS)), labels)
        ax.set_title(title, fontsize=9)
        ax.set_ylabel(unit, fontsize=8)
    fig.suptitle("A-D ablation, 20 synthetic cohorts (mean with 95% interval). SYNTHETIC BENCHMARK.", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def shap_a_vs_c_chart(path: Path, comparison: str = "SGLT2i-DPP4i") -> list[dict]:
    """Side by side: version A's global mean |TreeSHAP| (results/xai/shap_A.csv) and version C's mean |exact SHAP| of the engine's
    estimate over its reference cohort, for one comparison; the true modifiers are marked. Returns the numbers drawn."""
    from diacausal.causal_inference.recommend import Engine
    from diacausal.xai.cate_shap_benchmark import explain_matrix

    params = load_params()
    engine = Engine()
    names = engine.adjustment
    phi, _, _, _ = explain_matrix(engine.fitted.dr, engine.fitted.X, comparison, engine.z)
    c_imp = {f: float(np.abs(phi[:, j]).mean()) for j, f in enumerate(names)}
    a_imp = {r["feature"]: float(r["mean_abs_phi"]) for r in csv.DictReader((FIG_DIR / "shap_A.csv").open())
             if r["scope"] == "global" and r["comparison"] == comparison and r["feature"] in names}
    true = set(truth.modifiers(params)[comparison])
    plt = _plt()
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    order = sorted(names, key=lambda f: -c_imp[f])
    for ax, (label, imp) in zip(axes, [("A: XAI-only model (TreeSHAP)", a_imp), ("C: causal estimate (exact SHAP)", c_imp)]):
        vals = [imp.get(f, 0.0) for f in order]
        ax.barh(range(len(order)), vals, color=["#0E5049" if f in true else "#9FB0A6" for f in order])
        ax.set_yticks(range(len(order)), [f + (" *" if f in true else "") for f in order], fontsize=8)
        ax.set_title(label, fontsize=10)
        ax.set_xlabel("mean |SHAP|, HbA1c points", fontsize=8)
    axes[0].invert_yaxis()  # once: the two panels share the axis, so the largest bar is on top in both
    fig.suptitle(f"{comparison.replace('-', ' vs ')}: which features each version credits (* = true effect modifier). SYNTHETIC; "
                 "SHAP explains a model, not a cause.", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return [{"feature": f, "A": a_imp.get(f, 0.0), "C": c_imp[f], "true_modifier": f in true} for f in order]


def run(reps: int, n: int, n_test: int, n_agree: int, out: Path = OUT, figures: bool = True) -> list[dict]:
    from diacausal.guards.rules_loader import load_rules

    started = time.time()
    params, rules = load_params(), load_rules()
    seed = int(params.get("engine.random_seed"))
    replicates = []
    for r in range(reps):
        replicates.append(evaluate_replicate(params, rules, seed + r, n, n_test, n_agree))
        print(f"  replicate {r + 1}/{reps} done ({time.time() - started:.0f} s)", flush=True)
    rows = aggregate(replicates)
    write_csv(rows, out)
    info = {"reps": reps, "n_patients": n, "n_test_patients": n_test, "shap_lime_patients": n_agree, "seed": seed,
            "params_sha": params.fingerprint, "rules_sha": rules.version, "seconds": round(time.time() - started, 1),
            "note": "synthetic benchmark; B's numbers repeat under C and D; D's retrieval and writing rows have n_reps 0 (fixed question sets)"}
    if figures:
        FIG_DIR.mkdir(parents=True, exist_ok=True)
        comparison_chart(rows, FIG_DIR / "ablation_chart.png")
        info["shap_A_vs_C"] = shap_a_vs_c_chart(FIG_DIR / "shap_A_vs_C.png")
    out.with_name(out.stem + "_run_info.json").write_text(json.dumps(info, indent=1))
    return rows
