"""The "master login" = admin role, run from the command line; password rules; migrations."""

import io
from datetime import UTC, datetime

import pyotp
import pytest
from sqlalchemy import create_engine, inspect, select

from app import db as database
from app.auth import cli, mfa, passwords
from app.auth.cli import Refused
from app.db.models import AuditLog, Base, User
from conftest import PASSWORD, TEST_DB, add_user

ADMIN_SECRET = pyotp.random_base32(32)


def make_admin(user_id="admin.one"):
    return add_user(user_id, role="admin", display_name="Admin One", mfa_enrolled=True,
                    totp_secret_enc=mfa.encrypt(ADMIN_SECRET))


def current_code() -> str:
    return pyotp.TOTP(ADMIN_SECRET).at(datetime.now(UTC))


def run_cli(monkeypatch, capsys, args: list[str], stdin: str) -> tuple[int, str, str]:
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    code = cli.main(["--password-stdin", *args])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_first_admin_can_be_created_once(monkeypatch, capsys, db):
    code, out, _ = run_cli(monkeypatch, capsys, ["create-first-admin", "Admin.One", "Dr Admin"], PASSWORD + "\n")
    assert code == 0 and "Created admin admin.one" in out
    user = db.scalar(select(User))
    assert user.role == "admin" and user.user_id == "admin.one"
    assert passwords.verify_password(PASSWORD, user.password_hash) and PASSWORD not in user.password_hash

    code, _, err = run_cli(monkeypatch, capsys, ["create-first-admin", "second", "Dr Two"], PASSWORD + "\n")
    assert code == 1 and "An admin already exists" in err


def test_admin_creates_a_clinician_with_password_and_current_code(monkeypatch, capsys, db):
    make_admin()
    stdin = f"{PASSWORD}\n{current_code()}\nanother good passphrase\n"
    code, out, _ = run_cli(monkeypatch, capsys, ["--as", "admin.one", "create-user", "dr.mehta", "Dr Mehta"], stdin)
    assert code == 0 and "Created clinician dr.mehta" in out
    row = db.scalar(select(AuditLog).where(AuditLog.event == "account_created", AuditLog.user_id == "dr.mehta"))
    assert row.detail == "by admin admin.one"


def test_admin_action_refused_without_the_right_code(monkeypatch, capsys):
    make_admin()
    code, _, err = run_cli(monkeypatch, capsys, ["--as", "admin.one", "list"], f"{PASSWORD}\n000000\n")
    assert code == 1 and "did not match" in err


def test_a_clinician_cannot_act_as_admin(monkeypatch, capsys):
    add_user("dr.rao", mfa_enrolled=True, totp_secret_enc=mfa.encrypt(ADMIN_SECRET))
    code, _, err = run_cli(monkeypatch, capsys, ["--as", "dr.rao", "list"], f"{PASSWORD}\n{current_code()}\n")
    assert code == 1 and "did not match" in err


def test_disable_and_reset_mfa_end_that_users_sessions(db):
    admin = make_admin()
    add_user("dr.rao", mfa_enrolled=True, totp_secret_enc=mfa.encrypt("A" * 32))
    admin = db.get(User, admin.id)
    cli.run(db, "reset-mfa", "dr.rao", admin)
    user = db.scalar(select(User).where(User.user_id == "dr.rao"))
    assert user.mfa_enrolled is False and user.totp_secret_enc is None
    cli.run(db, "disable", "dr.rao", admin)
    assert user.disabled is True
    with pytest.raises(Refused):
        cli.run(db, "disable", "admin.one", admin)  # not yourself


def test_list_shows_accounts_but_no_secrets(db):
    admin = make_admin()
    out = cli.run(db, "list", None, db.get(User, admin.id))
    assert "admin.one" in out and "admin" in out and ADMIN_SECRET not in out


@pytest.mark.parametrize(
    ("password", "problem"),
    [
        ("short pass", "at least 12"),
        ("password1234", "too common"),
        ("aaaaaaaaaaaaaaa", "too common"),
        ("my dr.rao password", "must not contain the user ID"),
        ("x" * 129, "at most 128"),
    ],
)
def test_password_rules(password, problem):
    assert problem in passwords.password_problem(password, "dr.rao")


def test_a_long_passphrase_is_fine():
    assert passwords.password_problem("correct horse battery staple", "dr.rao") is None


def test_user_ids_are_simple_ascii():
    with pytest.raises(Refused):
        cli.normalise_user_id("dr rao!")
    assert cli.normalise_user_id("  Dr.Rao ") == "dr.rao"


def test_migrations_build_exactly_the_tables_in_models(tmp_path):
    url = f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}"
    database.migrate(url)
    migrated = inspect(create_engine(url))
    assert set(migrated.get_table_names()) - {"alembic_version"} == set(Base.metadata.tables)
    for name, table in Base.metadata.tables.items():
        assert {c["name"] for c in migrated.get_columns(name)} == set(table.columns.keys())


def test_the_test_database_is_not_the_real_one():
    assert "diacausal-tests-" in TEST_DB
