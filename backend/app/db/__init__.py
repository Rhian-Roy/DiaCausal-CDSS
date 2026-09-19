"""The database: SQLAlchemy 2 + Alembic migrations. SQLite now; PostgreSQL later is
only a change of DIACAUSAL_DATABASE_URL (see app/secrets_env.py).

    configure(url)   connect and bring the tables up to date (runs the migrations)
    get_db()         FastAPI dependency: one database session per request
"""

from collections.abc import Iterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

MIGRATIONS = Path(__file__).resolve().parent / "migrations"

_engine: Engine | None = None
_factory: sessionmaker[Session] | None = None


def _sqlite_foreign_keys(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def migrate(url: str) -> None:
    """Create or update every table to the latest migration."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


def configure(url: str) -> Engine:
    global _engine, _factory
    if _engine is not None and str(_engine.url) == url:
        return _engine
    migrate(url)
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _sqlite_foreign_keys)
    _engine, _factory = engine, sessionmaker(engine, expire_on_commit=False)
    return engine


def new_session() -> Session:
    if _factory is None:
        raise RuntimeError("database not configured: call app.db.configure(url) first")
    return _factory()


def get_db() -> Iterator[Session]:
    with new_session() as db:
        yield db
