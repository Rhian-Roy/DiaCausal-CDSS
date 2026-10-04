"""Nothing under diacausal/ may use legacy/ (docs/RESTRUCTURE_PLAN.md: legacy/ is parked, not a dependency).

Scans the source with `ast`: an import of `legacy` or `causal_engine` (the old 2-arm package, now
legacy/causal_engine), or a string that names the legacy folder as a path. A minimum file count makes
sure the scan really looked at the package (a scan of an empty folder would pass without checking).
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "diacausal"
FORBIDDEN_ROOTS = {"legacy", "causal_engine"}
MIN_FILES = 12


def _violations(path: Path) -> list[str]:
    bad = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        bad += [f"imports {n}" for n in names if n.split(".")[0] in FORBIDDEN_ROOTS]
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value.replace("\\", "/")
            if v.startswith("legacy/") or v == "legacy" or "/legacy/" in v:
                bad.append(f"names the path {v!r}")
    return bad


def test_nothing_under_diacausal_uses_legacy():
    files = sorted(PACKAGE.rglob("*.py"))
    assert len(files) >= MIN_FILES, f"scanned only {len(files)} files: is the scan looking at the right folder?"
    problems = {str(f.relative_to(ROOT)): v for f in files if (v := _violations(f))}
    assert not problems, f"diacausal/ must not use legacy/: {problems}"


def test_the_scan_catches_a_violation(tmp_path):
    for code in ("import legacy.x", "from causal_engine import dag", "P = 'legacy/data.csv'"):
        f = tmp_path / "bad.py"
        f.write_text(code, encoding="utf-8")
        assert _violations(f), code
    f.write_text("import numpy\nP = 'data/rules.csv'\n", encoding="utf-8")
    assert not _violations(f)
