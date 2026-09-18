from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

TRACE = "abc12345"


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def chat_body() -> Callable[..., dict]:
    """Build a valid request body; override any piece with keyword arguments."""

    def build(text: str = "What should I add to metformin?", **overrides) -> dict:
        body = {
            "schema_version": "1.0",
            "client_trace_id": TRACE,
            "parts": [{"type": "text", "text": text}],
        }
        body.update(overrides)
        return body

    return build
