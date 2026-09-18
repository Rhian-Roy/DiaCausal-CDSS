#!/usr/bin/env python3
"""One-time setup for the DiaCausal chat app. Run it from the repo root with Python 3.12:

    macOS / Linux:  python3.12 scripts/setup.py
    Windows:        py -3.12 scripts/setup.py

It creates backend/.venv (the backend's own private Python) and installs the
libraries for the backend (pip) and the frontend (npm). Safe to run again, e.g.
after a `git pull` — stop the backend and frontend servers first.
Afterwards, check everything with:  python3 scripts/check_all.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
WINDOWS = sys.platform == "win32"
VENV = BACKEND / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if WINDOWS else "bin/python")

INSTALL_HELP = """
How to install the missing tool (details: docs/SETUP.md, step 1):
  macOS:   brew install python@3.12 node@24
           echo 'export PATH="/opt/homebrew/opt/node@24/bin:$PATH"' >> ~/.zshrc   (then open a new terminal)
  Windows: winget install Python.Python.3.12 OpenJS.NodeJS.LTS   (then open a new terminal)
  Linux:   sudo apt install python3.12 python3.12-venv
           Node 24 LTS from https://nodejs.org/en/download (Ubuntu's own 'nodejs' package is too old)
"""


def node_is_supported(major: int, minor: int) -> bool:
    """The pinned test tools (Vitest 5, jsdom 30) support Node 22.22+, 24.15+ and 26+."""
    return (major == 22 and minor >= 22) or (major == 24 and minor >= 15) or major >= 26


def step(title: str) -> None:
    print(f"\n== {title}")


def fail(message: str) -> None:
    print(f"\n[FAIL] {message}")
    print(INSTALL_HELP)
    sys.exit(1)


def run(cmd: list[str], cwd: Path) -> None:
    print("   $", " ".join(str(part) for part in cmd))
    if subprocess.run([str(part) for part in cmd], cwd=cwd).returncode != 0:
        print("\n[FAIL] That command failed (see the output above). Fix it, then run this script again.")
        print("       If this is a re-run: stop the backend and frontend servers first (Ctrl+C);")
        print("       on Windows they lock files that setup needs to replace.")
        sys.exit(1)


def venv_is_usable() -> bool:
    """backend/.venv exists, is Python 3.12 and has pip (a half-made one does not)."""
    if not VENV_PY.exists():
        return False
    probe = subprocess.run(
        [str(VENV_PY), "-c", "import sys, pip; print(sys.version_info[:2] == (3, 12))"],
        capture_output=True, text=True,
    )
    return probe.returncode == 0 and probe.stdout.strip() == "True"


def main() -> None:
    # Show each line as it happens, and never crash on a character the terminal can't show.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace", line_buffering=True)

    print("DiaCausal setup")

    step("1/4  Python")
    if sys.version_info[:2] != (3, 12):
        fail(
            f"This is Python {sys.version.split()[0]}; the backend needs Python 3.12.\n"
            "       Run the script with 3.12:  macOS/Linux  python3.12 scripts/setup.py\n"
            "                                  Windows      py -3.12 scripts/setup.py"
        )
    print(f"   [OK] Python {sys.version.split()[0]}")

    step("2/4  Node.js")
    node = shutil.which("node")
    npm = shutil.which("npm")
    if not node or not npm:
        fail("Node.js (node and npm) was not found on this computer.")
    raw = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    match = re.match(r"v(\d+)\.(\d+)", raw)
    if not match or not node_is_supported(int(match[1]), int(match[2])):
        fail(f"Node.js {raw or '?'} is not supported by the project's tools; install Node 24 LTS (24.15 or newer).")
    print(f"   [OK] Node {raw}" + ("" if raw.startswith("v24.") else "  (works; the project uses Node 24 LTS)"))

    step("3/4  Backend: private Python in backend/.venv + libraries")
    if venv_is_usable():
        print("   backend/.venv already exists (Python 3.12), reusing it")
    else:
        # Missing, half-made (no pip) or another Python version: (re)build it.
        run([sys.executable, "-m", "venv", "--clear", VENV], ROOT)
    run([VENV_PY, "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", "requirements-dev.txt"], BACKEND)
    print("   [OK] backend libraries installed")

    step("4/4  Frontend: libraries in frontend/node_modules")
    run([npm, "ci", "--no-audit", "--no-fund"], FRONTEND)
    print("   [OK] frontend libraries installed")
    print("   (Lines starting with 'npm warn' - on a Mac, one about 'fsevents' - are harmless.)")

    check = "py scripts/check_all.py" if WINDOWS else "python3 scripts/check_all.py"
    print(f"\nSetup finished. Now check that everything works:\n\n    {check}\n")


if __name__ == "__main__":
    main()
