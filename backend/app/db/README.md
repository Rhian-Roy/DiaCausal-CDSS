# db — database (not built yet)

Nothing is stored today: each message is answered and forgotten.

**What goes here:** the database connection, table models and migrations.

**Likely first tables**

| Table | Holds |
|---|---|
| `clinicians` | user ID, password hash, MFA secret (encrypted), lockout state |
| `audit_log` | time, clinician, trace ID, outcome, each stage's status — *not* the message text |
| `feedback` | clinician ratings of answers, for the evaluation study |

**Likely libraries:** SQLAlchemy 2 (or SQLModel) + Alembic for migrations; SQLite on a
laptop, PostgreSQL when deployed. A `get_session` dependency will be passed to routes the
same way `require_clinician` will be (see `../auth/README.md`).

**Rules:** store message text only if the study protocol and consent allow it; the trace
ID is the link between the audit log, the backend log and the browser console.
