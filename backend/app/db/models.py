"""The tables. Change them only together with a new migration in migrations/versions/.

Never stored anywhere: passwords (only their Argon2id hash), 6-digit codes, message text.
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """Stored as UTC; always read back with the time zone (SQLite would drop it)."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime: use app.auth.clock.now()")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    """One person. No shared accounts; no self-registration (admins create accounts)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # the login name, lower case
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16))  # "clinician" or "admin" (the whiteboard's "master login")
    password_hash: Mapped[str] = mapped_column(String(255))  # Argon2id, via pwdlib
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())

    # MFA (TOTP): the shared secret, encrypted with DIACAUSAL_SECRET_KEY (Fernet).
    totp_secret_enc: Mapped[str | None] = mapped_column(Text, default=None)
    mfa_enrolled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_totp_step: Mapped[int] = mapped_column(Integer, default=0)  # a code is accepted once only

    # Lockout (design 03).
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_failed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)

    # Intended-use acknowledgement (design 07), per user, with date and version.
    ack_version: Mapped[str | None] = mapped_column(String(16), default=None)
    ack_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)


class AuthSession(Base):
    """A signed-in browser. The cookie holds a random token; only its SHA-256 is stored."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_pk: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(16))  # "password_ok" (code still needed) or "full"
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime())


class CaptchaChallenge(Base):
    """One CAPTCHA: answered once, within 5 minutes. The answer never leaves the server."""

    __tablename__ = "captcha_challenges"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    answer: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    ip: Mapped[str] = mapped_column(String(64))


class AuditLog(Base):
    """Who did what, when. Never passwords, codes, CAPTCHA answers or message text."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    event: Mapped[str] = mapped_column(String(32), index=True)  # e.g. sign_in, sign_in_failed, chat
    user_id: Mapped[str | None] = mapped_column(String(64), index=True)  # the login name, if known
    request_id: Mapped[str] = mapped_column(String(36), unique=True)  # server-generated UUID
    client_trace_id: Mapped[str | None] = mapped_column(String(64), index=True)  # the browser's trace ID
    outcome: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(Text, default="")  # e.g. stage statuses; never secrets or text
    ip: Mapped[str | None] = mapped_column(String(64))
