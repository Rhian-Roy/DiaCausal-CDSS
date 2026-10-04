"""Shared fixtures for the XAI tests (run: python -m pytest tests/xai -q; needs requirements-xai.txt for shap and lime)."""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLBACKEND", "Agg")

from diacausal.causal_inference.cohort import generate_cohort  # noqa: E402
from diacausal.config import load_params  # noqa: E402
from diacausal.guards.rules_loader import load_rules  # noqa: E402


@pytest.fixture(scope="session")
def params():
    return load_params()


@pytest.fixture(scope="session")
def rules():
    return load_rules()


@pytest.fixture(scope="session")
def cohorts(params):
    """A small train and test cohort, built the way the benchmark builds a replicate (test seed = seed + 100000)."""
    return generate_cohort(params, n=1500, seed=7), generate_cohort(params, n=800, seed=7 + 100_000)
