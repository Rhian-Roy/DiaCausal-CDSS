<!-- Owner: C | Model: Opus 5 | Effort: high | Branch: feat/auth | Start: Tue 22 Sep -->
# Prompt 2: Login, MFA, CAPTCHA, admin, audit log

**How to run:** in Claude Code type `/model`, choose **Opus 5**, set effort to **high**, then type:
`Do docs/prompts/02-auth.md exactly. First create and switch to the branch feat/auth from an up-to-date main.`

---
Read CLAUDE.md, backend/app/auth/README.md, backend/app/db/README.md, frontend/src/features/auth/README.md and design/v1/01–08. Task: sign-in, so /api/v1/chat answers only signed-in clinicians. Plan first (endpoints, tables, login state machine, exact pinned library versions) and wait for my OK.
Whiteboard: "master login, ID, password, CAPTCHA (python lib), MFA, backend authentication". Build to OWASP ASVS L1 / NIST SP 800-63B:
1. Individual accounts only. "Master login" = an admin role that creates, disables, unlocks and resets MFA for clinician accounts. No shared login, no self-registration. First admin via scripts/create_admin.py (prompts for the password; no default password anywhere). Admin actions via CLI scripts for now — no admin screen.
2. backend/app/db/: SQLAlchemy 2 + Alembic, SQLite now (Postgres later = URL change). Tables: users, audit_log.
3. Two steps: (a) user ID + password + CAPTCHA -> short-lived login token (designs 01–03); (b) 6-digit TOTP -> session (designs 04–05). Argon2id via pwdlib. pyotp, ±1 step, no code reuse, secret Fernet-encrypted with a key from .env (add .env.example; never commit .env). First sign-in -> MFA setup (design 06): QR + manual key in groups of 4 + confirm a code.
4. CAPTCHA: Python `captcha` library, image + audio, offline. Its built-in voices cover digits 0-9 only, so use a 6-digit challenge so image and audio match. Answer server-side, single use, 5-minute expiry, "New image", "Play audio". Behind a small provider interface so Cloudflare Turnstile can be swapped in later.
5. After first sign-in: intended-use acknowledgement (design 07), stored per user with date and version.
6. Session: __Host- cookie, HttpOnly, Secure, SameSite=Strict; idle and absolute timeouts in settings.py with a one-line reason; 2-minute warning modal (design 08); logout; CSRF protection on every state-changing request.
7. One message for every failure ("Those details did not match"); per-IP and per-account rate limiting with increasing delay; lockout (design 03) an attacker can't use to lock everyone out; admin unlock.
8. audit_log: sign-in success/failure, lockout, logout, every chat request — time, user, a server-generated UUID request_id AND the client trace ID, outcome, stage statuses. Never passwords, codes, CAPTCHA answers or message text. Return request_id in the chat response.
9. Frontend: the screens in src/features/auth/ from designs 01–08 (fonts from local @fontsource). Keep the CAPTCHA inside the form, before "Sign in". App.tsx: sign-in -> MFA -> acknowledgement -> ChatPage. TopBar shows the clinician's name and "Sign out".
10. Console lines with a trace ID: "login input passed", "captcha passed", "password passed", "mfa passed".
11. Tests: wrong password; wrong/expired/reused CAPTCHA; wrong/reused TOTP; lockout and unlock; chat without session -> 401; missing CSRF -> 403; timeout; no secrets or message text in logs. Add live checks to scripts/check_all.py; update docs/TESTING.md, the check count, docs/SETUP.md (create admin, enrol an authenticator app).
12. Write docs/explain/04-login-and-mfa.md: one full sign-in, request by request, and 8 viva questions with answers incl. "Why is a CAPTCHA not a second factor?" and "Why no shared master login?".

---
When you are completely finished (all tests green):
1. Run `python3 scripts/check_all.py` and show me the last line.
2. Commit, push this branch, and open a pull request to main (use `gh pr create`; if `gh` is not logged in, walk me through `gh auth login` step by step).
3. Give me the pull-request link.
4. Write a 5-line plain-English summary of what changed that I can paste into our team WhatsApp.
Do NOT merge the pull request — I will get it reviewed first.
