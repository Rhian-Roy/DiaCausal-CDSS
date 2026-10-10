"""Run versions A to D over the 20 synthetic cohorts and write the ablation table (P26; diacausal/xai/ablation.py).

    .venv/bin/python scripts/xai_ablation.py            # 20 replicates x 5,000 patients (about 10 minutes; needs requirements-xai.txt)
    .venv/bin/python scripts/xai_ablation.py --quick    # 3 x 1,500, written next to the full table as *_quick.csv (no figures)

Writes results/xai_ablation.csv (version, metric, comparison, mean, ci_low, ci_high, n_reps), results/xai_ablation_run_info.json,
results/xai/ablation_chart.png (one comparison chart) and results/xai/shap_A_vs_C.png (the side-by-side SHAP charts).
SYNTHETIC DATA ONLY. Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diacausal.xai import ablation  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args(argv)
    if a.quick:
        out, (reps, n, n_test, n_agree) = ablation.OUT.with_name("xai_ablation_quick.csv"), (3, 1500, 1000, 20)
    else:
        out, (reps, n, n_test, n_agree) = ablation.OUT, (20, 5000, 2000, 100)
    print(f"A-D ablation: {reps} replicates x {n} patients (synthetic) -> {out}")
    rows = ablation.run(reps, n, n_test, n_agree, out, figures=not a.quick)
    for r in rows:
        if r["comparison"] in ("all", "SGLT2i-DPP4i") and r["metric"] in ("pehe", "regret", "answered_when_thin", "modifier_precision_at_k", "coverage"):
            print(f"  {r['version']}  {r['metric']:24s} {r['comparison']:13s} {r['mean']:.3f}")
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
