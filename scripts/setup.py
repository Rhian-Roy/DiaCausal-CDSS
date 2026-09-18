#!/usr/bin/env python3
"""One-time setup for the DiaCausal chat app. Run it from the repo root with Python 3.12:

    macOS / Linux:  python3.12 scripts/setup.py
    Windows:        py -3.12 scripts\\setup.py

It creates backend/.venv (the backend's own private Python) and installs the
libraries for the backend (pip) and the frontend (npm). Safe to run again.
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

NODE_MIN = (20, 19)  # Vite 8 needs 20.19+; we use 24 LTS

INSTALL_HELP = """
How to install the missing tool (see docs/SETUP.md for details):
  macOS:   brew install python@3.12 node@24
  Windows: winget install Python.Python.3.12 OpenJS.NodeJS.LTS   (then open a new terminal)
  Linux:   use your package manager, or https://www.python.org and https://nodejs.org
"""


def step(title: str) -> None:
    print(f"\n== {title}")


def fail(message: str) -> None:
    print(f"\n[FAIL] {message}")
    print(INSTALL_HELP)
    sys.exit(1)


def run(cmd: list[str], cwd: Path) -> None:
    print("   $", " ".join(str(part) for part in cmd))
    if subprocess.run(cmd, cwd=cwd).returncode != 0:
        print(f"\n[FAIL] That command failed (see the output above). Fix it, then run this script again.")
        sys.exit(1)


def venv_python_version() -> tuple[int, int] | None:
    if not VENV_PY.exists():
        return None
    out = subprocess.run([str(VENV_PY), "--version"], capture_output=True, text=True).stdout
    match = re.search(r"(\d+)\.(\d+)", out)
    return (int(match[1]), int(match[2])) if match else None


def main() -> None:
    print("DiaCausal setup")

    step("1/4  Python")
    if sys.version_info[:2] != (3, 12):
        fail(
            f"This is Python {sys.version.split()[0]}; the backend needs Python 3.12.\n"
            "       Run the script with 3.12:  macOS/Linux  python3.12 scripts/setup.py\n"
            "                                  Windows      py -3.12 scripts\\setup.py"
        )
    print(f"   [OK] Python {sys.version.split()[0]}")

    step("2/4  Node.js")
    node = shutil.which("node")
    npm = shutil.which("npm")
    if not node or not npm:
        fail("Node.js (node and npm) was not found on this computer.")
    raw = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    match = re.match(r"v(\d+)\.(\d+)", raw)
    if not match or (int(match[1]), int(match[2])) < NODE_MIN:
        fail(f"Node.js {raw or '?'} is too old; install Node 24 LTS.")
    print(f"   [OK] Node {raw}" + ("" if raw.startswith("v24.") else "  (works; the project uses Node 24 LTS)"))

    step("3/4  Backend: private Python in backend/.venv + libraries")
    if venv_python_version() != (3, 12):
        # Missing, or made with another Python version: (re)build it.
        run([sys.executable, "-m", "venv", "--clear", str(VENV)], ROOT)
    else:
        print("   backend/.venv already exists (Python 3.12), reusing it")
    run([str(VENV_PY), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", "requirements-dev.txt"], BACKEND)
    print("   [OK] backend libraries installed")

    step("4/4  Frontend: libraries in frontend/node_modules")
    run([npm, "ci", "--no-audit", "--no-fund"], FRONTEND)
    print("   [OK] frontend libraries installed")

    check = "py scripts\\check_all.py" if WINDOWS else "python3 scripts/check_all.py"
    print(f"\nSetup finished. Now check that everything works:\n\n    {check}\n")


if __name__ == "__main__":
    main()
