"""FastAPI dependencies that protect endpoints.

    require_clinician    fully signed in (password + code), session not timed out,
                         CSRF header present, intended use acknowledged
    require_csrf_session any live session (also half-way through sign-in) + CSRF header

Failures are JSON like {"error": "not_signed_in", "message": "..."} with 401 or 403.
"""

from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import audit, sessions
from app.auth.schemas import AuthError
from app.db import get_db
from app.db.models import AuthSession, User
from app.settings import INTENDED_USE_VERSION
from app.tracing import log


class AuthProblem(Exception):
    def __init__(self, status: int, error: str, message: str, clear_cookie: bool = False, **extra) -> None:
        self.status, self.body = status, AuthError(error=error, message=message, **extra)
        self.clear_cookie = clear_cookie  # only when the session is gone for good


async def auth_problem_handler(_request: Request, exc: AuthProblem) -> JSONResponse:
    response = JSONResponse(status_code=exc.status, content=exc.body.model_dump(exclude_none=True))
    if exc.body.retry_after_seconds:
        response.headers["Retry-After"] = str(exc.body.retry_after_seconds)
    if exc.clear_cookie:
        sessions.clear_cookie(response)
    return response


NOT_SIGNED_IN = "Please sign in."


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@dataclass
class Signed:
    session: AuthSession
    user: User


def _live_session(request: Request, db: Session) -> Signed:
    session = sessions.find(db, request.cookies.get(sessions.COOKIE))
    if session is None:
        raise AuthProblem(401, "not_signed_in", NOT_SIGNED_IN, clear_cookie=True)
    user = db.get(User, session.user_pk)
    if user is None or user.disabled:
        sessions.end(db, session)
        raise AuthProblem(401, "not_signed_in", NOT_SIGNED_IN, clear_cookie=True)
    if reason := sessions.expired_reason(session):
        sessions.end(db, session)
        audit.record(db, "session_timeout", reason, user_id=user.user_id, ip=client_ip(request))
        log.info("session ended: %s timeout", reason)
        raise AuthProblem(401, "session_expired", "Your session has ended. Please sign in again.", clear_cookie=True)
    return Signed(session, user)


def _check_csrf(request: Request, session: AuthSession) -> None:
    if not sessions.csrf_ok(session, request.headers.get(sessions.CSRF_HEADER)):
        raise AuthProblem(403, "csrf_failed", "This request is missing its security token. Reload the page.")


def current_session(request: Request, db: Session = Depends(get_db)) -> Signed:
    """Any live session, no CSRF check (for reading, e.g. GET /auth/me)."""
    return _live_session(request, db)


def require_csrf_session(request: Request, db: Session = Depends(get_db)) -> Signed:
    signed = _live_session(request, db)
    _check_csrf(request, signed.session)
    return signed


def require_clinician(request: Request, db: Session = Depends(get_db)) -> Signed:
    signed = _live_session(request, db)
    if signed.session.stage != sessions.FULL:
        raise AuthProblem(401, "not_signed_in", NOT_SIGNED_IN)
    _check_csrf(request, signed.session)
    if signed.user.ack_version != INTENDED_USE_VERSION:
        raise AuthProblem(403, "acknowledge_first", "Please read and acknowledge the intended use first.")
    sessions.touch(db, signed.session)
    return signed
