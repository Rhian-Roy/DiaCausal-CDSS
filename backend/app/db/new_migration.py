"""Make a new migration after changing models.py. From backend/:

    .venv/bin/python -m app.db.new_migration "add feedback table"

Alembic compares models.py with the tables the existing migrations build and writes the
difference to migrations/versions/. Read the new file, then commit it with models.py.
"""

import sys
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.db import MIGRATIONS, migrate

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    scratch = f"sqlite:///{(Path(tempfile.mkdtemp()) / 'scratch.db').as_posix()}"
    migrate(scratch)  # the tables as the existing migrations build them
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", scratch)
    existing = len(list((MIGRATIONS / "versions").glob("[0-9]*.py")))
    command.revision(config, message=sys.argv[1], autogenerate=True, rev_id=f"{existing + 1:04d}")
