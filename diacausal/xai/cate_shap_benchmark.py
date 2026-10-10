"""Version C's benchmark (docs/XAI_PLAN.md section 6; P25): score the exact SHAP drivers of the causal estimate against the generator's
TRUE effect modifiers, over the same 20 synthetic replicates as the engine's benchmark.

    python -m diacausal.xai.cate_shap_benchmark_benchmark [--quick]
    -> results/xai/causal_shap_metrics.csv   (version, metric, comparison, mean, ci_low, ci_high, n_reps)
       results/xai/causal_shap_presets.csv   (every contribution of the three demo patients, and which the card shows)
       results/xai/causal_shap_run_info.json

Kept apart from diacausal/xai/cate_shap.py on purpose: this file borrows version A's metric helpers (top_k, precision_at_k,
spearman, mean_ci, the presets), and the pipeline imports cate_shap, so the pipeline never loads version A (a test checks).

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

from diacausal.config import ARMS, CONTRASTS, RESULTS_DIR, load_params
from diacausal.causal_inference.estimators import TARGETS
from diacausal.xai import truth
from diacausal.xai.baseline import PRESETS, mean_ci, precision_at_k, spearman, top_k
from diacausal.xai.cate_shap import COMPARISONS, drivers, explain_effect, max_drivers

OUT_DIR = RESULTS_DIR / "xai"
METRIC_COLUMNS = ["version", "metric", "comparison", "mean", "ci_low", "ci_high", "n_reps"]
PRESET_COLUMNS = ["preset", "comparison", "base", "estimate", "feature", "value", "mean", "slope_per_unit", "phi", "ci_low", "ci_high",
                  "clear", "shown"]


def explain_matrix(dr, X: np.ndarray, target: str, z: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Vectorised explain_effect for many patients: (phi (n, p), se (n, p), base, estimate (n,)) and the clear flags (p,)."""
    k = TARGETS.index(target)
    C = (np.atleast_2d(X) - dr.mean_) / dr.scale_
    beta = dr.beta_[:, k]
    se_coef = np.sqrt(np.clip(np.diag(dr.cov_[k])[1:], 0.0, None))
    phi = C * beta[1:]
    estimate = beta[0] + C @ beta[1:]
    return phi, np.abs(C) * se_coef, estimate, np.abs(beta[1:]) > z * se_coef


def evaluate_replicate(params, rules, seed: int, n: int, n_test: int) -> dict:
    """The benchmark's replicate `seed` (train cohort seed, test cohort seed + 100000): fit the engine's models, explain every test
    patient's three comparisons, and score the explanations against the generator's TRUE effect modifiers."""
    from diacausal.causal_inference.benchmark import safe_matrix
    from diacausal.causal_inference.cohort import features, generate_cohort
    from diacausal.causal_inference.dag import load_dag
    from diacausal.causal_inference.fitting import fit_all

    z = float(params.get("engine.ci_z"))
    names = load_dag(params).adjustment_set
    limit = max_drivers(params)
    cohort = generate_cohort(params, n=n, seed=seed)
    f = fit_all(params, cohort, seed)
    test = generate_cohort(params, n=n_test, seed=seed + 100_000)
    Xt = features(params, test)
    dr_pred = f.dr.predict(Xt, z)
    safe = safe_matrix(rules, test)
    sd = {name: float(Xt[:, j].std()) for j, name in enumerate(names)}
    importance_truth = truth.true_importance(params, sd)
    modifiers = truth.modifiers(params)
    slopes_truth = truth.true_slopes(params)
    m: dict[tuple[str, str], float] = {}
    for (a, b), comparison in zip(CONTRASTS, COMPARISONS):
        phi, se, estimate, clear = explain_matrix(f.dr, Xt, comparison, z)
        k = TARGETS.index(comparison)
        base = f.dr.beta_[0, k]
        m["additivity_max_error", comparison] = float(np.max(np.abs(base + phi.sum(axis=1) - dr_pred[comparison][:, 0])))
        mean_abs = {name: float(np.abs(phi[:, j]).mean()) for j, name in enumerate(names)}
        true_set = modifiers[comparison]
        m["modifier_precision_at_k", comparison] = precision_at_k(mean_abs, true_set)
        m["modifier_spearman", comparison] = spearman([mean_abs[x] for x in names], [importance_truth[comparison][x] for x in names])
        top3 = {names[i] for i in top_k([mean_abs[x] for x in names], 3)}
        m["modifier_top3_overlap", comparison] = len(top3 & set(true_set)) / min(3, len(true_set)) if true_set else float("nan")
        # the card rule, on test patients for whom the rules leave both options
        both = safe[:, ARMS.index(a)] & safe[:, ARMS.index(b)]
        shown_total = false_total = 0
        recall = []
        order = np.argsort(-np.abs(phi), axis=1, kind="stable")
        for i in np.flatnonzero(both):
            shown = [names[j] for j in order[i] if clear[j] and phi[i, j] != 0.0][:limit]
            shown_total += len(shown)
            false_total += sum(s not in true_set for s in shown)
            if true_set:
                recall.append(len(set(shown) & set(true_set)) / len(true_set))
        m["false_driver_rate", comparison] = false_total / shown_total if shown_total else float("nan")
        m["driver_recall", comparison] = float(np.mean(recall)) if recall else float("nan")
        m["patients_with_no_clear_driver", comparison] = float(np.mean([not any(clear[j] and phi[i, j] != 0.0 for j in range(len(names)))
                                                                        for i in np.flatnonzero(both)])) if both.any() else float("nan")
        # does each per-unit slope's 95% interval contain the TRUE slope? (modifiers and non-modifiers alike)
        se_coef = np.sqrt(np.clip(np.diag(f.dr.cov_[k])[1:], 0.0, None))
        slope, slope_se = f.dr.beta_[1:, k] / f.dr.scale_, se_coef / f.dr.scale_
        hit = [abs(slope[j] - slopes_truth[comparison][name]) <= z * slope_se[j] for j, name in enumerate(names)]
        m["slope_interval_coverage", comparison] = float(np.mean(hit))
        m["clear_set_equals_true_modifiers", comparison] = float({names[j] for j in np.flatnonzero(clear)} == set(true_set))
    return m


def aggregate(replicates: list[dict]) -> list[dict]:
    keys = sorted({key for r in replicates for key in r}, key=lambda kc: (kc[0], kc[1]))
    rows = []
    for metric, comparison in keys:
        mean, lo, hi, n = mean_ci([r.get((metric, comparison), float("nan")) for r in replicates])
        rows.append({"version": "C", "metric": metric, "comparison": comparison, "mean": mean, "ci_low": lo, "ci_high": hi, "n_reps": n})
    # exact SHAP has no randomness: LIME-style instability does not exist for version C (plan 7.1); stated, not measured
    rows.append({"version": "C", "metric": "explanation_is_deterministic", "comparison": "all", "mean": 1.0, "ci_low": float("nan"),
                 "ci_high": float("nan"), "n_reps": len(replicates)})
    return rows


def presets_report(engine) -> list[dict]:
    """The three demo patients, with the engine's own fitted model: every contribution of every comparison, and which the card shows."""
    from diacausal.causal_inference.schemas import PatientIn

    limit = max_drivers(engine.params)
    rows = []
    for name, raw in PRESETS.items():
        x = engine.feature_vector(PatientIn(**raw))
        for comparison in COMPARISONS:
            e = explain_effect(engine.fitted.dr, x, comparison, engine.z, engine.adjustment)
            shown = {c.feature for c in drivers(e, limit)}
            for c in e.contributions:
                rows.append({"preset": name, "comparison": comparison, "base": e.base, "estimate": e.estimate, "feature": c.feature,
                             "value": c.value, "mean": c.mean, "slope_per_unit": c.slope_per_unit, "phi": c.phi, "ci_low": c.ci_low,
                             "ci_high": c.ci_high, "clear": int(c.clear), "shown": int(c.feature in shown)})
    return rows


def _fmt(x) -> str:
    if isinstance(x, float):
        return "" if np.isnan(x) else f"{x:.6g}"
    return str(x)


def write_csv(rows: list[dict], columns: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        for r in rows:
            w.writerow({k: _fmt(r[k]) for k in columns})


def run(reps: int, n: int, n_test: int, out: Path = OUT_DIR) -> list[dict]:
    from diacausal.causal_inference.recommend import Engine
    from diacausal.guards.rules_loader import load_rules

    started = time.time()
    params, rules = load_params(), load_rules()
    seed = int(params.get("engine.random_seed"))
    replicates = []
    for r in range(reps):
        replicates.append(evaluate_replicate(params, rules, seed + r, n, n_test))
        print(f"  replicate {r + 1}/{reps} done ({time.time() - started:.0f} s)", flush=True)
    rows = aggregate(replicates)
    write_csv(rows, METRIC_COLUMNS, out / "causal_shap_metrics.csv")
    write_csv(presets_report(Engine()), PRESET_COLUMNS, out / "causal_shap_presets.csv")
    info = {"version": "C (exact SHAP of the DR-learner's linear final stage)", "reps": reps, "n_patients": n, "n_test_patients": n_test,
            "seed": seed, "max_drivers": max_drivers(params), "params_sha": params.fingerprint, "rules_sha": rules.version,
            "seconds": round(time.time() - started, 1), "note": "synthetic benchmark; drivers describe the estimate, never a cause"}
    (out / "causal_shap_run_info.json").write_text(json.dumps(info, indent=1))
    return rows


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true", help="3 replicates x 1,500 patients")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    a = ap.parse_args(argv)
    reps, n, n_test = (3, 1500, 1000) if a.quick else (20, 5000, 2000)
    print(f"Version C (exact SHAP on the causal estimate): {reps} replicates x {n} patients (synthetic) -> {a.out}")
    rows = run(reps, n, n_test, a.out)
    for r in rows:
        if r["metric"] in ("modifier_top3_overlap", "false_driver_rate", "driver_recall", "slope_interval_coverage"):
            print(f"  {r['metric']:26s} {r['comparison']:13s} {r['mean']:.3f}")
    print(f"Saved results to {a.out}")


if __name__ == "__main__":
    main()
