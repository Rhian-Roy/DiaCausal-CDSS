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


@pytest.fixture(scope="session")
def engine(tmp_path_factory):
    """The demo/API engine, fitted once on a smaller reference cohort to keep tests quick."""
    from diacausal_engine.recommend import Engine

    return Engine(n=3000)


@pytest.fixture()
def audit_file(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr("diacausal_engine.recommend.AUDIT_PATH", path)
    return path


TYPICAL = dict(age=52, sex="male", duration_years=5, hba1c=8.4, egfr=88, bmi=27.0)
EGFR40_PANCREATITIS = dict(age=60, sex="female", duration_years=8, hba1c=8.2, egfr=40, bmi=25.5, pancreatitis_history=True)
OLDER_HYPO = dict(age=80, sex="male", duration_years=15, hba1c=8.0, egfr=38, bmi=24.0, hypo_history=True, ascvd=True)
