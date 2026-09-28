"""Does the synthetic cohort look like real Indian adults with diabetes? (a plausibility check)

    .venv/bin/python scripts/fetch_nmb2017.py      # once: real reference data (CC0)
    .venv/bin/python scripts/compare_cohort.py     # writes docs/midsem/data/real_vs_synthetic.{png,csv}

Compares age, BMI, HbA1c and sex in DiaCausal's synthetic cohort (seed 0, observed columns only)
with NMB-2017 adults who said they have diabetes, and with the subset whose HbA1c is at or above
the cohort's inclusion threshold (params: generator.inclusion.hba1c_min), the closest real match to
"on metformin, not at target". It is a check on realism, not a validation of drug effects: NMB-2017
records no drug and no follow-up HbA1c, so nothing here is used to fit or grade the engine.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from diacausal_engine.cohort import generate_cohort, observed_view  # noqa: E402
from diacausal_engine.config import load_params  # noqa: E402

REAL = ROOT / "data" / "reference" / "nmb2017.csv"
OUT = ROOT / "docs" / "midsem" / "data"
SYN, REAL_C = "#00897b", "#c47a00"
INK, MUTED, GRID = "#1c2a24", "#56635c", "#e4e7e6"


def real_groups(hba1c_min: float) -> dict[str, pd.DataFrame]:
    df = pd.read_csv(REAL)
    df["female"] = (df["gender"] == "Female").astype(int)
    ok = df["height_cm"].between(120, 210) & df["weight_kg"].between(25, 200)
    df["bmi"] = np.where(ok, df["weight_kg"] / (df["height_cm"] / 100) ** 2, np.nan)
    dia = df[df["diabetes_self_declared"] == "Diabetic"]
    return {"NMB-2017: said they have diabetes": dia,
            f"NMB-2017: diabetes and HbA1c >= {hba1c_min:g}%": dia[dia["hba1c"] >= hba1c_min]}


def summary(name: str, df: pd.DataFrame) -> list[dict]:
    rows = [{"group": name, "variable": "n", "value": f"{len(df)}"}]
    for v, unit in (("age", "years"), ("bmi", "kg/m2"), ("hba1c", "%")):
        s = df[v].dropna()
        rows.append({"group": name, "variable": f"{v} ({unit})",
                     "value": f"mean {s.mean():.1f}, SD {s.std():.1f}, median {s.median():.1f} (IQR {s.quantile(.25):.1f}-{s.quantile(.75):.1f})"})
    rows.append({"group": name, "variable": "female", "value": f"{100 * df['female'].mean():.0f}%"})
    rows.append({"group": name, "variable": "BMI >= 25 (Asian-Indian obese)", "value": f"{100 * (df['bmi'].dropna() >= 25).mean():.0f}%"})
    return rows


def main() -> None:
    if not REAL.exists():
        sys.exit("run scripts/fetch_nmb2017.py first")
    params = load_params()
    hba1c_min = params.get("generator.inclusion.hba1c_min")
    syn = observed_view(generate_cohort(params, seed=0))
    groups = {"DiaCausal synthetic cohort (seed 0)": syn, **real_groups(hba1c_min)}
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([r for n, g in groups.items() for r in summary(n, g)]).to_csv(OUT / "real_vs_synthetic.csv", index=False)

    real = list(groups.values())[2]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), dpi=200)
    for ax, (v, label, bins) in zip(axes, (("age", "Age (years)", np.arange(20, 91, 5)),
                                           ("bmi", "BMI (kg/m²)", np.arange(14, 46, 1.5)),
                                           ("hba1c", "HbA1c (%)", np.arange(hba1c_min, 14.01, 0.4)))):
        for df, colour, name in ((syn, SYN, "Synthetic"), (real, REAL_C, "Real (NMB-2017)")):
            ax.hist(df[v].dropna(), bins=bins, density=True, histtype="step", linewidth=2, color=colour, label=name)
        ax.set_title(label, color=INK, fontsize=11, loc="left")
        ax.set_yticks([])
        ax.tick_params(colors=MUTED, labelsize=9)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
    axes[0].legend(frameon=False, fontsize=9, labelcolor=INK, loc="upper left")
    if "bmi" in syn:
        axes[1].axvline(25, color=MUTED, linewidth=1, linestyle=":")
        axes[1].text(33, axes[1].get_ylim()[1] * 0.8, "obese ≥ 25\n(Asian-Indian)", fontsize=8, color=MUTED)
    fig.suptitle(f"Synthetic cohort vs real Indian adults with diabetes and HbA1c ≥ {hba1c_min:g}% (n = {len(real)})",
                 color=INK, fontsize=12, x=0.01, ha="left")
    fig.text(0.01, -0.02, "Real: NMB-2017, Nagarathna et al. 2020, Mendeley Data doi:10.17632/twp8xw6p25.1 (CC0). "
             "It has no drug or follow-up data, so it checks realism only.", fontsize=8, color=MUTED)
    fig.tight_layout()
    fig.savefig(OUT / "real_vs_synthetic.png", bbox_inches="tight", facecolor="white")
    print((OUT / "real_vs_synthetic.csv").read_text())


if __name__ == "__main__":
    main()
