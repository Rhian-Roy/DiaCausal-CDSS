import os
import secrets
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

# Before the app is imported: a throwaway secret key and database for the whole test run.
os.environ["DIACAUSAL_SECRET_KEY"] = Fernet.generate_key().decode()
_TMP = Path(tempfile.mkdtemp(prefix="diacausal-tests-"))
TEST_DB = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["DIACAUSAL_DATABASE_URL"] = TEST_DB

from app import db as database  # noqa: E402
from app.auth import clock, passwords, sessions, throttle  # noqa: E402
from app.db.models import AuditLog, AuthSession, CaptchaChallenge, User  # noqa: E402
from app.main import create_app  # noqa: E402
from app.settings import INTENDED_USE_VERSION  # noqa: E402

TRACE = "abc12345"
PASSWORD = "correct horse battery staple"
# Argon2id is slow on purpose; hash the test password once, not in every test.
PASSWORD_HASH = passwords.hash_password(PASSWORD)
# Browsers only send a Secure cookie over HTTPS, so the test client pretends to be HTTPS.
BASE_URL = "https://testserver"


@pytest.fixture(autouse=True)
def clean_database() -> Iterator[None]:
    """Every test starts with empty tables and forgotten rate-limit counters."""
    database.configure(TEST_DB)
    with database.new_session() as db:
        for table in (AuditLog, AuthSession, CaptchaChallenge, User):
            db.query(table).delete()
        db.commit()
    throttle.reset_memory()
    yield


@pytest.fixture
def db():
    with database.new_session() as session:
        yield session


def add_user(user_id: str = "dr.rao", role: str = "clinician", **fields) -> User:
    with database.new_session() as db:
        user = User(
            user_id=user_id, display_name=fields.pop("display_name", "Dr Rao"), role=role,
            password_hash=PASSWORD_HASH, created_at=clock.now(), **fields,
        )
        db.add(user)
        db.commit()
        return user


@pytest.fixture
def anon() -> TestClient:
    """A browser that is not signed in."""
    return TestClient(create_app(TEST_DB), base_url=BASE_URL)


@pytest.fixture
def client() -> TestClient:
    """A browser that is fully signed in (password + code done, intended use acknowledged),
    sending its CSRF token on every request. Made directly in the database for speed; the
    real step-by-step sign-in is tested in test_auth.py."""
    user = add_user(mfa_enrolled=True, ack_version=INTENDED_USE_VERSION, ack_at=clock.now())
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with database.new_session() as db:
        now = clock.now()
        db.add(AuthSession(token_hash=sessions._hash(token), user_pk=user.id, stage=sessions.FULL,
                           csrf_token=csrf, created_at=now, last_seen_at=now))
        db.commit()
    test_client = TestClient(create_app(TEST_DB), base_url=BASE_URL, headers={sessions.CSRF_HEADER: csrf})
    test_client.cookies.set(sessions.COOKIE, token)
    return test_client


# Enough patient detail for the clinical guardrails to be able to answer at all: without
# eGFR they abstain (rule G00b in app/clinical/guardrails.v1.yaml), which is the point of
# the panel. Tests about missing details send their own parts.
PATIENT = {
    "type": "patient", "age_years": 58, "diabetes_duration_years": 6, "hba1c_percent": 8.4,
    "egfr_ml_min_1_73m2": 62, "bmi_kg_m2": 31.2, "established_ascvd": False, "ckd": False,
    "heart_failure": False, "past_dka": False, "recurrent_genital_or_urinary_infection": False,
    "past_pancreatitis": False, "past_hypoglycaemia": "none",
}


@pytest.fixture
def chat_body() -> Callable[..., dict]:
    """Build a valid request body; override any piece with keyword arguments."""

    def build(text: str = "What should I add to metformin?", **overrides) -> dict:
        body = {
            "schema_version": "1.0",
            "client_trace_id": TRACE,
            "parts": [{"type": "text", "text": text}, PATIENT],
        }
        body.update(overrides)
        return body

    return build

