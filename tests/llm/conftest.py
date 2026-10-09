"""Shared fixtures for the local-model tests (run: python -m pytest tests/llm -q). No Ollama and no model are needed."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm_helpers import FakeOllama  # noqa: E402

from diacausal.config import load_rag_config  # noqa: E402
from diacausal.llm.providers import ollama  # noqa: E402


@pytest.fixture(scope="session")
def rag_cfg():
    return load_rag_config()


@pytest.fixture()
def llm_cfg():
    return ollama.load_llm_config()


@pytest.fixture()
def fake():
    """Start a fake server with `fake(reply)`; all of them are closed after the test."""
    made = []

    def start(reply):
        server = FakeOllama(reply)
        made.append(server)
        return server

    yield start
    for server in made:
        server.close()
