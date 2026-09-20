"""Account administration from the command line (there is no admin screen yet).

The whiteboard's "master login" is an ADMIN ROLE, not a shared password: each admin is a
person with their own account, and every action below is done *as* that admin (their
user ID, password and current 6-digit code) and written to audit_log.

    python -m app.auth.cli create-first-admin               (only while there is no admin)
    python -m app.auth.cli --as ADMIN create-user USER_ID "Dr Name" [--role admin]
    python -m app.auth.cli --as ADMIN disable|enable|unlock|reset-mfa USER_ID
    python -m app.auth.cli --as ADMIN list

Easier: scripts/create_admin.py and scripts/admin.py in the repo root call this for you.
Passwords are always typed at a hidden prompt (or piped with --password-stdin);
never on the command line, where they would end up in the shell history.
"""

import argparse
import getpass
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import db as database
from app.auth import audit, clock, mfa, passwords, sessions, throttle
from app.db.models import User
from app.secrets_env import MissingSecret, database_url, secret_key


class Refused(Exception):
    pass


def _read_password(prompt: str, from_stdin: bool) -> str:
    if from_stdin:
        line = sys.stdin.readline()
        if not line:
            raise Refused("No password arrived on standard input.")
        return line.rstrip("\n")
    if not sys.stdin.isatty():
        # No real terminal (an editor's console, a script, a CI job): getpass cannot hide
        # typing, so say what to do instead of failing with a traceback.
        raise Refused(
            "This needs a real terminal so the password stays hidden while you type it.\n"
            "       Open Terminal (or iTerm) and run the same command there, or pipe the\n"
            "       password in:  echo 'your password' | python3 scripts/create_admin.py "
            "USER_ID \"Display name\" --password-stdin\n"
            "       (piping puts the password in your shell history — change it afterwards)."
        )
    return getpass.getpass(prompt)


def _new_password(user_id: str, from_stdin: bool) -> str:
    first = _read_password(f"New password for {user_id}: ", from_stdin)
    if problem := passwords.password_problem(first, user_id):
        raise Refused(problem)
    if not from_stdin and getpass.getpass("Type it again: ") != first:
        raise Refused("The two passwords were different.")
    return first


def normalise_user_id(user_id: str) -> str:
    cleaned = user_id.strip().casefold()
    if not (3 <= len(cleaned) <= 64) or not all(c.isascii() and (c.isalnum() or c in "._-") for c in cleaned):
        raise Refused("A user ID is 3-64 characters: letters, digits, '.', '_' or '-'.")
    return cleaned


def create_user(db: Session, user_id: str, name: str, role: str, password: str, by: str | None) -> User:
    user_id = normalise_user_id(user_id)
    if db.scalar(select(User).where(User.user_id == user_id)):
        raise Refused(f"There is already an account {user_id}.")
    if problem := passwords.password_problem(password, user_id):
        raise Refused(problem)
    user = User(
        user_id=user_id, display_name=name.strip() or user_id, role=role,
        password_hash=passwords.hash_password(password), created_at=clock.now(),
    )
    db.add(user)
    db.commit()
    audit.record(db, "account_created", role, user_id=user_id, detail=f"by {by or 'first-admin setup'}")
    return user


def _find(db: Session, user_id: str) -> User:
    user = db.scalar(select(User).where(User.user_id == user_id.strip().casefold()))
    if user is None:
        raise Refused(f"No account {user_id}.")
    return user


def authenticate_admin(db: Session, user_id: str, password: str, code: str) -> User:
    """The admin running the command proves who they are: password + current 6-digit code."""
    admin = db.scalar(select(User).where(User.user_id == user_id.strip().casefold()))
    counter = throttle.counter_for(admin, user_id)
    if throttle.is_locked(counter):
        raise Refused("That account is locked. Wait, or ask another administrator.")
    ok = passwords.verify_password(password, admin.password_hash if admin else None)
    step = None
    if ok and admin is not None and admin.totp_secret_enc and admin.mfa_enrolled:
        step = mfa.matching_step(mfa.decrypt(admin.totp_secret_enc), code.strip(), admin.last_totp_step)
    if admin is None or admin.disabled or admin.role != "admin" or step is None:
        throttle.add_failure(counter)
        db.commit()
        audit.record(db, "admin_auth_failed", "failed", user_id=user_id)
        raise Refused("Those details did not match (an administrator's user ID, password and current code).")
    admin.last_totp_step = step
    throttle.clear(admin)
    db.commit()
    return admin


def run(db: Session, action: str, target: str | None, admin: User) -> str:
    by = f"admin {admin.user_id}"
    if action == "list":
        rows = db.scalars(select(User).order_by(User.user_id)).all()
        return "\n".join(
            f"{u.user_id:20} {u.role:9} {'DISABLED' if u.disabled else 'active':8} "
            f"mfa={'yes' if u.mfa_enrolled else 'no':3} {'LOCKED' if throttle.is_locked(u) else ''}  {u.display_name}"
            for u in rows
        )
    user = _find(db, target or "")
    if action == "disable":
        if user.id == admin.id:
            raise Refused("You cannot disable your own account.")
        user.disabled = True
        sessions.end_all_for(db, user)
    elif action == "enable":
        user.disabled = False
    elif action == "unlock":
        throttle.clear(user)
    elif action == "reset-mfa":
        user.totp_secret_enc, user.mfa_enrolled, user.last_totp_step = None, False, 0
        sessions.end_all_for(db, user)
    db.commit()
    audit.record(db, f"admin_{action.replace('-', '_')}", "done", user_id=user.user_id, detail=f"by {by}")
    return f"{action}: done for {user.user_id}."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.auth.cli", description=__doc__.split("\n\n")[0])
    parser.add_argument("--as", dest="admin", help="your admin user ID (every action except create-first-admin)")
    parser.add_argument("--password-stdin", action="store_true", help="read passwords from standard input")
    sub = parser.add_subparsers(dest="action", required=True)
    first = sub.add_parser("create-first-admin", help="create the first admin (only when there is none)")
    first.add_argument("user_id")
    first.add_argument("name")
    create = sub.add_parser("create-user", help="create a clinician (or, with --role admin, another admin)")
    create.add_argument("user_id")
    create.add_argument("name")
    create.add_argument("--role", choices=["clinician", "admin"], default="clinician")
    for action in ("disable", "enable", "unlock", "reset-mfa"):
        sub.add_parser(action).add_argument("user_id")
    sub.add_parser("list")
    args = parser.parse_args(argv)

    try:
        secret_key()
        database.configure(database_url())
        with database.new_session() as db:
            if args.action == "create-first-admin":
                if db.scalar(select(func.count()).where(User.role == "admin")):
                    raise Refused("An admin already exists. Ask them to run: scripts/admin.py --as THEIR_ID create-user ... --role admin")
                user_id = normalise_user_id(args.user_id)
                user = create_user(db, user_id, args.name, "admin", _new_password(user_id, args.password_stdin), None)
                print(f"Created admin {user.user_id}. Sign in at the web page; the first sign-in sets up the authenticator app.")
                return 0

            if not args.admin:
                raise Refused("Say which admin you are: --as YOUR_ADMIN_ID")
            password = _read_password(f"Password for {args.admin}: ", args.password_stdin)
            code = _read_password("Current 6-digit code from your authenticator app: ", args.password_stdin)
            admin = authenticate_admin(db, args.admin, password, code)
            if args.action == "create-user":
                user_id = normalise_user_id(args.user_id)
                user = create_user(db, user_id, args.name, args.role, _new_password(user_id, args.password_stdin),
                                   f"admin {admin.user_id}")
                print(f"Created {user.role} {user.user_id}.")
            else:
                print(run(db, args.action, getattr(args, "user_id", None), admin))
            return 0
    except (Refused, MissingSecret) as problem:
        print(f"Not done: {problem}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
