"""The pre-registered stress test: stronger confounding (docs/XAI_PLAN.md section 10). About 3 minutes.

    .venv/bin/python scripts/xai_stress.py                  # results/xai_stress.csv (multipliers 1.0, 1.5, 2.0; 3 replicates x 1,500)
    .venv/bin/python scripts/xai_stress.py --out /tmp/x.csv   # the same, written elsewhere (the tests do this)

The plan was written and committed before this code existed; every row is written whatever it shows.
SYNTHETIC DATA ONLY. Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from diacausal.xai import stress  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=stress.OUT)
    a = ap.parse_args()
    print(f"Stress test: multipliers {stress.MULTIPLIERS}, {stress.REPS} replicates x {stress.N} patients (synthetic) -> {a.out}")
    rows = stress.run(out=a.out)
    for r in rows:
        if r["version"] == "B-A" and r["metric"] in ("regret", "abs_effect_bias") and r["comparison"] in ("all", "SGLT2i-DPP4i"):
            print(f"  x{r['multiplier']}  B-A  {r['metric']:16s} {r['comparison']:13s} {r['mean']:+.4f}")
    print(f"Saved {a.out}")


if __name__ == "__main__":
    main()
