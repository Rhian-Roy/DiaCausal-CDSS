"""Draw the Gantt chart and the timeline chart exactly as the department's Project Interaction Sheet.

    .venv/bin/python scripts/make_gantt.py     # writes docs/midsem/gantt.png, docs/midsem/timeline.png
                                               # and copies both into report/figures/

Only the rows on the interaction sheet (Second Half of 2026 and First Half of 2027) appear, in
its own words and on its own dates: weeks 0-10, Synopsis Presentations I and II, guide evaluation,
the final synopsis presentation, December (100% implementation, research paper), January and
February 2027. Each bar is the sheet's week (ending on the sheet's date). The implementation rows
(25 / 40 / 60 / 80 / 100%) also say what each covers and, where we are ahead of the sheet, the
date it was actually met or our target date, as the sheet asks for implementation in four sections.

Colours: pine = done (signed or met early), amber = today, hatched grey = planned.
Edit ROWS / TIMELINE when the plan changes, then rerun.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "midsem"
DONE, NOW, PLAN = "#00897b", "#c47a00", "#e4e7e6"
INK, MUTED, GRID = "#1c2a24", "#56635c", "#e3e7e5"
TODAY = date(2026, 9, 30)  # Synopsis Presentation-II

# (label, start, end, status, note) — status: done | today | plan. Bars = the sheet's weeks.
ROWS = [
    ("Week 0 · Topic Finalization", date(2026, 7, 1), date(2026, 7, 14), "done", ""),
    ("Week 1 · Topic Selection Presentation", date(2026, 7, 16), date(2026, 7, 22), "done", ""),
    ("Week 2 · Abstract, Introduction", date(2026, 7, 23), date(2026, 7, 29), "done", ""),
    ("Week 3 · Review of Literature", date(2026, 7, 30), date(2026, 8, 5), "done", ""),
    ("Synopsis Presentation-I", date(2026, 8, 12), date(2026, 8, 12), "done", ""),
    ("Week 4 · Proposed System", date(2026, 8, 13), date(2026, 8, 19), "done", ""),
    ("Week 5 · H/W and S/W Requirements, Timeline Chart", date(2026, 8, 27), date(2026, 9, 2), "done", ""),
    ("Week 6 · Design", date(2026, 9, 3), date(2026, 9, 9), "done", ""),
    ("Week 7 · Implementation (25%)", date(2026, 9, 17), date(2026, 9, 23), "done", "Section 1: causal engine core + chat app base"),
    ("Synopsis Presentation-II", date(2026, 9, 30), date(2026, 9, 30), "today", ""),
    ("Week 8 · Implementation (40%) & Progress Feedback", date(2026, 10, 1), date(2026, 10, 7), "done",
     "Section 2 (evidence search, website): met 28 Sep"),
    ("Week 9 · Implementation (60%) & Overall Progress", date(2026, 10, 8), date(2026, 10, 14), "done",
     "Section 3 (engine + evidence in chat app): met 29 Sep"),
    ("Week 10 · Implementation (80%)", date(2026, 10, 15), date(2026, 10, 21), "plan",
     "Section 4a (better search): our target 3 Oct"),
    ("Guide Evaluation", date(2026, 10, 26), date(2026, 10, 31), "plan", ""),
    ("Final Synopsis Presentation (Tentative)", date(2026, 11, 2), date(2026, 11, 30), "plan", ""),
    ("December · Implementation (100%), Research Paper", date(2026, 12, 1), date(2026, 12, 31), "plan",
     "Section 4: target 6 Oct"),
    ("January · Project Evaluation: Complete Presentation", date(2027, 1, 1), date(2027, 1, 31), "plan", ""),
    ("February · PCUBE (Poster, Presentation, Model)", date(2027, 2, 1), date(2027, 2, 28), "plan", ""),
    ("February · Research Paper, Black Book Submission", date(2027, 2, 1), date(2027, 2, 28), "plan", ""),
]


def draw_gantt(out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(13, 7.6), dpi=200)
    n = len(ROWS)
    for i, (label, start, end, status, note) in enumerate(ROWS):
        y = n - 1 - i
        if start == end:  # a presentation day: a diamond, not a bar
            ax.plot(mdates.date2num(start), y, marker="D", markersize=11, zorder=5,
                    color=DONE if status == "done" else NOW, markeredgecolor="white")
        else:
            width = (end - start).days + 1
            kw = dict(height=0.62, left=mdates.date2num(start), edgecolor="white", linewidth=2)
            if status == "done":
                ax.barh(y, width, color=DONE, **kw)
            elif status == "today":
                ax.barh(y, width, color=NOW, **kw)
            else:
                ax.barh(y, width, color=PLAN, hatch="///", **{**kw, "edgecolor": "#aab2ae", "linewidth": 0.8})
        if note:
            ax.text(mdates.date2num(end) + 3, y, note, va="center", fontsize=8.6, color=INK)
    x = mdates.date2num(TODAY)
    ax.axvline(x, color=INK, linewidth=1.2, linestyle=(0, (4, 3)))
    ax.text(x + 1.5, n - 0.2, "Today: 30 Sep", fontsize=8.8, color=INK, va="top")
    ax.set_yticks(range(n))
    ax.set_yticklabels([r[0] for r in reversed(ROWS)], fontsize=9.6, color=INK)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.tick_params(axis="x", colors=MUTED, labelsize=9.5)
    ax.set_xlim(mdates.date2num(date(2026, 7, 1)), mdates.date2num(date(2027, 2, 28)))
    ax.set_ylim(-0.7, n + 0.6)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#c9d0cc")
    ax.tick_params(axis="y", length=0)
    ax.legend(handles=[Patch(color=DONE, label="Done (signed, or met early)"), Patch(color=NOW, label="Today"),
                       Patch(facecolor=PLAN, hatch="///", edgecolor="#aab2ae", label="Planned"),
                       Line2D([], [], marker="D", color=DONE, linestyle="none", markeredgecolor="white",
                              markersize=9, label="Presentation")],
              loc="lower left", frameon=False, fontsize=9, ncol=4, bbox_to_anchor=(0, -0.1))
    ax.set_title("Gantt chart: Project Interaction Sheet, Group 28 (July 2026 – February 2027)",
                 fontsize=12.5, color=INK, loc="left", pad=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


# Timeline chart: one line per interaction-sheet entry (week, date, task, status).
TIMELINE = [
    ("Week 0", "", "Topic Finalization", "Signed"),
    ("Week 1", "22/07/2026", "Topic Selection Presentation", "Signed"),
    ("Week 2", "29/07/2026", "Abstract, Introduction", "Signed"),
    ("Week 3", "05/08/2026", "Review of Literature", "Signed"),
    ("", "12/08/2026", "Synopsis Presentation-I", "Done"),
    ("Week 4", "19/08/2026", "Proposed System (define problem, approach, scope)", "Signed"),
    ("Week 5", "02/09/2026", "H/W and S/W Requirements & Timeline Chart", "Signed"),
    ("Week 6", "09/09/2026", "Design", "Signed"),
    ("Week 7", "23/09/2026", "Implementation (25%): Section 1, causal engine core + chat app base", "Signed"),
    ("", "30/09/2026", "Synopsis Presentation-II", "Today"),
    ("Week 8", "07/10/2026", "Implementation (40%) & Overall Progress Feedback: Section 2", "Met 28 Sep"),
    ("Week 9", "14/10/2026", "Implementation (60%) & Overall Progress: Section 3", "Met 29 Sep"),
    ("Week 10", "21/10/2026", "Implementation (80%): Section 4a, better search", "Target 3 Oct"),
    ("", "26–31/10/2026", "Guide Evaluation", "Planned"),
    ("", "November 2026", "Final Synopsis Presentation (Tentative)", "Planned"),
    ("", "December 2026", "Implementation (100%): Section 4 complete; Research Paper", "Target 6 Oct"),
    ("", "January 2027", "Project Evaluation: Complete Project Presentation", "Planned"),
    ("", "February 2027", "Project Evaluation: PCUBE (Poster, Presentation and Model)", "Planned"),
    ("", "February 2027", "Research Paper Revision, Submission; Black Book Submission", "Planned"),
]
STATUS_COLOUR = {"Signed": DONE, "Done": DONE, "Today": NOW, "Met 28 Sep": DONE, "Met 29 Sep": DONE,
                 "Target 3 Oct": "#9aa39f", "Target 6 Oct": "#9aa39f", "Planned": "#9aa39f"}


def draw_timeline(out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(13, 7.6), dpi=200)
    n = len(TIMELINE)
    ax.set_xlim(0, 1)
    ax.set_ylim(-1.2, n - 0.2)
    ax.axis("off")
    x_line = 0.175
    ax.plot([x_line, x_line], [-0.3, n - 0.7], color="#c9d0cc", linewidth=2, zorder=1)
    for i, (tag, when, task, status) in enumerate(TIMELINE):
        y = n - 1 - i
        colour = STATUS_COLOUR[status]
        filled = status in ("Signed", "Done", "Today") or status.startswith("Met")
        milestone = "Presentation" in task or "Evaluation" in task
        ax.scatter([x_line], [y], s=110 if milestone else 70, marker="D" if milestone else "o",
                   color=colour if filled else "white", edgecolor=colour, linewidth=1.6, zorder=3)
        ax.text(0.005, y, tag, va="center", fontsize=10, color=INK, fontweight="bold")
        ax.text(0.068, y, when, va="center", fontsize=9.5, color=MUTED)
        ax.text(x_line + 0.02, y, task, va="center", fontsize=10.2, color=INK,
                fontweight="bold" if milestone else "normal")
        ax.text(0.80, y, status, va="center", ha="left", fontsize=9.5, color=colour if filled else MUTED,
                fontweight="bold" if status == "Today" or status.startswith("Met") else "normal")
    ax.set_title("Timeline chart: Project Interaction Sheet, Group 28 (2026–27)",
                 fontsize=12.5, color=INK, loc="left", fontweight="bold")
    ax.text(0.005, -0.75, "Implementation in four sections (sheet note): 1 causal engine core · 2 evidence search (RAG), "
            "secondary outcomes, website ·\n3 causal engine + evidence inside the chat app · 4 better search, "
            "real-data adapter, evaluation tools.", fontsize=8.8, color=MUTED, va="center")
    fig.tight_layout()
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in (draw_gantt(OUT_DIR / "gantt.png"), draw_timeline(OUT_DIR / "timeline.png")):
        shutil.copy(path, ROOT / "report" / "figures" / path.name)
        print(f"wrote {path.relative_to(ROOT)} (and report/figures/{path.name})")
