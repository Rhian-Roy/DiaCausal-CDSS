"""Pytest picks the helpers up from guard_helpers.py (tests/guards is not a package: put it on the path)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
