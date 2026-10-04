"""The restructure tools (P13 step 0): the file map is consistent, check_moves catches wrong states, and the
baseline comparison catches a real change but not last-digit noise."""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


check_moves = _load("check_moves")
baseline = _load("restructure_baseline")


def test_the_file_map_is_consistent():
    rows = check_moves.read_map()
    assert len(rows) >= 610
    olds = [r["old_path"] for r in rows]
    assert len(olds) == len(set(olds)), "an old path appears twice"
    news = [p for r in rows for p in r["new_paths"] if r["action"] != "merge"]
    assert len({n.lower() for n in news if news.count(n) == 1}) == len({n for n in news if news.count(n) == 1}), "case clash"
    assert not [n for n in news if n.split("/")[0].lower() == "rag"], "a root folder called rag"
    assert {r["step"] for r in rows} <= set(range(0, 11))
    assert {r["action"] for r in rows} <= {"stay", "stay + edit", "move", "split", "merge"}


LAST_STEP_DONE = 4  # raise by one in each restructure pull request (docs/RESTRUCTURE_PLAN.md, section 5)


def test_the_tree_matches_the_map_for_the_last_step_done():
    """Steps up to LAST_STEP_DONE must be done and later steps must not have started. Fails when a move
    lands without raising LAST_STEP_DONE (or the other way round): run check_moves.py --step N."""
    assert check_moves.check(check_moves.read_map(), ROOT, step=LAST_STEP_DONE) == []


def _tree(tmp_path: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)


ROWS = [{"old_path": "a/x.py", "new_path": "diacausal/x.py", "step": 2, "action": "move", "notes": "", "new_paths": ["diacausal/x.py"]},
        {"old_path": "keep.txt", "new_path": "keep.txt", "step": 0, "action": "stay", "notes": "", "new_paths": ["keep.txt"]}]


def test_check_moves_not_started_done_with_shim_and_wrong_states(tmp_path):
    _tree(tmp_path, {"a/x.py": "print(1)\n" * 40, "keep.txt": "k"})
    assert check_moves.check(ROWS, tmp_path, step=0, tracked=[]) == []            # not started: old there, new absent
    assert check_moves.check(ROWS, tmp_path, step=2, tracked=[])                  # claims done but nothing moved
    _tree(tmp_path, {"diacausal/x.py": "real code\n" * 60})
    assert any("exists too early" in p for p in check_moves.check(ROWS, tmp_path, step=0, tracked=[]))
    assert any("not a shim" in p for p in check_moves.check(ROWS, tmp_path, step=2, tracked=[]))  # big old file left behind
    _tree(tmp_path, {"a/x.py": "import sys\nsys.modules[__name__] = __import__('diacausal.x')\nfrom diacausal import x  # noqa\n"})
    assert check_moves.check(ROWS, tmp_path, step=2, tracked=[]) == []            # done, with a tiny shim
    (tmp_path / "keep.txt").unlink()
    assert any("should stay in place" in p for p in check_moves.check(ROWS, tmp_path, step=2, tracked=[]))


def test_check_moves_forbids_a_root_rag_folder_and_case_clashes(tmp_path):
    _tree(tmp_path, {"a/x.py": "x", "keep.txt": "k"})
    assert check_moves.check(ROWS, tmp_path, step=0, tracked=["RAG/sources.csv"]) == []                       # the original, before step 2
    assert any("RAG/ must be gone" in p for p in check_moves.check(ROWS, tmp_path, step=2, tracked=["RAG/sources.csv"]))
    assert any("never create a root folder" in p for p in check_moves.check(ROWS, tmp_path, step=0, tracked=["rag/index.py"]))
    assert any("never create a root folder" in p for p in check_moves.check(ROWS, tmp_path, step=0, tracked=["Rag/index.py"]))
    assert any("letter-case clash" in p for p in check_moves.check(ROWS, tmp_path, step=0, tracked=["docs/A.md", "docs/a.md"]))


def test_baseline_comparison_ignores_last_digit_noise_and_catches_a_real_change():
    a = {"v": [1.0, 2.0, {"x": 0.1234567890123}], "s": "text"}
    assert baseline.first_difference(a, {"v": [1.0, 2.0 + 1e-15, {"x": 0.1234567890123}], "s": "text"}) is None
    assert "v[1]" in baseline.first_difference(a, {"v": [1.0, 2.001, {"x": 0.1234567890123}], "s": "text"})
    assert "keys differ" in baseline.first_difference(a, {"v": [], "z": 1})
    assert "s:" in baseline.first_difference(a, {"v": a["v"], "s": "other"})
    assert "items" in baseline.first_difference({"v": [1, 2]}, {"v": [1]})


def test_baseline_folder_comparison_detects_a_changed_csv_cell(tmp_path):
    def make(d: Path, value: str) -> None:
        (d / "benchmark").mkdir(parents=True)
        for n in ("model.json", "evidence.json", "rag_eval.json"):
            (d / n).write_text('{"a": 1.0}')
        (d / "openapi.json").write_text("{}")
        for n in ("benchmark_summary.csv", "refutation.csv", "evalues.csv"):
            with (d / "benchmark" / n).open("w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["method", "bias"])
                w.writerow(["AIPW", value if n == "benchmark_summary.csv" else "0.5"])

    make(tmp_path / "old", "0.0123")
    make(tmp_path / "same", "0.0123000000000001")
    make(tmp_path / "diff", "0.0124")
    assert baseline.compare_dirs(tmp_path / "old", tmp_path / "same") == []
    problems = baseline.compare_dirs(tmp_path / "old", tmp_path / "diff")
    assert problems and "benchmark_summary.csv" in problems[0]
