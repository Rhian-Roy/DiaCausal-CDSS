"""Baseline for the restructure (docs/RESTRUCTURE_PLAN.md, section 6): prove a move changed nothing.

    .venv/bin/python scripts/restructure_baseline.py save       # on the unmoved tree: records the numbers
    .venv/bin/python scripts/restructure_baseline.py compare    # after each step: regenerates and compares

`save` writes ~/DiaCausal-baselines/<git short sha>/ (outside the repository; nothing tracked is touched):
  model.json        what `python -m diacausal_engine.export_web` would write to web/model.json
  evidence.json     what `python -m diacausal_rag.export_web` would write to web/evidence.json
  openapi.json      the committed openapi.json (after `export_openapi.py --check` passed)
  benchmark/        the quick benchmark (3 repeats x 1,500 patients): benchmark_summary.csv, refutation.csv, evalues.csv
  rag_eval.json     the RAG evaluation summary (template explanations, 60 gold questions)
`compare` recomputes all of it with the CURRENT code, using the new module names if they exist and the
old ones otherwise, and compares: numbers to a relative 1e-12 (the same tolerance tests/web already uses,
because last-digit float differences are normal), text exactly. It compares with the folder named by
--dir, or with the newest one. Compare with a baseline made on THIS computer, not with the committed
web/*.json files (a fresh export can differ from them in the last digit of a few floats).

Exit code 0 = identical, 1 = something differs (the first differences are printed).
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import math
import platform
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
BASE = Path.home() / "DiaCausal-baselines"
TOL = 1e-12


def _module(*names: str):
    """The first importable module among the new name and the old name."""
    last = None
    for n in names:
        try:
            return importlib.import_module(n)
        except ModuleNotFoundError as e:
            last = e
    raise last


def generate(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    rec = _module("diacausal.causal_inference.recommend", "diacausal_engine.recommend")
    web_e = _module("diacausal.causal_inference.export_web", "diacausal_engine.export_web")
    web_r = _module("diacausal.rag.export_web", "diacausal_rag.export_web")
    bench = _module("diacausal.causal_inference.benchmark", "diacausal_engine.benchmark")
    ev = _module("diacausal.rag.evaluate", "diacausal_rag.evaluate")
    (out / "model.json").write_text(json.dumps(web_e.model_dict(rec.Engine()), sort_keys=True), encoding="utf-8")
    (out / "evidence.json").write_text(json.dumps(web_r.evidence_dict(), sort_keys=True), encoding="utf-8")
    fresh = subprocess.run([sys.executable, str(ROOT / "scripts/export_openapi.py"), "--check"], capture_output=True, text=True)
    if fresh.returncode != 0:
        raise SystemExit("openapi.json is stale: " + fresh.stderr.strip())
    (out / "openapi.json").write_text((ROOT / "openapi.json").read_text(encoding="utf-8"), encoding="utf-8")
    bench.run(3, 1500, 1000, out / "benchmark")
    _rows, summary = ev.run("template")
    (out / "rag_eval.json").write_text(json.dumps(summary, sort_keys=True, default=str), encoding="utf-8")


def first_difference(a, b, path="") -> str | None:
    """Where two JSON-like trees differ: same keys, lengths, strings; numbers equal to a relative TOL."""
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return f"{path}: keys differ ({sorted(set(a) ^ set(b))[:5]})"
        return next((d for k in a if (d := first_difference(a[k], b[k], f"{path}.{k}"))), None)
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f"{path}: {len(a)} vs {len(b)} items"
        return next((d for i, (x, y) in enumerate(zip(a, b)) if (d := first_difference(x, y, f"{path}[{i}]"))), None)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return None if math.isclose(a, b, rel_tol=TOL, abs_tol=TOL) else f"{path}: {a!r} vs {b!r}"
    return None if a == b else f"{path}: {str(a)[:60]!r} vs {str(b)[:60]!r}"


def _csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k, v in r.items():
            try:
                r[k] = float(v)
            except (TypeError, ValueError):
                pass
    return rows


def compare_dirs(old: Path, new: Path) -> list[str]:
    problems = []
    for name in ("model.json", "evidence.json", "rag_eval.json"):
        d = first_difference(json.loads((old / name).read_text()), json.loads((new / name).read_text()), name)
        if d:
            problems.append(d)
    if (old / "openapi.json").read_text() != (new / "openapi.json").read_text():
        problems.append("openapi.json differs")
    for name in ("benchmark_summary.csv", "refutation.csv", "evalues.csv"):
        d = first_difference(_csv(old / "benchmark" / name), _csv(new / "benchmark" / name), name)
        if d:
            problems.append(d)
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["save", "compare"])
    ap.add_argument("--dir", type=Path, default=None, help="baseline folder (default: the newest in ~/DiaCausal-baselines)")
    a = ap.parse_args(argv)
    if a.action == "save":
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or "nogit"
        target = a.dir or BASE / f"{date.today()}-{sha}"
        generate(target)
        (target / "meta.json").write_text(json.dumps({"git": sha, "date": str(date.today()), "python": platform.python_version(),
                                                      "platform": platform.platform()}, indent=1), encoding="utf-8")
        print(f"baseline saved in {target}")
        return 0
    old = a.dir or max((p for p in BASE.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, default=None)
    if old is None:
        print("no baseline yet: run `restructure_baseline.py save` on the unmoved tree first", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        generate(Path(tmp))
        problems = compare_dirs(old, Path(tmp))
    if problems:
        print(f"restructure_baseline: DIFFERENT from {old}:")
        for p in problems[:10]:
            print("  -", p)
        return 1
    print(f"restructure_baseline: identical to {old} (numbers to {TOL:g}, text exact)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
