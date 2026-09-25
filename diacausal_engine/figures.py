"""The five benchmark figures (matplotlib, saved as PNG for the slides and the report).

Colours: the three options always wear the same hue (blue = SGLT2i, orange = DPP-4i,
aqua = sulfonylurea); the truth is drawn in ink; "before" is grey. No green means
"recommended" anywhere — these are method-accuracy plots, not advice.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from diacausal_engine import ARMS, CONTRASTS  # noqa: E402

ARM_COLOUR = {"SGLT2i": "#2a78d6", "DPP4i": "#eb6834", "SU": "#1baf7a"}
METHOD_COLOUR = {"naive": "#8a8984", "IPW": "#2a78d6", "matching": "#eb6834", "AIPW": "#1baf7a"}
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
LABEL = {"SGLT2i": "SGLT2i", "DPP4i": "DPP-4i", "SU": "Sulfonylurea"}
FOOT = "Synthetic India-calibrated cohort; HbA1c change in percentage points. Research prototype — not for clinical use."


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": INK,
            "axes.titlecolor": INK,
            "axes.titleweight": "bold",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "font.size": 10,
            "legend.frameon": False,
        }
    )


def _save(fig, path: Path) -> None:
    fig.text(0.01, -0.02, FOOT, fontsize=7.5, color=MUTED, ha="left", va="top")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def contrast_label(target: str) -> str:
    a, b = target.split("-")
    return f"{LABEL[a]} vs {LABEL[b]}"


def overlap(e: np.ndarray, T: np.ndarray, threshold: float, path: Path) -> None:
    """Propensity for each option, split by the option actually received."""
    _style()
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), sharey=True)
    bins = np.linspace(0, 1, 41)
    for j, (ax, arm) in enumerate(zip(axes, ARMS)):
        for k, got in enumerate(ARMS):
            ax.hist(e[T == k, j], bins=bins, density=True, histtype="step", linewidth=2,
                    color=ARM_COLOUR[got], label=f"received {LABEL[got]}")
        ax.axvline(threshold, color=INK, linestyle="--", linewidth=1.2)
        ax.text(threshold + 0.015, 0.97, f"{threshold:g} (below = insufficient evidence)", rotation=90,
                fontsize=8, color=INK, va="top", transform=ax.get_xaxis_transform())
        ax.set_title(f"P(receive {LABEL[arm]})")
        ax.set_xlabel("cross-fitted propensity score")
    axes[0].set_ylabel("density")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=3, fontsize=8, bbox_to_anchor=(1.0, 1.05))
    fig.suptitle("Overlap: how likely each patient was to get each option", x=0.01, y=1.04, ha="left", fontweight="bold")
    _save(fig, path)


def love_plot(rows: list[dict], threshold: float, path: Path) -> None:
    _style()
    rows = sorted(rows, key=lambda r: r["smd_before"])
    y = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(7, 0.35 * len(rows) + 1.6))
    ax.hlines(y, [r["smd_after"] for r in rows], [r["smd_before"] for r in rows], color=GRID, linewidth=2)
    ax.scatter([r["smd_before"] for r in rows], y, s=60, facecolor=SURFACE, edgecolor=MUTED, linewidth=2,
               label="before weighting", zorder=3)
    ax.scatter([r["smd_after"] for r in rows], y, s=60, color=ARM_COLOUR["SGLT2i"], edgecolor=SURFACE,
               linewidth=2, label="after IPW weighting", zorder=4)
    ax.axvline(threshold, color=INK, linestyle="--", linewidth=1.2)
    ax.text(threshold, -0.9, f" {threshold:g} = balanced", fontsize=8, color=INK, va="center")
    ax.set_ylim(-1.3, len(rows) - 0.5)
    ax.set_yticks(y, [r["covariate"] for r in rows])
    ax.set_xlabel("largest |standardised mean difference| across the three pairs of options")
    ax.set_title("Covariate balance before and after weighting", loc="left")
    ax.legend(loc="lower right", fontsize=8)
    _save(fig, path)


def ate_vs_truth(summary: dict, truth: dict, path: Path) -> None:
    """summary[method][target] = (mean estimate, mean low, mean high, coverage)."""
    _style()
    methods = list(summary)
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), sharey=True)
    for ax, (a, b) in zip(axes, CONTRASTS):
        t = f"{a}-{b}"
        for i, m in enumerate(methods):
            est, lo, hi, cov = summary[m][t]
            ax.errorbar(est, i, xerr=[[est - lo], [hi - est]], fmt="o", markersize=8, capsize=4, linewidth=2,
                        color=METHOD_COLOUR.get(m, INK))
            ax.text(est, i + 0.22, f"{est:+.3f}   coverage {cov:.0%}", ha="center", va="bottom", fontsize=8, color=MUTED)
        ax.axvline(truth[t], color=INK, linewidth=1.5)
        ax.text(truth[t], len(methods) - 0.35, f" truth {truth[t]:+.3f}", fontsize=8, color=INK)
        ax.set_title(contrast_label(t))
        ax.set_xlabel("difference in 6-month HbA1c change")
        ax.set_ylim(-0.6, len(methods) - 0.1)
    axes[0].set_yticks(range(len(methods)), methods)
    fig.suptitle("Average effect: estimate and 95% CI (averaged over repeats) vs the true value",
                 x=0.01, y=1.04, ha="left", fontweight="bold")
    _save(fig, path)


def cate_recovery(pred: dict, truth: dict, path: Path) -> None:
    """pred[target] = (n, 3) [estimate, low, high]; truth[target] = (n,)."""
    _style()
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, (a, b) in zip(axes, CONTRASTS):
        t = f"{a}-{b}"
        x, y = truth[t], pred[t][:, 0]
        ax.scatter(x, y, s=10, alpha=0.35, color=ARM_COLOUR[a], edgecolor="none")
        lim = [min(x.min(), y.min()), max(x.max(), y.max())]
        ax.plot(lim, lim, color=INK, linewidth=1.2, linestyle="--")
        pehe = float(np.sqrt(np.mean((y - x) ** 2)))
        ax.set_title(f"{contrast_label(t)}\nPEHE {pehe:.3f}")
        ax.set_xlabel("true patient-level effect")
    axes[0].set_ylabel("DR-learner estimate")
    fig.suptitle("Patient-level effects: DR-learner estimate vs truth (fresh test patients)",
                 x=0.01, y=1.04, ha="left", fontweight="bold")
    _save(fig, path)


def calibration(pred: dict, truth: dict, path: Path, bins: int = 10) -> None:
    """Mean predicted vs mean true effect within deciles of the prediction."""
    _style()
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, (a, b) in zip(axes, CONTRASTS):
        t = f"{a}-{b}"
        p, tr = pred[t][:, 0], truth[t]
        edges = np.quantile(p, np.linspace(0, 1, bins + 1))
        idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, bins - 1)
        mp = [p[idx == k].mean() for k in range(bins)]
        mt = [tr[idx == k].mean() for k in range(bins)]
        lim = [min(mp + mt), max(mp + mt)]
        ax.plot(lim, lim, color=INK, linewidth=1.2, linestyle="--", label="perfect calibration")
        ax.plot(mp, mt, "o-", color=ARM_COLOUR[a], markersize=8, linewidth=2, label="DR-learner deciles")
        ax.set_title(contrast_label(t))
        ax.set_xlabel("mean predicted effect in decile")
    axes[0].set_ylabel("mean true effect in decile")
    axes[0].legend(loc="upper left", fontsize=8)
    fig.suptitle("Calibration of patient-level effects by decile", x=0.01, y=1.04, ha="left", fontweight="bold")
    _save(fig, path)
