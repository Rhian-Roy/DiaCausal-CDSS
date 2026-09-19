"""What the sign-in endpoints accept and return (mirrored in frontend/src/features/auth/api.ts)."""

from typing import Literal

from pydantic import Field

from app.schemas import StrictModel
from app.settings import TRACE_ID_PATTERN

Stage = Literal["password_ok", "full"]


class CaptchaResponse(StrictModel):
    captcha_id: str
    image: str  # data: URL of a PNG showing 6 digits
    audio_url: str  # the same 6 digits, spoken (WAV)


class LoginRequest(StrictModel):
    client_trace_id: str = Field(pattern=TRACE_ID_PATTERN)
    user_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)
    captcha_id: str = Field(min_length=1, max_length=64)
    captcha_answer: str = Field(min_length=1, max_length=16)


class LoginResponse(StrictModel):
    next: Literal["mfa", "mfa_setup"]  # step 2: enter a code, or set up the authenticator first
    user_id: str
    csrf_token: str


class CodeRequest(StrictModel):
    client_trace_id: str = Field(pattern=TRACE_ID_PATTERN)
    code: str = Field(min_length=1, max_length=16)


class MfaSetupResponse(StrictModel):
    qr_image: str  # data: URL of an SVG QR code for the authenticator app
    key_groups: list[str]  # the same key, in groups of 4, to type by hand
    issuer: str
    account: str


class AcknowledgeRequest(StrictModel):
    version: str = Field(min_length=1, max_length=16)


class SessionInfo(StrictModel):
    user_id: str
    display_name: str
    role: Literal["clinician", "admin"]
    stage: Stage
    needs_mfa_setup: bool
    needs_acknowledgement: bool
    intended_use_version: str
    csrf_token: str
    idle_timeout_seconds: int
    warning_seconds: int


class AuthError(StrictModel):
    """Every sign-in failure. `message` is deliberately the same for every wrong detail."""

    error: Literal[
        "login_failed", "code_failed", "locked", "slow_down", "not_signed_in", "session_expired",
        "csrf_failed", "acknowledge_first", "captcha_expired", "wrong_step",
    ]
    message: str
    attempts_left: int | None = None
    retry_after_seconds: int | None = None
