"""Check the repository against docs/RESTRUCTURE_FILE_MAP.csv (the restructure plan, P10/P13).

    python scripts/check_moves.py --step 2        # steps 0..2 must be done, 3..10 must not have started
    python scripts/check_moves.py                  # same as --step 0 (nothing moved yet)
    python scripts/check_moves.py --list           # print rows per step and what each expects

For each row of the map:
  * a step AFTER --step: the old path must still exist, and no new path may exist yet;
  * a step UP TO --step: every new path must exist; the old path must be gone, or be a small
    shim (a file of at most 25 lines that imports from the `diacausal` package) left on purpose;
  * action "stay" / "stay + edit" / "merge": the path must exist (for "merge", old and new both).
Files created after the map was made (not in the CSV) are fine and only counted. Two things fail:
a folder at the repository root called `rag` in any letter case other than the original `RAG/` (and `RAG/`
itself once step 2 is done): it would clash on macOS and Windows; and two tracked paths that differ only
in letter case.

Exit code 0 = everything matches; 1 = problems (listed).
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "docs" / "RESTRUCTURE_FILE_MAP.csv"
MAX_SHIM_LINES = 25


def read_map(path: Path = MAP) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["step"] = int(r["step"])
        r["new_paths"] = [p.strip() for p in r["new_path"].split(" + ")]
    return rows


def is_shim(path: Path) -> bool:
    """A leftover at an old path is acceptable only if it is a tiny file that points at the new package."""
    if not path.is_file():
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return False
    return len(lines) <= MAX_SHIM_LINES and any("diacausal" in line and "import" in line for line in lines)


def check(rows: list[dict], root: Path, step: int, tracked: list[str] | None = None) -> list[str]:
    problems: list[str] = []
    for r in rows:
        old, news, row_step, action = root / r["old_path"], [root / p for p in r["new_paths"]], r["step"], r["action"]
        moves = r["new_paths"] != [r["old_path"]]
        if action in ("stay", "stay + edit"):
            if not old.exists():
                problems.append(f"step {row_step}: {r['old_path']} should stay in place but is missing")
        elif action == "merge":
            for p in [old, *news]:
                if not p.exists():
                    problems.append(f"step {row_step}: {p.relative_to(root)} is missing (merge target and source must both exist)")
        elif moves and row_step > step:  # not started
            if not old.exists():
                problems.append(f"step {row_step}: {r['old_path']} is gone but its step has not been done yet")
            for p in news:
                if p.exists():
                    problems.append(f"step {row_step}: {p.relative_to(root)} exists too early (its step has not been done yet)")
        elif moves:  # done
            for p in news:
                if not p.exists():
                    problems.append(f"step {row_step}: {p.relative_to(root)} is missing (the move is done)")
            if old.exists() and not is_shim(old):
                problems.append(f"step {row_step}: {r['old_path']} is still there and is not a shim (at most {MAX_SHIM_LINES} lines importing diacausal)")
    names = tracked if tracked is not None else _tracked(root)
    seen: dict[str, str] = {}
    for name in names:
        low = name.lower()
        if low in seen and seen[low] != name:
            problems.append(f"letter-case clash: {seen[low]} and {name}")
        seen[low] = name
        top = name.split("/")[0]
        if top.lower() == "rag" and "/" in name and not (top == "RAG" and step < 2):
            why = "RAG/ must be gone after step 2" if top == "RAG" else "never create a root folder called rag, in any letter case"
            problems.append(f"{why}: {name}")
    return problems


def _tracked(root: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True)
    return out.stdout.splitlines() if out.returncode == 0 else []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--step", type=int, default=0, help="the last step that is done (0 = nothing moved yet)")
    ap.add_argument("--list", action="store_true", help="print the rows of each step")
    a = ap.parse_args(argv)
    rows = read_map()
    if a.list:
        for s in sorted({r["step"] for r in rows if r["new_paths"] != [r["old_path"]]}):
            todo = [r for r in rows if r["step"] == s and r["new_paths"] != [r["old_path"]]]
            print(f"step {s}: {len(todo)} files")
            for r in todo:
                print(f"   {r['old_path']}  ->  {r['new_path']}   [{r['action']}]")
        return 0
    problems = check(rows, ROOT, a.step)
    in_map = {r["old_path"] for r in rows}
    new_files = [n for n in _tracked(ROOT) if n not in in_map and not any(n in r["new_paths"] for r in rows)]
    if problems:
        print(f"check_moves: {len(problems)} problem(s) for step {a.step}:")
        for p in problems:
            print("  -", p)
        return 1
    print(f"check_moves: all {len(rows)} rows match for step {a.step} ({len(new_files)} tracked files are newer than the map).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
