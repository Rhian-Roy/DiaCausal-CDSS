# auth — sign-in screens (built)

Designs `design/v1/01-08`: `SignInPage` (01-03), `CodePage` (04-05), `MfaSetupPage` (06),
`IntendedUsePage` (07), `SessionTimer` (08). `src/App.tsx` moves between them:
sign in → [first time: authenticator set-up] → code → intended use → chat.

`api.ts` calls `/api/v1/auth/*`. The session is an `HttpOnly` cookie the page cannot
read; the CSRF token is kept in memory only (`src/lib/authSession.ts`) and sent as
`X-CSRF-Token`. The browser never stores the password or code.

Console lines (with a trace ID): `login input passed`, `captcha passed`, `password passed`,
`mfa passed`. Tests: `src/App.test.tsx`.
