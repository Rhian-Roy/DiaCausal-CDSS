"""Sign-in: CAPTCHA, password, 6-digit code, lockout, sessions, CSRF, audit log.

Time is controlled with the `frozen` fixture, so timeouts and codes are tested exactly.
"""

import logging
from datetime import UTC, datetime, timedelta

import pyotp
import pytest
from sqlalchemy import select

from app.auth import clock, mfa
from app.auth import sessions as sess
from app.db.models import AuditLog, AuthSession, CaptchaChallenge, User
from app.settings import (
    CAPTCHA_SECONDS,
    INTENDED_USE_VERSION,
    LOCKOUT_SECONDS,
    LOGIN_PENDING_SECONDS,
    SESSION_ABSOLUTE_SECONDS,
    SESSION_IDLE_SECONDS,
)
from conftest import PASSWORD, TRACE, add_user

DID_NOT_MATCH = "Those details did not match"


class Clock:
    def __init__(self) -> None:
        self.time = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.time

    def forward(self, seconds: float) -> None:
        self.time += timedelta(seconds=seconds)


@pytest.fixture
def frozen(monkeypatch) -> Clock:
    fake = Clock()
    monkeypatch.setattr(clock, "now", fake)
    return fake


# ── helpers: one step of the sign-in each ────────────────────────────────────


def captcha(anon, db) -> tuple[str, str]:
    """A new CAPTCHA and its answer (read from the server's database, as only a test can)."""
    body = anon.get("/api/v1/auth/captcha").json()
    db.expire_all()
    return body["captcha_id"], db.get(CaptchaChallenge, body["captcha_id"]).answer


def login(anon, db, user_id="dr.rao", password=PASSWORD, answer=None, captcha_id=None):
    cid, right = captcha(anon, db)
    return anon.post("/api/v1/auth/login", json={
        "client_trace_id": TRACE, "user_id": user_id, "password": password,
        "captcha_id": captcha_id or cid, "captcha_answer": right if answer is None else answer,
    })


def secret_of(db, user_id="dr.rao") -> str:
    db.expire_all()
    return mfa.decrypt(db.scalar(select(User).where(User.user_id == user_id)).totp_secret_enc)


def code(secret: str) -> str:
    return pyotp.TOTP(secret).at(clock.now())


def post(anon, path, csrf, json=None):
    return anon.post(path, json=json, headers={sess.CSRF_HEADER: csrf})


def enrol(anon, db) -> dict:
    """First sign-in for a new account, up to and including the authenticator set-up."""
    csrf = login(anon, db).json()["csrf_token"]
    post(anon, "/api/v1/auth/mfa/setup", csrf)
    return post(anon, "/api/v1/auth/mfa/confirm", csrf, {"client_trace_id": TRACE, "code": code(secret_of(db))}).json()


def audit_rows(db, event=None):
    db.expire_all()
    query = select(AuditLog).order_by(AuditLog.id)
    return db.scalars(query.where(AuditLog.event == event) if event else query).all()


def chat(anon, csrf, text="HbA1c 8.4% on metformin"):
    return post(anon, "/api/v1/chat", csrf,
                {"schema_version": "1.0", "client_trace_id": TRACE, "parts": [{"type": "text", "text": text}]})


# ── a whole sign-in ──────────────────────────────────────────────────────────


def test_first_sign_in_sets_up_mfa_then_acknowledges_then_chats(anon, db, frozen):
    add_user()

    step1 = login(anon, db)
    assert step1.status_code == 200 and step1.json()["next"] == "mfa_setup"
    csrf = step1.json()["csrf_token"]
    assert chat(anon, csrf).status_code == 401  # half signed in is not signed in

    setup = post(anon, "/api/v1/auth/mfa/setup", csrf).json()
    assert setup["qr_image"].startswith("data:image/svg+xml;base64,")
    assert all(len(group) == 4 for group in setup["key_groups"]) and len(setup["key_groups"]) == 8
    assert "".join(setup["key_groups"]) == secret_of(db)

    info = post(anon, "/api/v1/auth/mfa/confirm", csrf, {"client_trace_id": TRACE, "code": code(secret_of(db))})
    assert info.status_code == 200
    info = info.json()
    assert info["stage"] == "full" and info["needs_acknowledgement"] is True
    csrf = info["csrf_token"]  # a new session, with a new token

    assert chat(anon, csrf).json()["error"] == "acknowledge_first"
    ack = post(anon, "/api/v1/auth/acknowledge", csrf, {"version": INTENDED_USE_VERSION})
    assert ack.json()["needs_acknowledgement"] is False
    db.expire_all()
    user = db.scalar(select(User))
    assert user.ack_version == INTENDED_USE_VERSION and user.ack_at == frozen.time

    reply = chat(anon, csrf)
    assert reply.status_code == 200 and reply.json()["outcome"] == "answered"


def test_second_sign_in_asks_for_the_code(anon, db, frozen):
    add_user()
    enrol(anon, db)
    anon.cookies.clear()
    frozen.forward(30)

    step1 = login(anon, db).json()
    assert step1["next"] == "mfa"
    info = post(anon, "/api/v1/auth/mfa", step1["csrf_token"], {"client_trace_id": TRACE, "code": code(secret_of(db))})
    assert info.status_code == 200 and info.json()["stage"] == "full"
    assert info.json()["display_name"] == "Dr Rao" and info.json()["role"] == "clinician"


def test_session_cookie_is_host_only_httponly_secure_strict(anon, db):
    add_user()
    cookie = login(anon, db).headers["set-cookie"]
    assert cookie.startswith("__Host-diacausal_session=")
    for attribute in ("HttpOnly", "Secure", "SameSite=strict", "Path=/"):
        assert attribute.lower() in cookie.lower()
    assert "domain" not in cookie.lower()


def test_session_token_changes_at_each_step(anon, db, frozen):
    add_user()
    login(anon, db)
    first = anon.cookies.get(sess.COOKIE)
    csrf = login(anon, db).json()["csrf_token"]
    post(anon, "/api/v1/auth/mfa/setup", csrf)
    post(anon, "/api/v1/auth/mfa/confirm", csrf, {"client_trace_id": TRACE, "code": code(secret_of(db))})
    assert anon.cookies.get(sess.COOKIE) not in (None, first)
    db.expire_all()
    assert len(db.scalars(select(AuthSession)).all()) == 2  # the abandoned first half-session + the full one


# ── wrong details: always the same answer ────────────────────────────────────


def test_wrong_password(anon, db):
    add_user()
    reply = login(anon, db, password="wrong password here")
    assert reply.status_code == 401
    assert reply.json() == {"error": "login_failed", "message": DID_NOT_MATCH, "attempts_left": 4}
    assert sess.COOKIE not in anon.cookies


def test_unknown_user_gets_exactly_the_same_answer(anon, db):
    add_user()
    wrong_password = login(anon, db, password="wrong password here")
    no_such_user = login(anon, db, user_id="nobody.here")
    assert no_such_user.status_code == wrong_password.status_code == 401
    assert no_such_user.json() == wrong_password.json()


def test_wrong_captcha(anon, db):
    add_user()
    reply = login(anon, db, answer="000000x")
    assert reply.status_code == 401 and reply.json()["message"] == DID_NOT_MATCH


def test_captcha_cannot_be_reused(anon, db):
    add_user()
    cid, answer = captcha(anon, db)
    first = anon.post("/api/v1/auth/login", json={"client_trace_id": TRACE, "user_id": "dr.rao",
                                                  "password": "wrong password here", "captcha_id": cid,
                                                  "captcha_answer": answer})
    again = anon.post("/api/v1/auth/login", json={"client_trace_id": TRACE, "user_id": "dr.rao",
                                                  "password": PASSWORD, "captcha_id": cid, "captcha_answer": answer})
    assert first.status_code == 401 and again.status_code == 401
    assert again.json()["message"] == DID_NOT_MATCH


def test_captcha_expires_after_5_minutes(anon, db, frozen):
    add_user()
    cid, answer = captcha(anon, db)
    frozen.forward(CAPTCHA_SECONDS + 1)
    reply = anon.post("/api/v1/auth/login", json={"client_trace_id": TRACE, "user_id": "dr.rao",
                                                  "password": PASSWORD, "captcha_id": cid, "captcha_answer": answer})
    assert reply.status_code == 401
    assert anon.get(f"/api/v1/auth/captcha/{cid}/audio").status_code == 404


def test_captcha_is_6_digits_as_a_png_image_and_a_wav_sound(anon, db):
    body = anon.get("/api/v1/auth/captcha").json()
    assert body["image"].startswith("data:image/png;base64,")
    answer = db.get(CaptchaChallenge, body["captcha_id"]).answer
    assert len(answer) == 6 and answer.isdigit()
    audio = anon.get(body["audio_url"])
    assert audio.status_code == 200 and audio.headers["content-type"] == "audio/wav"
    assert audio.content[:4] == b"RIFF" and audio.headers["cache-control"] == "no-store"
    assert answer not in str(body)


def test_captcha_answer_ignores_spaces(anon, db):
    add_user()
    cid, answer = captcha(anon, db)
    reply = anon.post("/api/v1/auth/login", json={"client_trace_id": TRACE, "user_id": " DR.RAO ",
                                                  "password": PASSWORD, "captcha_id": cid,
                                                  "captcha_answer": f"{answer[:3]} {answer[3:]}"})
    assert reply.status_code == 200


def test_wrong_code(anon, db, frozen):
    add_user()
    enrol(anon, db)
    anon.cookies.clear()
    frozen.forward(30)
    csrf = login(anon, db).json()["csrf_token"]
    right = code(secret_of(db))
    wrong = f"{(int(right) + 1) % 1_000_000:06d}"
    reply = post(anon, "/api/v1/auth/mfa", csrf, {"client_trace_id": TRACE, "code": wrong})
    assert reply.status_code == 401
    assert reply.json() == {"error": "code_failed", "message": "That code did not work", "attempts_left": 4}


def test_a_code_cannot_be_used_twice(anon, db, frozen):
    add_user()
    enrol(anon, db)  # uses the code for this 30-second step
    anon.cookies.clear()
    csrf = login(anon, db).json()["csrf_token"]
    reply = post(anon, "/api/v1/auth/mfa", csrf, {"client_trace_id": TRACE, "code": code(secret_of(db))})
    assert reply.status_code == 401  # same step as before: refused
    frozen.forward(30)
    reply = post(anon, "/api/v1/auth/mfa", csrf, {"client_trace_id": TRACE, "code": code(secret_of(db))})
    assert reply.status_code == 200


def test_a_code_from_the_previous_step_still_works_once(anon, db, frozen):
    add_user()
    enrol(anon, db)
    anon.cookies.clear()
    frozen.forward(60)
    previous = pyotp.TOTP(secret_of(db)).at(frozen.time - timedelta(seconds=30))
    two_back = pyotp.TOTP(secret_of(db)).at(frozen.time - timedelta(seconds=60))
    csrf = login(anon, db).json()["csrf_token"]
    assert post(anon, "/api/v1/auth/mfa", csrf, {"client_trace_id": TRACE, "code": two_back}).status_code == 401
    assert post(anon, "/api/v1/auth/mfa", csrf, {"client_trace_id": TRACE, "code": previous}).status_code == 200


def test_mfa_secret_is_encrypted_in_the_database(anon, db):
    add_user()
    csrf = login(anon, db).json()["csrf_token"]
    post(anon, "/api/v1/auth/mfa/setup", csrf)
    db.expire_all()
    stored = db.scalar(select(User)).totp_secret_enc
    assert secret_of(db) not in stored and stored.startswith("gAAAA")  # Fernet token


def test_the_code_step_needs_the_password_step_first(anon):
    reply = anon.post("/api/v1/auth/mfa", json={"client_trace_id": TRACE, "code": "123456"})
    assert reply.status_code == 401


def test_half_sign_in_expires_after_5_minutes(anon, db, frozen):
    add_user()
    enrol(anon, db)
    anon.cookies.clear()
    csrf = login(anon, db).json()["csrf_token"]
    frozen.forward(LOGIN_PENDING_SECONDS + 1)
    reply = post(anon, "/api/v1/auth/mfa", csrf, {"client_trace_id": TRACE, "code": code(secret_of(db))})
    assert reply.status_code == 401 and reply.json()["error"] == "session_expired"


# ── lockout, delay, unlock ───────────────────────────────────────────────────


def fail_times(anon, db, frozen, n, user_id="dr.rao"):
    replies = []
    for _ in range(n):
        replies.append(login(anon, db, user_id=user_id, password="wrong password here"))
        frozen.forward(31)  # wait out the growing delay
    return replies


def test_five_wrong_passwords_lock_the_account(anon, db, frozen):
    add_user()
    replies = fail_times(anon, db, frozen, 5)
    assert [r.json().get("attempts_left") for r in replies[:4]] == [4, 3, 2, 1]
    assert replies[4].status_code == 423 and replies[4].json()["error"] == "locked"
    locked = login(anon, db)  # even the right password is refused now
    assert locked.status_code == 423 and "minutes" in locked.json()["message"]
    assert len(audit_rows(db, "lockout")) == 1


def test_an_unknown_user_id_locks_the_same_way(anon, db, frozen):
    replies = fail_times(anon, db, frozen, 5, user_id="nobody.here")
    assert replies[4].status_code == 423


def test_the_lock_clears_on_its_own(anon, db, frozen):
    add_user()
    fail_times(anon, db, frozen, 5)
    frozen.forward(LOCKOUT_SECONDS + 1)
    assert login(anon, db).status_code == 200


def test_admin_unlock(anon, db, frozen):
    from app.auth import cli

    add_user()
    admin = add_user("admin.one", role="admin", display_name="Admin")
    fail_times(anon, db, frozen, 5)
    print(cli.run(db, "unlock", "dr.rao", db.get(User, admin.id)))
    assert login(anon, db).status_code == 200
    assert audit_rows(db, "admin_unlock")[0].detail == "by admin admin.one"


def test_wrong_captchas_do_not_lock_the_account(anon, db, frozen):
    """So a bot that cannot solve CAPTCHAs cannot lock a colleague out."""
    add_user()
    for _ in range(8):
        assert login(anon, db, answer="999999x").status_code == 401
    assert login(anon, db).status_code == 200


def test_growing_delay_after_the_third_failure(anon, db, frozen):
    add_user()
    for _ in range(3):
        login(anon, db, password="wrong password here")
    reply = login(anon, db, password="wrong password here")
    assert reply.status_code == 429 and reply.json()["error"] == "slow_down"
    assert reply.headers["retry-after"] == "3"
    frozen.forward(3)
    assert login(anon, db).status_code == 200


def test_wrong_codes_lock_too_and_end_the_half_session(anon, db, frozen):
    add_user()
    enrol(anon, db)
    anon.cookies.clear()
    csrf = login(anon, db).json()["csrf_token"]
    for _ in range(4):
        post(anon, "/api/v1/auth/mfa", csrf, {"client_trace_id": TRACE, "code": "000000"})
        frozen.forward(31)
    reply = post(anon, "/api/v1/auth/mfa", csrf, {"client_trace_id": TRACE, "code": "000000"})
    assert reply.status_code == 423


def test_disabled_account_cannot_sign_in(anon, db):
    add_user(disabled=True)
    reply = login(anon, db)
    assert reply.status_code == 401 and reply.json()["message"] == DID_NOT_MATCH


# ── the chat endpoint is protected ───────────────────────────────────────────


def test_chat_without_a_session_is_401(anon, chat_body):
    reply = anon.post("/api/v1/chat", json=chat_body())
    assert reply.status_code == 401 and reply.json()["error"] == "not_signed_in"


def test_invalid_chat_without_a_session_is_401_not_422(anon, chat_body):
    """Strangers learn nothing about the contract."""
    assert anon.post("/api/v1/chat", json=chat_body(parts=[{"type": "image"}])).status_code == 401


def test_chat_without_the_csrf_header_is_403(client, chat_body):
    del client.headers[sess.CSRF_HEADER]
    reply = client.post("/api/v1/chat", json=chat_body())
    assert reply.status_code == 403 and reply.json()["error"] == "csrf_failed"


def test_chat_with_a_wrong_csrf_token_is_403(client, chat_body):
    client.headers[sess.CSRF_HEADER] = "not-the-token"
    assert client.post("/api/v1/chat", json=chat_body()).status_code == 403


def test_logout_needs_the_csrf_header(client):
    del client.headers[sess.CSRF_HEADER]
    assert client.post("/api/v1/auth/logout").status_code == 403


def test_idle_timeout(client, chat_body, frozen):
    client.post("/api/v1/chat", json=chat_body())  # activity now
    frozen.forward(SESSION_IDLE_SECONDS - 5)
    assert client.post("/api/v1/chat", json=chat_body()).status_code == 200  # still in time; counts as activity
    frozen.forward(SESSION_IDLE_SECONDS + 1)
    reply = client.post("/api/v1/chat", json=chat_body())
    assert reply.status_code == 401 and reply.json()["error"] == "session_expired"


def test_absolute_timeout_even_when_active(client, chat_body, frozen, db):
    started, step = frozen.time, 10 * 60
    while (frozen.time - started).total_seconds() + step < SESSION_ABSOLUTE_SECONDS:  # active all day
        frozen.forward(step)
        assert client.post("/api/v1/auth/keepalive").status_code == 200
    frozen.time = started + timedelta(seconds=SESSION_ABSOLUTE_SECONDS + 1)  # just past 8 h, never idle
    reply = client.post("/api/v1/chat", json=chat_body())
    assert reply.status_code == 401 and reply.json()["error"] == "session_expired"
    assert audit_rows(db, "session_timeout")[0].outcome == "absolute"


def test_idle_timeout_is_recorded_as_idle(client, chat_body, frozen, db):
    frozen.forward(SESSION_IDLE_SECONDS + 1)
    client.post("/api/v1/chat", json=chat_body())
    assert audit_rows(db, "session_timeout")[0].outcome == "idle"


def test_keepalive_resets_the_idle_timer(client, chat_body, frozen):
    client.post("/api/v1/chat", json=chat_body())
    frozen.forward(SESSION_IDLE_SECONDS - 10)
    assert client.post("/api/v1/auth/keepalive").status_code == 200
    frozen.forward(SESSION_IDLE_SECONDS - 10)
    assert client.post("/api/v1/chat", json=chat_body()).status_code == 200


def test_logout_ends_the_session_on_the_server(client, chat_body, db):
    token = client.cookies.get(sess.COOKIE)
    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.set(sess.COOKIE, token)  # even if the browser kept the old cookie ...
    assert client.post("/api/v1/chat", json=chat_body()).status_code == 401  # ... it no longer works
    assert audit_rows(db, "sign_out")


def test_me_says_who_is_signed_in(client):
    info = client.get("/api/v1/auth/me").json()
    assert info["user_id"] == "dr.rao" and info["stage"] == "full"
    assert info["idle_timeout_seconds"] == SESSION_IDLE_SECONDS and info["warning_seconds"] == 120


def test_me_without_a_session_is_401(anon):
    assert anon.get("/api/v1/auth/me").status_code == 401


# ── audit log and logs ───────────────────────────────────────────────────────


def test_every_chat_request_is_audited_with_request_id_and_trace_id(client, chat_body, db):
    reply = client.post("/api/v1/chat", json=chat_body("Patient Ramesh Kumar, HbA1c 8.4")).json()
    row = audit_rows(db, "chat")[0]
    assert row.request_id == reply["request_id"] and len(row.request_id) == 36
    assert row.client_trace_id == TRACE and row.user_id == "dr.rao" and row.outcome == "answered"
    assert row.detail.startswith("backend_guard=passed,clinical_guardrails=skipped")
    assert "Ramesh" not in str([vars(r) for r in audit_rows(db)])


def test_blocked_chat_is_audited_too(client, chat_body, db):
    client.post("/api/v1/chat", json=chat_body("She is pregnant, 28 weeks"))
    row = audit_rows(db, "chat")[0]
    assert row.outcome == "blocked" and "backend_guard=blocked" in row.detail


def test_sign_in_success_and_failure_are_audited(anon, db, frozen):
    add_user()
    login(anon, db, password="wrong password here")
    frozen.forward(31)
    enrol(anon, db)
    events = [(r.event, r.outcome) for r in audit_rows(db)]
    assert ("sign_in_failed", "password") in events and ("sign_in", "passed") in events
    assert all(r.client_trace_id == TRACE for r in audit_rows(db) if r.event.startswith("sign_in"))


def test_no_secret_is_ever_logged_or_audited(anon, db, frozen, caplog):
    caplog.set_level(logging.DEBUG)
    add_user()
    cid, answer = captcha(anon, db)
    csrf = anon.post("/api/v1/auth/login", json={"client_trace_id": TRACE, "user_id": "dr.rao", "password": PASSWORD,
                                                 "captcha_id": cid, "captcha_answer": answer}).json()["csrf_token"]
    post(anon, "/api/v1/auth/mfa/setup", csrf)
    one_time = code(secret_of(db))
    info = post(anon, "/api/v1/auth/mfa/confirm", csrf, {"client_trace_id": TRACE, "code": one_time}).json()
    post(anon, "/api/v1/auth/acknowledge", info["csrf_token"], {"version": INTENDED_USE_VERSION})
    chat(anon, info["csrf_token"], "secret-words ZEBRA99 in the question")

    everything = caplog.text + str([vars(r) for r in audit_rows(db)])
    for secret in (PASSWORD, answer, one_time, secret_of(db), "ZEBRA99", csrf, info["csrf_token"]):
        assert secret not in everything
    assert "[abc12345] login: captcha passed" in caplog.text or "login: captcha passed" in caplog.text


def test_login_log_lines_carry_the_trace_id(anon, db, caplog):
    caplog.set_level(logging.INFO, logger="diacausal")
    add_user()
    login(anon, db)
    lines = {r.getMessage(): r.trace_id for r in caplog.records if r.name == "diacausal"}
    assert lines["login: captcha passed"] == TRACE and lines["login: password passed"] == TRACE
