#!/usr/bin/env python3
"""Create the FIRST admin account (the whiteboard's "master login"). Run from the repo root:

    macOS / Linux:  python3 scripts/create_admin.py USER_ID "Display name"
    Windows:        py scripts/create_admin.py USER_ID "Display name"

It asks for the password at a hidden prompt (there is no default password anywhere).
It only works while there is no admin yet; after that, admins use scripts/admin.py.
The first sign-in on the web page then sets up the authenticator app (QR code).
"""

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
VENV_PY = BACKEND / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

if __name__ == "__main__":
    if not VENV_PY.exists():
        sys.exit("Run the one-time setup first: python3.12 scripts/setup.py")
    extra = [a for a in sys.argv[1:] if a == "--password-stdin"]
    names = [a for a in sys.argv[1:] if a != "--password-stdin"]
    if len(names) != 2:
        sys.exit(__doc__)
    sys.exit(subprocess.call([str(VENV_PY), "-m", "app.auth.cli", *extra, "create-first-admin", *names], cwd=BACKEND))
