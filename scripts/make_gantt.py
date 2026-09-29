"""Draw the Gantt chart and the timeline chart from the department's Project Interaction Sheet.

    .venv/bin/python scripts/make_gantt.py     # writes docs/midsem/gantt.png, docs/midsem/timeline.png
                                               # and copies both into report/figures/

Every row follows the interaction sheet (Second Half of 2026, First Half of 2027): the weekly tasks
signed with the guide, Synopsis Presentations I and II, the 25 / 40 / 60 / 80 / 100% implementation
checks, guide evaluation, the final synopsis presentation, the research paper and the black book.
As the sheet asks, implementation is split into four sections; each shows the sheet's deadline
(diamond) and our own dates (bar). Exam dates come from docs/01_Master_Plan.md.

Colours: pine = done, amber = in progress, hatched grey = planned, cross-hatched = exams.
Edit ROWS / MILESTONES when the plan changes, then rerun.
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

# (label, start, end, status, sheet deadline or None, deadline label)
ROWS = [
    ("Wk 0  Topic finalisation (vacation slot)", date(2026, 7, 1), date(2026, 7, 21), "done", None, ""),
    ("Wk 1  Topic selection presentation (16 papers)", date(2026, 7, 15), date(2026, 7, 22), "done", date(2026, 7, 22), ""),
    ("Wk 2  Abstract and introduction", date(2026, 7, 23), date(2026, 7, 29), "done", date(2026, 7, 29), ""),
    ("Wk 3  Review of literature", date(2026, 7, 30), date(2026, 8, 5), "done", date(2026, 8, 5), ""),
    ("Wk 4  Proposed system: problem, approach, scope", date(2026, 8, 13), date(2026, 8, 19), "done", date(2026, 8, 19), ""),
    ("Wk 5  H/W, S/W requirements, timeline chart", date(2026, 8, 20), date(2026, 9, 2), "done", date(2026, 9, 2), ""),
    ("Wk 6  Design: block, flow diagrams, working", date(2026, 9, 3), date(2026, 9, 9), "done", date(2026, 9, 9), ""),
    ("Impl. 1  Causal engine core + chat app base", date(2026, 9, 10), date(2026, 9, 25), "done", date(2026, 9, 23), "25%"),
    ("Impl. 2  Evidence search (RAG), outcomes, website", date(2026, 9, 24), date(2026, 9, 28), "done", date(2026, 10, 7), "40%"),
    ("Impl. 3  Engine + RAG inside the chat app", date(2026, 9, 29), date(2026, 10, 3), "now", date(2026, 10, 14), "60%"),
    ("Impl. 4  Better search, real-data adapter, eval tools", date(2026, 10, 3), date(2026, 10, 6), "plan", date(2026, 10, 21), "80%"),
    ("Doctor review, usability study, results frozen", date(2026, 10, 7), date(2026, 10, 23), "plan", None, ""),
    ("Guide evaluation", date(2026, 10, 26), date(2026, 10, 31), "plan", None, ""),
    ("Practical exams", date(2026, 10, 31), date(2026, 11, 7), "exam", None, ""),
    ("Final synopsis presentation (tentative)", date(2026, 11, 9), date(2026, 11, 17), "plan", None, ""),
    ("Theory exams", date(2026, 11, 18), date(2026, 11, 30), "exam", None, ""),
    ("100% sign-off; research paper (format, plagiarism)", date(2026, 12, 1), date(2026, 12, 31), "plan", None, "100%"),
    ("Project evaluation: complete presentation", date(2027, 1, 4), date(2027, 1, 30), "plan", None, ""),
    ("PCUBE; paper revision; black book submission", date(2027, 2, 1), date(2027, 2, 27), "plan", None, ""),
]
MILESTONES = [(date(2026, 8, 12), "Synopsis\nPresentation-I"), (date(2026, 9, 30), "Synopsis\nPresentation-II")]


def draw_gantt(out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(13, 7.6), dpi=200)
    n = len(ROWS)
    for i, (label, start, end, status, due, due_label) in enumerate(ROWS):
        y = n - 1 - i
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
        if due is not None and label.startswith("Impl."):
            x = mdates.date2num(due)
            ax.plot(x, y, marker="D", markersize=7, color=INK, markeredgecolor="white", zorder=5)
            tx = max(x, mdates.date2num(end) + 1) + 2
            ax.text(tx, y, f"sheet: {due_label} by {due:%d %b}", va="center", fontsize=8.5, color=MUTED)
        elif due_label == "100%":
            ax.text(mdates.date2num(end) - 2, y, "100%", va="center", ha="right", fontsize=8.5, color=INK)
    for d, text in MILESTONES:
        x = mdates.date2num(d)
        ax.axvline(x, color=INK, linewidth=1.2, linestyle=(0, (4, 3)))
        ax.text(x + 1.5, n - 0.2, text, fontsize=8.8, color=INK, va="top")
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
    ax.legend(handles=[Patch(color=DONE, label="Done"), Patch(color=NOW, label="In progress"),
                       Patch(facecolor=PLAN, hatch="///", edgecolor="#aab2ae", label="Planned"),
                       Patch(facecolor="#f3f4f4", hatch="xx", edgecolor="#b5bcb9", label="Exams"),
                       Line2D([], [], marker="D", color=INK, linestyle="none", markeredgecolor="white",
                              label="Interaction-sheet deadline")],
              loc="lower left", frameon=False, fontsize=9, ncol=5, bbox_to_anchor=(0, -0.1))
    ax.set_title("DiaCausal Gantt chart from the Project Interaction Sheet (Group 28), Jul 2026 – Feb 2027",
                 fontsize=12.5, color=INK, loc="left", pad=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


# Timeline chart: one line per interaction-sheet entry (week, date, task, status).
TIMELINE = [
    ("Wk 0", "Jul 2026", "Topic finalisation, feasibility study", "Signed"),
    ("Wk 1", "22 Jul", "Topic selection presentation: 16 papers, comparison table, gaps", "Signed"),
    ("Wk 2", "29 Jul", "Abstract and introduction (abstract revised)", "Signed"),
    ("Wk 3", "05 Aug", "Review of literature (changes suggested, made)", "Signed"),
    ("SP-I", "12 Aug", "Synopsis Presentation-I", "Done"),
    ("Wk 4", "19 Aug", "Proposed system: problem, approach, scope", "Signed"),
    ("Wk 5", "02 Sep", "H/W and S/W requirements, timeline chart", "Signed"),
    ("Wk 6", "09 Sep", "Design: block, flow/activity diagrams, working of the system", "Signed"),
    ("Wk 7", "23 Sep", "Implementation 25%: coding details (Section 1)", "Signed"),
    ("SP-II", "30 Sep", "Synopsis Presentation-II (about 64% done)", "Today"),
    ("Wk 8", "07 Oct", "Implementation 40% + progress feedback (Section 2 done early)", "Ahead"),
    ("Wk 9", "14 Oct", "Implementation 60% (Section 3: our target 3 Oct)", "Planned"),
    ("Wk 10", "21 Oct", "Implementation 80% (Section 4: our target 6 Oct)", "Planned"),
    ("Eval", "26–31 Oct", "Guide evaluation", "Planned"),
    ("Final", "Nov 2026", "Final synopsis presentation (tentative)", "Planned"),
    ("Dec", "Dec 2026", "100% implementation; research paper format, plagiarism, language, flow", "Planned"),
    ("Jan", "Jan 2027", "Project evaluation: complete project presentation", "Planned"),
    ("Feb", "Feb 2027", "PCUBE (poster, presentation, model); paper revision and submission", "Planned"),
    ("Feb", "Feb 2027", "Black book (plagiarism check, final submission with interaction sheet)", "Planned"),
]
STATUS_COLOUR = {"Signed": DONE, "Done": DONE, "Today": NOW, "Ahead": DONE, "Planned": "#9aa39f"}


def draw_timeline(out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(13, 7.6), dpi=200)
    n = len(TIMELINE)
    ax.set_xlim(0, 1)
    ax.set_ylim(-1.2, n - 0.2)
    ax.axis("off")
    x_line = 0.14
    ax.plot([x_line, x_line], [-0.3, n - 0.7], color="#c9d0cc", linewidth=2, zorder=1)
    for i, (tag, when, task, status) in enumerate(TIMELINE):
        y = n - 1 - i
        colour = STATUS_COLOUR[status]
        filled = status != "Planned"
        milestone = tag in ("SP-I", "SP-II", "Eval", "Final")
        ax.scatter([x_line], [y], s=110 if milestone else 70, marker="D" if milestone else "o",
                   color=colour if filled else "white", edgecolor=colour, linewidth=1.6, zorder=3)
        ax.text(0.005, y, tag, va="center", fontsize=10, color=INK, fontweight="bold")
        ax.text(0.052, y, when, va="center", fontsize=9.5, color=MUTED)
        ax.text(x_line + 0.02, y, task, va="center", fontsize=10.2, color=INK,
                fontweight="bold" if milestone else "normal")
        ax.text(0.80, y, status, va="center", ha="left", fontsize=9.5, color=colour if status != "Planned" else MUTED,
                fontweight="bold" if status in ("Today", "Ahead") else "normal")
    ax.set_title("DiaCausal timeline chart: every entry of the Project Interaction Sheet (2026–27)",
                 fontsize=12.5, color=INK, loc="left", fontweight="bold")
    ax.text(0.005, -0.75, "Implementation in four sections, as the sheet asks: 1 causal engine core + chat app base · "
            "2 evidence search (RAG), outcomes, website ·\n3 engine + RAG inside the chat app · "
            "4 better search, real-data adapter, evaluation tools.", fontsize=8.8, color=MUTED, va="center")
    fig.tight_layout()
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    return out


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in (draw_gantt(OUT_DIR / "gantt.png"), draw_timeline(OUT_DIR / "timeline.png")):
        shutil.copy(path, ROOT / "report" / "figures" / path.name)
        print(f"wrote {path.relative_to(ROOT)} (and report/figures/{path.name})")
