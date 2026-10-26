"""Shared by every test folder: no test ever writes to the real trace store (logs/observability.sqlite3).

Each test that starts the API gets its own empty store in a temporary folder (diacausal/observability/store.py reads
DIACAUSAL_TRACE_DB when the server starts)."""

import pytest


@pytest.fixture(autouse=True)
def _temporary_trace_store(tmp_path, monkeypatch):
    monkeypatch.setenv("DIACAUSAL_TRACE_DB", str(tmp_path / "observability.sqlite3"))
