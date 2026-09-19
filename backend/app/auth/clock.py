"""The current time, in one place so tests can move it forward (timeouts, lockouts, codes)."""

from datetime import UTC, datetime


def now() -> datetime:
    return datetime.now(UTC)
