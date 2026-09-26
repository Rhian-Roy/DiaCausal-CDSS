"""Draw the project timeline (Gantt chart) for the mid-sem slides and report.

    .venv/bin/python scripts/make_gantt.py        # writes docs/midsem/gantt.png

Teal = done, amber = in progress, hatched grey = planned. The vertical line marks
Progress Presentation-II (30 Sept 2026). Early phases (July–August) are approximate.
Edit TASKS below when the plan changes, then rerun.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "midsem" / "gantt.png"
DONE, NOW, PLAN = "#00897b", "#c47a00", "#e4e7e6"
INK, MUTED = "#1c2a24", "#56635c"

# (task, start, end, status) — status: done | now | plan
TASKS = [
    ("Topic, proposal and approval", date(2026, 7, 6), date(2026, 7, 31), "done"),
    ("Literature and dataset research", date(2026, 7, 20), date(2026, 9, 10), "done"),
    ("Dataset decision, scope frozen", date(2026, 9, 1), date(2026, 9, 18), "done"),
    ("Requirements and system design", date(2026, 9, 8), date(2026, 9, 25), "done"),
    ("Chat app: sign-in, guards, patient panel", date(2026, 9, 12), date(2026, 9, 22), "done"),
    ("Causal engine v0.3 + benchmark", date(2026, 9, 21), date(2026, 9, 25), "done"),
    ("Website, accounts, Evidence tab", date(2026, 9, 25), date(2026, 9, 27), "done"),
    ("Engine extras, RAG sources and retrieval", date(2026, 9, 27), date(2026, 10, 9), "now"),
    ("RAG explanations, gold set, results frozen", date(2026, 10, 10), date(2026, 10, 16), "plan"),
    ("Clinician vignette review (SUS)", date(2026, 10, 10), date(2026, 10, 23), "plan"),
    ("Integration, RAG evaluation, paper draft", date(2026, 10, 17), date(2026, 10, 23), "plan"),
    ("Final report, paper, viva preparation", date(2026, 10, 24), date(2026, 10, 30), "plan"),
    ("Practical examinations", date(2026, 10, 31), date(2026, 11, 7), "exam"),
    ("Theory examinations", date(2026, 11, 18), date(2026, 11, 30), "exam"),
    ("Final submission, paper submission", date(2026, 12, 1), date(2026, 12, 18), "plan"),
]
MILESTONE = date(2026, 9, 30)


def draw(out: Path = OUT) -> Path:
    fig, ax = plt.subplots(figsize=(12, 6.2), dpi=200)
    for i, (name, start, end, status) in enumerate(TASKS):
        y = len(TASKS) - 1 - i
        width = (end - start).days + 1
        kw = dict(height=0.62, left=mdates.date2num(start), edgecolor="white", linewidth=2)
        if status == "done":
            ax.barh(y, width, color=DONE, **kw)
        elif status == "now":
            ax.barh(y, width, color=NOW, **kw)
        elif status == "exam":
            ax.barh(y, width, color="#f3f4f4", hatch="xx", **{**kw, "edgecolor": "#b5bcb9", "linewidth": 0.8})
        else:
            ax.barh(y, width, color=PLAN, hatch="///", **{**kw, "edgecolor": "#aab2ae", "linewidth": 0.8})
    ax.set_yticks(range(len(TASKS)))
    ax.set_yticklabels([t[0] for t in reversed(TASKS)], fontsize=10, color=INK)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%B"))
    ax.tick_params(axis="x", colors=MUTED, labelsize=10)
    ax.set_xlim(mdates.date2num(date(2026, 7, 1)), mdates.date2num(date(2026, 12, 31)))
    ax.grid(axis="x", color="#e3e7e5", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#c9d0cc")
    ax.tick_params(axis="y", length=0)
    m = mdates.date2num(MILESTONE)
    ax.axvline(m, color=INK, linewidth=1.4, linestyle=(0, (4, 3)))
    ax.text(m + 1.5, len(TASKS) - 0.35, "30 Sept: Progress\nPresentation-II", fontsize=9.5, color=INK, va="top")
    ax.legend(handles=[Patch(color=DONE, label="Done"), Patch(color=NOW, label="In progress"),
                       Patch(facecolor=PLAN, hatch="///", edgecolor="#aab2ae", label="Planned"),
                       Patch(facecolor="#f3f4f4", hatch="xx", edgecolor="#b5bcb9", label="University exams")],
              loc="lower left", frameon=False, fontsize=9.5, ncol=4, bbox_to_anchor=(0, -0.13))
    ax.set_title("DiaCausal project timeline, July–December 2026 (Group 28)", fontsize=13, color=INK,
                 loc="left", pad=12, fontweight="bold")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


if __name__ == "__main__":
    print(f"wrote {draw()}")
