#!/usr/bin/env python3
"""Account administration, done as an admin (your user ID, password and current 6-digit code).

    python3 scripts/admin.py --as YOUR_ADMIN_ID create-user dr.mehta "Dr Mehta"
    python3 scripts/admin.py --as YOUR_ADMIN_ID create-user dr.shah "Dr Shah" --role admin
    python3 scripts/admin.py --as YOUR_ADMIN_ID disable dr.mehta      (and: enable)
    python3 scripts/admin.py --as YOUR_ADMIN_ID unlock dr.mehta       (after too many attempts)
    python3 scripts/admin.py --as YOUR_ADMIN_ID reset-mfa dr.mehta    (lost phone: set up again)
    python3 scripts/admin.py --as YOUR_ADMIN_ID list

(Windows: py instead of python3.) Every action is written to the audit log.
"""

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
VENV = BACKEND / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
# In a container there is no backend/.venv: the libraries are installed for the
# interpreter running this script, so use that one.
VENV_PY = VENV if VENV.exists() else Path(sys.executable)

if __name__ == "__main__":
    if not VENV_PY.exists():
        sys.exit("Run the one-time setup first: python3.12 scripts/setup.py")
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        sys.exit(__doc__)
    sys.exit(subprocess.call([str(VENV_PY), "-m", "app.auth.cli", *sys.argv[1:]], cwd=BACKEND))
