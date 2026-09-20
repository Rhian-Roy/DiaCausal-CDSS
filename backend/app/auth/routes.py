"""Sign-in endpoints, under /api/v1/auth. One full sign-in (see docs/explain/04-login-and-mfa.md):

    GET  captcha                  new CAPTCHA (image; audio at captcha/{id}/audio)
    POST login                    step 1: user ID + password + CAPTCHA  -> half signed in
    POST mfa/setup, mfa/confirm   first time only: show QR, confirm a code -> signed in
    POST mfa                      step 2: 6-digit code                  -> signed in
    POST acknowledge              intended use read (design 07)
    GET  me, POST keepalive, POST logout

Every wrong detail gets the same answer: "Those details did not match".
Never logged or stored: passwords, codes, CAPTCHA answers.
"""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import audit, captcha, clock, mfa, passwords, sessions, throttle
from app.auth.deps import AuthProblem, Signed, client_ip, current_session, require_csrf_session
from app.auth.schemas import (
    AcknowledgeRequest,
    AuthError,
    CaptchaResponse,
    CodeRequest,
    LoginRequest,
    LoginResponse,
    MfaSetupResponse,
    SessionInfo,
)
from app.db import get_db
from app.db.models import User
from app.settings import INTENDED_USE_VERSION, SESSION_IDLE_SECONDS, SESSION_WARNING_SECONDS
from app.tracing import log, trace_context

router = APIRouter(prefix="/api/v1/auth", tags=["sign-in"])

DID_NOT_MATCH = "Those details did not match"
CODE_FAILED = "That code did not work"
ERRORS = {s: {"model": AuthError} for s in (401, 403, 423, 429)}


def normalise(user_id: str) -> str:
    return user_id.strip().casefold()


def session_info(signed: Signed) -> SessionInfo:
    user, session = signed.user, signed.session
    return SessionInfo(
        user_id=user.user_id, display_name=user.display_name, role=user.role,  # type: ignore[arg-type]
        stage=session.stage,  # type: ignore[arg-type]
        needs_mfa_setup=not user.mfa_enrolled,
        needs_acknowledgement=user.ack_version != INTENDED_USE_VERSION,
        intended_use_version=INTENDED_USE_VERSION, csrf_token=session.csrf_token,
        idle_timeout_seconds=SESSION_IDLE_SECONDS, warning_seconds=SESSION_WARNING_SECONDS,
    )


def _locked(counter) -> AuthProblem:
    wait = throttle.wait_seconds(counter)
    minutes = max(1, (wait + 59) // 60)
    return AuthProblem(
        423, "locked",
        f"Too many attempts. Try again in {minutes} minute{'s' if minutes > 1 else ''} or ask your administrator.",
        retry_after_seconds=wait,
    )


def _slow_down(wait: int) -> AuthProblem:
    return AuthProblem(429, "slow_down", f"Too many attempts. Wait {wait} seconds, then try again.",
                       retry_after_seconds=wait)


# ── CAPTCHA ──────────────────────────────────────────────────────────────────


@router.get("/captcha", responses={429: {"model": AuthError}})
def new_captcha(request: Request, response: Response, db: Session = Depends(get_db)) -> CaptchaResponse:
    """A new CAPTCHA. The answer stays on the server; it works once, for 5 minutes."""
    try:
        challenge = captcha.provider.new_challenge(db, client_ip(request))
    except captcha.TooManyChallenges:
        raise _slow_down(60) from None
    response.headers["Cache-Control"] = "no-store"
    return CaptchaResponse(
        captcha_id=challenge.id, image=challenge.image_data_url,
        audio_url=f"/api/v1/auth/captcha/{challenge.id}/audio",
    )


@router.get("/captcha/{captcha_id}/audio", response_class=Response,
            responses={200: {"content": {"audio/wav": {}}}, 404: {"model": AuthError}})
def captcha_audio(captcha_id: str, db: Session = Depends(get_db)) -> Response:
    """The same 6 digits, spoken, for people who cannot read the image."""
    audio = captcha.provider.audio(db, captcha_id)
    if audio is None:
        raise AuthProblem(404, "captcha_expired", "This picture has expired. Choose \"New image\".")
    return Response(audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})


# ── step 1: user ID + password + CAPTCHA ─────────────────────────────────────


@router.post("/login", responses=ERRORS)
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    """Step 1 of 2. On success the browser is half signed in (5 minutes to enter the code)."""
    ip = client_ip(request)
    user_id = normalise(body.user_id)
    with trace_context(body.client_trace_id):

        def fail(detail: str, problem: AuthProblem) -> AuthProblem:
            audit.record(db, "sign_in_failed", detail, user_id=user_id, client_trace_id=body.client_trace_id, ip=ip)
            log.warning("login failed (%s)", detail)
            return problem

        if wait := throttle.ip_wait_seconds(ip):
            raise fail("ip_throttled", _slow_down(wait))

        user = db.scalar(select(User).where(User.user_id == user_id))
        counter = throttle.counter_for(user, user_id)
        if throttle.is_locked(counter):
            raise fail("locked", _locked(counter))
        if wait := throttle.wait_seconds(counter):
            db.commit()
            raise fail("throttled", _slow_down(wait))

        if not captcha.provider.verify(db, body.captcha_id, body.captcha_answer):
            throttle.ip_failure(ip)  # a wrong CAPTCHA never counts towards the account's lock
            raise fail("captcha", AuthProblem(401, "login_failed", DID_NOT_MATCH,
                                              attempts_left=throttle.attempts_left(counter)))
        log.info("login: captcha passed")

        password_ok = passwords.verify_password(body.password, user.password_hash if user else None)
        if not password_ok or user is None or user.disabled:
            throttle.ip_failure(ip)
            now_locked = throttle.add_failure(counter)
            db.commit()
            if now_locked:
                audit.record(db, "lockout", "locked", user_id=user_id, client_trace_id=body.client_trace_id, ip=ip)
                raise fail("password", _locked(counter))
            raise fail("password", AuthProblem(401, "login_failed", DID_NOT_MATCH,
                                               attempts_left=throttle.attempts_left(counter)))
        log.info("login: password passed")

        session = sessions.start(db, request, response, user, sessions.PASSWORD_OK)
        audit.record(db, "sign_in_step1", "passed", user_id=user_id, client_trace_id=body.client_trace_id, ip=ip)
        return LoginResponse(next="mfa" if user.mfa_enrolled else "mfa_setup", user_id=user.user_id,
                             csrf_token=session.csrf_token)


# ── step 2: 6-digit code ─────────────────────────────────────────────────────


def _half_signed_in(signed: Signed) -> None:
    if signed.session.stage != sessions.PASSWORD_OK:
        raise AuthProblem(409, "wrong_step", "You are already signed in.")


def _check_code(db: Session, signed: Signed, body: CodeRequest, request: Request, response: Response,
                enrolling: bool) -> SessionInfo:
    user, ip = signed.user, client_ip(request)
    with trace_context(body.client_trace_id):
        if throttle.is_locked(user):
            sessions.end(db, signed.session)
            raise _locked(user)
        if wait := throttle.wait_seconds(user):
            db.commit()
            raise _slow_down(wait)
        if user.totp_secret_enc is None:
            raise AuthProblem(409, "wrong_step", "Set up your authenticator app first.")

        step = mfa.matching_step(mfa.decrypt(user.totp_secret_enc), body.code.strip(), user.last_totp_step)
        if step is None:
            throttle.ip_failure(ip)
            now_locked = throttle.add_failure(user)
            db.commit()
            audit.record(db, "sign_in_failed", "mfa", user_id=user.user_id, client_trace_id=body.client_trace_id, ip=ip)
            log.warning("login failed (mfa)")
            if now_locked:
                audit.record(db, "lockout", "locked", user_id=user.user_id, client_trace_id=body.client_trace_id, ip=ip)
                sessions.end(db, signed.session)
                raise _locked(user)
            raise AuthProblem(401, "code_failed", CODE_FAILED, attempts_left=throttle.attempts_left(user))

        user.last_totp_step = step  # this code (and any older one) will not work again
        if enrolling:
            user.mfa_enrolled = True
            audit.record(db, "mfa_enrolled", "passed", user_id=user.user_id, client_trace_id=body.client_trace_id, ip=ip)
        throttle.clear(user)
        full = sessions.start(db, request, response, user, sessions.FULL, replacing=signed.session)
        log.info("login: mfa passed")
        audit.record(db, "sign_in", "passed", user_id=user.user_id, client_trace_id=body.client_trace_id, ip=ip)
        return session_info(Signed(full, user))


@router.post("/mfa/setup", responses=ERRORS)
def mfa_setup(signed: Signed = Depends(require_csrf_session), db: Session = Depends(get_db)) -> MfaSetupResponse:
    """First sign-in only: the QR code and key for the authenticator app (design 06)."""
    _half_signed_in(signed)
    user = signed.user
    if user.mfa_enrolled:
        raise AuthProblem(409, "wrong_step", "Your authenticator app is already set up.")
    if user.totp_secret_enc is None:
        # Two requests can arrive at once (a browser that retries, or React's development
        # double-render). Only the first may create the secret, or one browser would show
        # a QR code for a secret the database has already replaced. The condition in the
        # UPDATE makes the database decide the winner; then we read back what it kept.
        db.execute(
            update(User)
            .where(User.id == user.id, User.totp_secret_enc.is_(None))
            .values(totp_secret_enc=mfa.encrypt(mfa.new_secret()))
        )
        db.commit()
        db.refresh(user)
    secret = mfa.decrypt(user.totp_secret_enc)
    return MfaSetupResponse(
        qr_image=mfa.qr_svg_data_url(mfa.provisioning_uri(secret, user.user_id)),
        key_groups=mfa.key_groups(secret), issuer=mfa.ISSUER, account=user.user_id,
    )


@router.post("/mfa/confirm", responses=ERRORS)
def mfa_confirm(body: CodeRequest, request: Request, response: Response,
                signed: Signed = Depends(require_csrf_session), db: Session = Depends(get_db)) -> SessionInfo:
    """First sign-in only: a code from the newly set-up app proves it works; then signed in."""
    _half_signed_in(signed)
    if signed.user.mfa_enrolled:
        raise AuthProblem(409, "wrong_step", "Your authenticator app is already set up.")
    return _check_code(db, signed, body, request, response, enrolling=True)


@router.post("/mfa", responses=ERRORS)
def mfa_verify(body: CodeRequest, request: Request, response: Response,
               signed: Signed = Depends(require_csrf_session), db: Session = Depends(get_db)) -> SessionInfo:
    """Step 2 of 2: the 6-digit code from the authenticator app."""
    _half_signed_in(signed)
    if not signed.user.mfa_enrolled:
        raise AuthProblem(409, "wrong_step", "Set up your authenticator app first.")
    return _check_code(db, signed, body, request, response, enrolling=False)


# ── after sign-in ────────────────────────────────────────────────────────────


def _require_full(signed: Signed) -> None:
    if signed.session.stage != sessions.FULL:
        raise AuthProblem(401, "not_signed_in", "Please sign in.")


@router.post("/acknowledge", responses=ERRORS)
def acknowledge(body: AcknowledgeRequest, request: Request, signed: Signed = Depends(require_csrf_session),
                db: Session = Depends(get_db)) -> SessionInfo:
    """"I understand" on the intended-use page (design 07): stored with date and version."""
    _require_full(signed)
    if body.version != INTENDED_USE_VERSION:
        raise AuthProblem(409, "wrong_step", "The intended-use text has changed. Reload the page.")
    user = signed.user
    user.ack_version, user.ack_at = INTENDED_USE_VERSION, clock.now()
    sessions.touch(db, signed.session)
    audit.record(db, "acknowledged", f"version {INTENDED_USE_VERSION}", user_id=user.user_id, ip=client_ip(request))
    return session_info(signed)


@router.get("/me", responses=ERRORS)
def me(response: Response, signed: Signed = Depends(current_session)) -> SessionInfo:
    """Who is signed in (the page asks on load). 401 if nobody."""
    response.headers["Cache-Control"] = "no-store"
    return session_info(signed)


@router.post("/keepalive", responses=ERRORS)
def keepalive(signed: Signed = Depends(require_csrf_session), db: Session = Depends(get_db)) -> SessionInfo:
    """"Stay signed in" on the timeout warning (design 08)."""
    _require_full(signed)
    sessions.touch(db, signed.session)
    return session_info(signed)


@router.post("/logout", status_code=204, responses=ERRORS)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> Response:
    """Sign out: the session is deleted on the server, not just forgotten by the browser."""
    session = sessions.find(db, sessions.token_from(request))
    if session is not None:
        if not sessions.csrf_ok(session, request.headers.get(sessions.CSRF_HEADER)):
            raise AuthProblem(403, "csrf_failed", "This request is missing its security token. Reload the page.")
        user = db.get(User, session.user_pk)
        sessions.end(db, session)
        audit.record(db, "sign_out", "passed", user_id=user.user_id if user else None, ip=client_ip(request))
    response.status_code = 204
    sessions.clear_cookie(response)
    return response

