# auth — sign-in (not built yet)

**What goes here:** backend authentication for the login screen in `design/login.html`:
hospital user ID + password + 6-digit authenticator code (MFA) + CAPTCHA (bot check).

**How it will connect**

1. `POST /api/v1/auth/login` checks, in this order: CAPTCHA → user ID + password →
   6-digit code. Any failure gives the same vague message ("Those details did not match").
2. On success the server sets a session cookie (`HttpOnly`, `Secure`, `SameSite=Strict`).
3. `app/routes.py` → `chat()` gains `clinician: Clinician = Depends(require_clinician)`,
   so the chat endpoint answers only signed-in clinicians.

**Likely libraries:** `argon2-cffi` (password hashes), `pyotp` (6-digit codes), a
server-side CAPTCHA check (e.g. a self-hosted image CAPTCHA, or a provider's verify API).

**Rules:** never log passwords, codes or CAPTCHA answers; rate-limit and lock out after
repeated failures; log sign-ins with the trace ID, never the secret.
