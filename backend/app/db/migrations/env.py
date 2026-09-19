"""Alembic runs this to apply migrations (app/db/__init__.py calls it for you)."""

from alembic import context
from sqlalchemy import create_engine

from app.db.models import Base

url = context.config.get_main_option("sqlalchemy.url")
engine = create_engine(url)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
