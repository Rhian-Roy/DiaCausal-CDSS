"""Shared pieces for the pipeline tests: one fitted engine, one client, the three demo presets."""

import logging
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from diacausal.api.main import create_app  # noqa: E402
from diacausal.causal_inference.recommend import get_engine  # noqa: E402

FLAGS = dict(ascvd=False, heart_failure=False, ckd=False, past_hypo=False, past_dka=False, past_pancreatitis=False,
             type1=False, on_metformin=True)

# The three presets of the demo (demo/streamlit_app.py), written as v1 patients, each with a question.
PRESETS = {
    "typical": (dict(age=52, sex="M", duration_years=5.0, hba1c_pct=8.4, egfr=88.0, bmi=27.0),
                "Can SGLT2 inhibitors cause ketoacidosis?"),
    "egfr40_pancreatitis": (dict(age=60, sex="F", duration_years=8.0, hba1c_pct=8.2, egfr=40.0, bmi=25.5,
                                 past_pancreatitis=True, ckd=True),
                            "Is a DPP-4 inhibitor safe after pancreatitis?"),
    "older_hypo": (dict(age=80, sex="M", duration_years=15.0, hba1c_pct=8.0, egfr=38.0, bmi=24.0, past_hypo=True,
                        ascvd=True, ckd=True),
                   "Do sulfonylureas cause low blood sugar in older adults?"),
}


def body(patient: dict, question: str, request_id: str = "t1") -> dict:
    return {"schema_version": "1.0", "request_id": request_id, "patient": {**FLAGS, **patient}, "question": question}


@pytest.fixture(scope="session")
def engine():
    return get_engine()


@pytest.fixture()
def audit_file(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr("diacausal.causal_inference.recommend.AUDIT_PATH", path)
    return path


@pytest.fixture()
def client(engine, audit_file):
    with TestClient(create_app(engine)) as c:
        yield c


@pytest.fixture()
def trace(caplog):
    caplog.set_level(logging.DEBUG)  # every logger, every level
    return caplog
