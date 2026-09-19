# 04 — Sign-in, MFA and the "master login"

Whiteboard: *"login page … master login … ID, password, captcha (python lib … bot
identification)"*, *"security … MFA (ID, PASS CODE, CAPTCHA)"*, *"BACKEND AUTHENTICATION
… for login"*. Built to OWASP ASVS level 1 and NIST SP 800-63B.

## The pieces

| Piece | What it is | Where |
|---|---|---|
| Accounts | One per person, created by an admin. Roles: `clinician`, `admin` | `backend/app/db/models.py` (`users`) |
| Password | Stored only as an **Argon2id** hash (`pwdlib`); at least 12 characters, common ones refused | `app/auth/passwords.py` |
| CAPTCHA | 6 digits as a picture **and** as audio, made offline by the Python `captcha` library; answer kept on the server, works once, for 5 minutes | `app/auth/captcha.py` (behind a small interface: Cloudflare Turnstile can replace it later) |
| MFA | A 6-digit code from Google/Microsoft Authenticator (TOTP, `pyotp`), ±30 s, each code once. The shared secret is encrypted in the database (Fernet, key in `backend/.env`) | `app/auth/mfa.py` |
| Session | Random token in a `__Host-` cookie: HttpOnly, Secure, SameSite=Strict. Database stores only its SHA-256 | `app/auth/sessions.py` (`sessions`) |
| CSRF | Every state-changing request must carry the session's token in `X-CSRF-Token` | `app/auth/deps.py` |
| Timeouts | Idle 15 minutes (warning at 13), absolute 8 hours; half-signed-in 5 minutes | `app/settings.py` (each with its reason) |
| Lockout | 5 wrong passwords/codes → 15-minute lock that clears itself; growing delay from the 3rd; per-IP limits; admin unlock | `app/auth/throttle.py` |
| Audit log | Sign-ins, failures, lockouts, sign-outs, timeouts, admin actions, **every chat request** (time, user, server `request_id` UUID, client trace ID, outcome, stage statuses). Never passwords, codes, CAPTCHA answers or message text | `app/auth/audit.py` (`audit_log`) |
| Master login | An **admin role**, not a shared password. Admin actions run from the command line, each needing the admin's own password + current code | `app/auth/cli.py`, `scripts/create_admin.py`, `scripts/admin.py` |

## One full first sign-in, request by request

| # | Browser does | Server does | Browser console |
|---|---|---|---|
| 1 | `GET /api/v1/auth/me` (did a reload keep me signed in?) | No cookie → `401 not_signed_in` | |
| 2 | `GET /api/v1/auth/captcha` | Makes 6 random digits, stores them in `captcha_challenges`, returns `captcha_id` + a PNG. The answer is never sent | |
| 3 | (optional) `GET …/captcha/{id}/audio` | The same digits as a WAV file | |
| 4 | User types ID, password, digits → `POST /api/v1/auth/login` with a new trace ID | Per-IP check → account locked? → growing delay? → **CAPTCHA** (deleted after this one try) → **password** (Argon2id; for an unknown user ID a dummy hash, so timing gives nothing away). Success: new session with `stage = password_ok` (5 minutes), cookie set, `{"next": "mfa_setup", "csrf_token": …}` | `[id] login input passed`, `[id] captcha passed`, `[id] password passed` |
| 5 | `POST /api/v1/auth/mfa/setup` + `X-CSRF-Token` | Makes a 160-bit secret, stores it **encrypted**, returns the QR code (SVG) and the key in groups of 4 | |
| 6 | Phone scans the QR; user types the code → `POST /api/v1/auth/mfa/confirm` | Checks the code (this 30-s step, one before or after, not used before) → `mfa_enrolled`, remembers the step, **replaces** the session with a new `full` one (new token, new CSRF token) | `[id] mfa passed` |
| 7 | "I understand" → `POST /api/v1/auth/acknowledge {"version": "1"}` | Stores version + date on the user; audit row | |
| 8 | Chat: `POST /api/v1/chat` + cookie + `X-CSRF-Token` | `require_clinician`: session exists, not timed out, stage `full`, CSRF matches, intended use acknowledged → pipeline → audit row with `request_id` → reply includes `request_id` | the usual 4 lines |
| 9 | 13 minutes idle → warning box; **Stay signed in** → `POST /auth/keepalive` | Resets the idle timer | |
| 10 | **Sign out** → `POST /api/v1/auth/logout` | Deletes the session row (the old cookie is now useless), clears the cookie; audit row | |

Every later sign-in: steps 1–4, then `POST /api/v1/auth/mfa` with the code.

A wrong detail anywhere in step 4 gives the same answer: **"Those details did not match"**,
with how many attempts are left. An unknown user ID gets exactly the same answer and the
same count, so nobody can find out which IDs exist.

## Why the lockout cannot lock everyone out

- Only attempts **with a correct CAPTCHA** count towards an account's lock. A bot that
  cannot read CAPTCHAs can hammer the server all day; it only slows down its own IP address.
- The lock **clears on its own** after 15 minutes (design 03) — an attacker would have to
  keep solving CAPTCHAs, one per try, to keep a colleague out.
- An admin can unlock at once (`scripts/admin.py --as ADMIN unlock USER`).

## Tests

`backend/tests/test_auth.py` (wrong password, wrong/expired/reused CAPTCHA, wrong/reused
code, lockout and unlock, chat without session → 401, missing CSRF → 403, idle and
absolute timeout, logout, audit rows, no secrets in logs), `backend/tests/test_admin.py`
(master login, password rules, migrations), `frontend/src/App.test.tsx` (the screens),
and 8 live checks in `scripts/check_all.py`, which really signs in with a CAPTCHA and a
6-digit code.

## Viva questions

**1. Why is a CAPTCHA not a second factor?**
A factor proves *who* you are: something you know (password), have (phone with the
authenticator), or are. A CAPTCHA only asks *whether you are a person*; anyone can solve
it. It slows down bots trying many passwords, so it protects the password step. It does
nothing if a person has stolen the password. The 6-digit code does.

**2. Why no shared master login?**
A shared password cannot be traced to a person, cannot be taken away from one person
who leaves, and spreads by being shared. So the "master login" is a role: each admin has
their own account, and every admin action is done as that person (password + code) and
written to the audit log.

**3. Why Argon2id and not SHA-256 for passwords?**
SHA-256 is fast: a graphics card tries billions of guesses per second on a stolen
database. Argon2id is deliberately slow and needs 64 MB of memory per guess, which makes
mass guessing very expensive. Each hash also has its own random salt.

**4. How does the 6-digit code work, and why can't it be reused?**
The phone and the server share a secret. Every 30 seconds both compute
HMAC-SHA1(secret, current 30-s step number) and turn it into 6 digits (RFC 6238). We accept
the step before and after for clock drift, and remember the newest step used. An older
or repeated code is refused, so a code seen over someone's shoulder is useless afterwards.

**5. What do HttpOnly, Secure, SameSite=Strict and `__Host-` each stop?**
HttpOnly: page scripts cannot read the cookie, so an injected script cannot steal it.
Secure: never sent over plain HTTP. SameSite=Strict: never sent with a request that
another website starts. `__Host-`: the browser only accepts it with Secure, Path=/ and no
Domain, so a sub-domain cannot plant or override it.

**6. What is CSRF and how is it stopped here?**
Cross-site request forgery: another website makes your browser send a request to our API
with your cookie. SameSite=Strict already blocks that, and as a second layer every
state-changing request must carry the session's CSRF token in a header. The token comes
in a JSON reply, which another site cannot read.

**7. Why does a wrong user ID get the same answer as a wrong password?**
Otherwise the answers reveal which user IDs exist (user enumeration), halving an
attacker's work. The same message, the same attempt count, and the same Argon2 time (a
dummy hash for unknown IDs) all hide it.

**8. What is in the audit log, and what is never in it?**
Time, event, user ID, a server-generated `request_id` UUID, the browser's trace ID,
outcome, stage statuses and the IP address. Never passwords, codes, CAPTCHA answers or
message text. The `request_id` is returned in every chat reply, so a clinician's report
can be matched to exactly one row.
