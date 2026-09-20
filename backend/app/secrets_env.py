"""The two values that are NOT in settings.py because they are secret or per-computer.

They are read from environment variables, or from backend/.env (made by
scripts/setup.py, never committed; see backend/.env.example):

  DIACAUSAL_SECRET_KEY    Fernet key that encrypts every MFA secret in the database.
                          Lose it and everyone must set up their authenticator again.
  DIACAUSAL_DATABASE_URL  Where the database is. Default: SQLite file backend/diacausal.db.
                          PostgreSQL later is only a URL change.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(ENV_FILE)  # real environment variables win over the file

DEFAULT_DATABASE_URL = f"sqlite:///{(BACKEND_DIR / 'diacausal.db').as_posix()}"


class MissingSecret(RuntimeError):
    pass


def database_url() -> str:
    return os.environ.get("DIACAUSAL_DATABASE_URL", DEFAULT_DATABASE_URL)


def secret_key() -> bytes:
    key = os.environ.get("DIACAUSAL_SECRET_KEY", "")
    if not key:
        raise MissingSecret(
            "DIACAUSAL_SECRET_KEY is not set. Run the setup once (python3.12 scripts/setup.py), "
            "which writes it to backend/.env."
        )
    return key.encode()
