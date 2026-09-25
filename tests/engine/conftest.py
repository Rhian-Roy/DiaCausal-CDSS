"""Shared fixtures for the causal engine tests (run: python -m pytest tests/engine -q)."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLBACKEND", "Agg")

import pytest  # noqa: E402

from diacausal_engine.cohort import generate_cohort  # noqa: E402
from diacausal_engine.config import load_params  # noqa: E402


@pytest.fixture(scope="session")
def params():
    return load_params()


@pytest.fixture(scope="session")
def cohort(params):
    """A seeded 4,000-patient cohort shared by the estimation tests."""
    return generate_cohort(params, n=4000, seed=11)
