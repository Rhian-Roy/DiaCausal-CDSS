# db — database (built)

SQLAlchemy 2 + Alembic. SQLite file `backend/diacausal.db` now (not committed);
PostgreSQL later is only a change of `DIACAUSAL_DATABASE_URL` (see `app/secrets_env.py`).
The app brings the tables up to date on start-up (`app.db.configure`).

| Table | Holds |
|---|---|
| `users` | user ID, name, role, Argon2id hash, encrypted MFA secret, lockout state, intended-use acknowledgement (version + date) |
| `sessions` | SHA-256 of each session token, stage, CSRF token, times |
| `captcha_challenges` | open CAPTCHAs (single use, 5 minutes) |
| `audit_log` | time, event, user, server `request_id`, client trace ID, outcome, stage statuses — never message text or secrets |

**Changing a table:** edit `models.py`, then from `backend/` generate a migration
(`.venv/bin/python -m alembic -c <config> revision --autogenerate`, see `migrations/`),
check it, and commit both. `tests/test_admin.py` fails if models and migrations differ.
