"""The pre-registered stress test: stronger confounding (docs/XAI_PLAN.md section 10, written BEFORE any run).

The naive comparison (0), version A and version B on the ablation's quick-mode cohorts (3 replicates, 1,500 training and 1,000 test
patients, seeds 7, 8, 9) at `generator.assignment.confounding_multiplier` 1.0, 1.5 and 2.0, with exactly the ablation's functions
(`ablation.naive_metrics`, `ablation.engine_metrics`, `baseline.evaluate_replicate`). Nothing else changes: the outcome model, the
safety rules, every engine setting, the learners and the seeds are the committed ones. At 1.0 the 0, A and B rows equal
results/xai_ablation_quick.csv (a test checks it).

    python scripts/xai_stress.py     ->  results/xai_stress.csv  (multiplier, version, metric, comparison, mean, ci_low, ci_high, n_reps)

Every row is written whatever it shows. SYNTHETIC DATA ONLY. Research prototype for clinician evaluation; not a marketed medical
device; not for unsupervised clinical use.
"""

from __future__ import annotations

import copy
import csv
import dataclasses
import time
from pathlib import Path

import numpy as np

from diacausal.config import RESULTS_DIR, load_params
from diacausal.xai import ablation, baseline

OUT = RESULTS_DIR / "xai_stress.csv"
MULTIPLIERS = (1.0, 1.5, 2.0)
REPS, N, N_TEST = 3, 1500, 1000  # the ablation's quick mode (scripts/xai_ablation.py --quick)
COLUMNS = ["multiplier", "version", "metric", "comparison", "mean", "ci_low", "ci_high", "n_reps"]
PAIRED = (*ablation.PAIRED, ("answered_when_thin_pairs", "all"), *(("abs_effect_bias", c) for c in ablation.COMPARISONS))


def with_multiplier(params, value: float):
    """A copy of the params with only `generator.assignment.confounding_multiplier` changed."""
    raw = copy.deepcopy(params.raw)
    raw["generator"]["assignment"]["confounding_multiplier"]["value"] = float(value)
    return dataclasses.replace(params, raw=raw)


def evaluate_replicate(params, rules, seed: int, n: int, n_test: int) -> dict[tuple[str, str, str], float]:
    """0, A and B on one replicate of the same cohorts the ablation uses, plus the cohort's thin share."""
    from diacausal.causal_inference.cohort import generate_cohort
    from diacausal.causal_inference.fitting import fit_all

    out: dict[tuple[str, str, str], float] = {}
    for (metric, c), v in baseline.evaluate_replicate(params, rules, seed, n, n_test, 0, with_lime=False).items():
        if metric == "thin_share":
            out["cohort", metric, c] = v
        else:
            out["A", metric, c] = v
    f = fit_all(params, generate_cohort(params, n=n, seed=seed), seed)
    test = generate_cohort(params, n=n_test, seed=seed + 100_000)
    b = ablation.engine_metrics(params, rules, f, test)
    out["A", "answered_when_thin_pairs", "all"] = b.pop(("_A_answered_when_thin_pairs", "all"))
    for (metric, c), v in b.items():
        out["B", metric, c] = v
    for (metric, c), v in ablation.naive_metrics(params, rules, f, test).items():
        out["0", metric, c] = v
    for version in ("0", "A", "B"):  # the absolute bias of the average effect: the quantity the paired difference is taken on
        for c in ablation.COMPARISONS:
            if (version, "effect_bias", c) in out:
                out[version, "abs_effect_bias", c] = abs(out[version, "effect_bias", c])
    for metric, c in PAIRED:
        if ("A", metric, c) in out and ("B", metric, c) in out:
            out["B-A", metric, c] = out["B", metric, c] - out["A", metric, c]
    return out


def aggregate(multiplier: float, replicates: list[dict]) -> list[dict]:
    order = ("cohort", "0", "A", "B", "B-A")
    keys = sorted({k for r in replicates for k in r}, key=lambda k: (order.index(k[0]), k[1], k[2]))
    rows = []
    for v, m, c in keys:
        mean, lo, hi, n = baseline.mean_ci([r.get((v, m, c), float("nan")) for r in replicates])
        rows.append({"multiplier": multiplier, "version": v, "metric": m, "comparison": c, "mean": mean, "ci_low": lo, "ci_high": hi, "n_reps": n})
    return rows


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


def run(multipliers=MULTIPLIERS, reps: int = REPS, n: int = N, n_test: int = N_TEST, out: Path = OUT) -> list[dict]:
    from diacausal.guards.rules_loader import load_rules

    started = time.time()
    base, rules = load_params(), load_rules()
    seed = int(base.get("engine.random_seed"))
    rows: list[dict] = []
    for m in multipliers:
        params = with_multiplier(base, m)
        replicates = []
        for r in range(reps):
            replicates.append(evaluate_replicate(params, rules, seed + r, n, n_test))
            print(f"  multiplier {m}: replicate {r + 1}/{reps} done ({time.time() - started:.0f} s)", flush=True)
        rows += aggregate(m, replicates)
    write_csv(rows, out)
    return rows
