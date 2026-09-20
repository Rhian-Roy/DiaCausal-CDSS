"""Sessions: a random token in a cookie; the database keeps only its SHA-256.

Cookie `__Host-diacausal_session`: HttpOnly (page scripts cannot read it), Secure (HTTPS
only; browsers treat http://localhost as secure), SameSite=Strict (never sent from
another site), Path=/ and no Domain (the __Host- prefix makes the browser insist on these).

Two stages: "password_ok" after step 1 (user ID + password + CAPTCHA; lasts 5 minutes,
enough to type the 6-digit code) and "full" after step 2. The token is replaced at each
step, so a token seen before sign-in is useless afterwards.

CSRF: every state-changing request must send the session's csrf_token in the
X-CSRF-Token header. Another site cannot read it, so it cannot forge the request.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Response
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.auth import clock
from app.db.models import AuthSession, User
from app.settings import LOGIN_PENDING_SECONDS, SESSION_ABSOLUTE_SECONDS, SESSION_IDLE_SECONDS

COOKIE = "__Host-diacausal_session"
CSRF_HEADER = "X-CSRF-Token"
PASSWORD_OK = "password_ok"
FULL = "full"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class Current:
    session: AuthSession
    user: User


def start(db: Session, response: Response, user: User, stage: str, replacing: AuthSession | None = None) -> AuthSession:
    """Create a session (replacing an earlier one) and set its cookie."""
    if replacing is not None:
        db.delete(replacing)
    token = secrets.token_urlsafe(32)
    now = clock.now()
    session = AuthSession(
        token_hash=_hash(token), user_pk=user.id, stage=stage,
        csrf_token=secrets.token_urlsafe(32), created_at=now, last_seen_at=now,
    )
    db.add(session)
    db.commit()
    max_age = LOGIN_PENDING_SECONDS if stage == PASSWORD_OK else SESSION_ABSOLUTE_SECONDS
    response.set_cookie(COOKIE, token, max_age=max_age, path="/", secure=True, httponly=True, samesite="strict")
    return session


def clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")


def expired_reason(session: AuthSession) -> str | None:
    """"idle" / "absolute" / "pending" if the session has run out, else None."""
    now = clock.now()
    if session.stage == PASSWORD_OK:
        return "pending" if now - session.created_at > timedelta(seconds=LOGIN_PENDING_SECONDS) else None
    if now - session.created_at > timedelta(seconds=SESSION_ABSOLUTE_SECONDS):
        return "absolute"
    if now - session.last_seen_at > timedelta(seconds=SESSION_IDLE_SECONDS):
        return "idle"
    return None


def find(db: Session, token: str | None) -> AuthSession | None:
    return db.get(AuthSession, _hash(token)) if token else None


def end(db: Session, session: AuthSession) -> None:
    db.delete(session)
    db.commit()


def end_all_for(db: Session, user: User) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_pk == user.id))
    db.commit()


def touch(db: Session, session: AuthSession) -> None:
    session.last_seen_at = clock.now()
    db.commit()


def csrf_ok(session: AuthSession, header_value: str | None) -> bool:
    return bool(header_value) and secrets.compare_digest(header_value.encode(), session.csrf_token.encode())
