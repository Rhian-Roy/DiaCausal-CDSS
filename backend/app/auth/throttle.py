"""Slowing down password guessing (OWASP ASVS 2.2.1, NIST SP 800-63B 5.2.2).

Per account (stored on the user row, so an admin can unlock from the command line):
  from the 3rd failure the next try must wait 2 s, 4 s, 8 s ... (max 30 s);
  at 5 failures the account locks for 15 minutes, then unlocks on its own.
Per IP address (in memory): many failures from one address, across any accounts,
  first slow down and then block that address for a while.

Unknown user IDs are tracked in memory exactly like real ones, so the answers
("did not match", "N attempts left", "locked") are the same for both and nobody can
find out which user IDs exist.

Only attempts with a correct CAPTCHA count towards an account's lock, so locking a
colleague out needs a person solving CAPTCHAs, and the lock clears itself anyway.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.auth import clock
from app.db.models import User
from app.settings import (
    DELAY_FROM_FAILURE,
    DELAY_MAX_SECONDS,
    IP_BLOCK_AFTER_FAILURES,
    IP_DELAY_FROM_FAILURE,
    IP_WINDOW_SECONDS,
    LOCKOUT_AFTER_FAILURES,
    LOCKOUT_SECONDS,
)


@dataclass
class Counter:
    """Failures for one user ID that has no account (mirrors the columns on User)."""

    failed_attempts: int = 0
    last_failed_at: datetime | None = None
    locked_until: datetime | None = None


@dataclass
class _IpRecord:
    failures: list[datetime] = field(default_factory=list)
    blocked_until: datetime | None = None


_lock = threading.Lock()
_unknown: dict[str, Counter] = {}
_ips: dict[str, _IpRecord] = {}


def reset_memory() -> None:
    """Forget the in-memory counters (tests)."""
    with _lock:
        _unknown.clear()
        _ips.clear()


def counter_for(user: User | None, user_id: str) -> User | Counter:
    if user is not None:
        return user
    with _lock:
        return _unknown.setdefault(user_id, Counter())


def _delay(failures: int, start: int, cap: int) -> int:
    return 0 if failures < start else min(2 ** (failures - start + 1), cap)


def wait_seconds(counter: User | Counter) -> int:
    """How long before this account may try again (0 = now). Clears an expired lock."""
    now = clock.now()
    if counter.locked_until is not None:
        if now < counter.locked_until:
            return int((counter.locked_until - now).total_seconds()) + 1
        counter.locked_until, counter.failed_attempts, counter.last_failed_at = None, 0, None
    if counter.last_failed_at is None:
        return 0
    ready = counter.last_failed_at + timedelta(seconds=_delay(counter.failed_attempts, DELAY_FROM_FAILURE, DELAY_MAX_SECONDS))
    return max(0, int((ready - now).total_seconds()) + (1 if ready > now else 0))


def is_locked(counter: User | Counter) -> bool:
    return counter.locked_until is not None and clock.now() < counter.locked_until


def add_failure(counter: User | Counter) -> bool:
    """Count a failure; True if the account is now locked."""
    counter.failed_attempts += 1
    counter.last_failed_at = clock.now()
    if counter.failed_attempts >= LOCKOUT_AFTER_FAILURES:
        counter.locked_until = counter.last_failed_at + timedelta(seconds=LOCKOUT_SECONDS)
        return True
    return False


def attempts_left(counter: User | Counter) -> int:
    return max(0, LOCKOUT_AFTER_FAILURES - counter.failed_attempts)


def clear(counter: User | Counter) -> None:
    counter.failed_attempts, counter.last_failed_at, counter.locked_until = 0, None, None


def ip_wait_seconds(ip: str) -> int:
    now = clock.now()
    with _lock:
        record = _ips.setdefault(ip, _IpRecord())
        if record.blocked_until and now < record.blocked_until:
            return int((record.blocked_until - now).total_seconds()) + 1
        record.failures = [t for t in record.failures if now - t < timedelta(seconds=IP_WINDOW_SECONDS)]
        if not record.failures:
            return 0
        delay = _delay(len(record.failures), IP_DELAY_FROM_FAILURE, 60)
        ready = record.failures[-1] + timedelta(seconds=delay)
        return max(0, int((ready - now).total_seconds()) + (1 if ready > now else 0))


def ip_failure(ip: str) -> None:
    now = clock.now()
    with _lock:
        record = _ips.setdefault(ip, _IpRecord())
        record.failures.append(now)
        if len(record.failures) >= IP_BLOCK_AFTER_FAILURES:
            record.blocked_until = now + timedelta(seconds=IP_WINDOW_SECONDS)
            record.failures.clear()
