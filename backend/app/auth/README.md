# auth — sign-in (built)

User ID + password + CAPTCHA, then a 6-digit authenticator code; the whiteboard's "master
login" is the **admin role**. How it works, request by request, and viva questions:
[docs/explain/04-login-and-mfa.md](../../../docs/explain/04-login-and-mfa.md).

| File | Does |
|---|---|
| `routes.py` | the endpoints under `/api/v1/auth` |
| `deps.py` | `require_clinician` (used by `/api/v1/chat`), CSRF check, JSON errors |
| `captcha.py` | offline image + audio CAPTCHA behind a provider interface (swap in Turnstile later) |
| `passwords.py`, `mfa.py` | Argon2id hashes; TOTP codes, encrypted secrets, QR code |
| `sessions.py`, `throttle.py` | cookie sessions and timeouts; delays, lockout, per-IP limits |
| `audit.py` | writes `audit_log` rows |
| `cli.py` | admin actions (`scripts/create_admin.py`, `scripts/admin.py` call it) |
| `clock.py` | the current time, replaceable in tests |

**Rules:** never log or store passwords, codes, CAPTCHA answers or message text; every
failure says "Those details did not match"; change timeouts only in `app/settings.py`.
