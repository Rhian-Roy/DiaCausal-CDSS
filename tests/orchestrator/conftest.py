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
