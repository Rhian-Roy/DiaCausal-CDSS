# DiaCausal — working rules

Research prototype chatbot for clinician evaluation; **not a marketed medical device; not
for unsupervised clinical use.** That sentence appears on every screen, in every chat reply
(`intended_use`) and in the API docs.

## Layout

- `frontend/` — React + Vite + TypeScript + Tailwind v4 + shadcn/ui (Node 24 LTS)
- `backend/` — FastAPI + Pydantic v2 on Python 3.12, in its own venv at `backend/.venv`
- `design/` — the screens to match (`chat.html` / `login.html` hold the exact colours, fonts, spacing)
- `causal_engine/`, notebooks, `RAG/` — earlier research code; the backend will call into it later

All commands run from the repo root. The `( ... )` keeps each `cd` inside its own line,
so a whole block can be pasted at once.

## Setup (once per checkout — `.venv` and `node_modules` are not in git)

```bash
python3.12 scripts/setup.py      # any OS; Windows: py -3.12 scripts\setup.py (see docs/SETUP.md)
```

## Check everything (tests, build, lint, live backend + page on spare ports)

```bash
python3 scripts/check_all.py     # must end with "ALL 34 CHECKS PASSED"; Windows: py scripts\check_all.py
```

If you add a requirement, add a check for it here or in the tests, and update
`docs/TESTING.md` (requirement → check table) and the numbers in `docs/explain/02-presenting-it.md`.

## Run (one terminal each)

```bash
(cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000)   # API on :8000, docs at /docs
(cd frontend && npm run dev)                                          # page on http://localhost:5173
```

## Test

```bash
(cd backend && .venv/bin/python -m pytest)       # API contract, guards, trace-ID logging
(cd frontend && npm test)                         # guards, output check, whole page flow (Vitest + jsdom)
(cd frontend && npm run build && npm run lint)    # type-check + bundle + oxlint
```

## Frontend rules

- Pressing Enter (Shift+Enter = new line) prints, in order, each line starting with the
  message's 8-hex trace ID: `[id] input passed`, `[id] ui guard passed`,
  `[id] medical ui guard passed`, then after the reply `[id] output passed`.
  Blocks and failures use `console.warn` / `console.error` with the same prefix.
- Flow lives in `src/lib/chatFlow.ts`; guards in `src/lib/guards.ts`. Both guards and the
  backend's `app/pipeline/blocklist.py` load `shared/guard_rules/rules.v1.json` — edit the
  lists there, never in code. A guard block shows notice 09–12 (`GuardNotice.tsx`); the
  backend returns `reason_code` + `scope_topic`. Never show or log the matched word.
- `src/lib/contract.ts` mirrors `backend/app/schemas.py` — change both together.
  `checkOutput` (src/lib/api.ts) refuses any reply with the wrong shape or another trace ID.
- The browser only calls `/api/...`; Vite proxies it to :8000. No CORS setup needed in dev.
- Colours, fonts, radii are tokens in `src/index.css` copied from `design/chat.html`; use
  `bg-pine`, `text-ink-muted`, `rounded-card` etc., never raw hex in components. Light-only.
  `md:` starts at 761px, the design's phone/desktop switch.
- Enter must not send while an input method is composing (`isComposing` or Safari's `keyCode 229`).
- shadcn/ui components live in `src/components/ui/` (ours to edit).

## API rules (backend/app/schemas.py is the contract)

- `POST /api/v1/chat` accepts exactly
  `{"schema_version":"1.0","client_trace_id":"...","parts":[{"type":"text","text":"..."}]}`.
  Unknown fields are rejected (`extra="forbid"`).
- Reject with HTTP 422 and a plain-English `message` (app/errors.py): unknown part types,
  text over 8000 characters (Python `len`, i.e. characters, not bytes), bad/missing
  `schema_version` or `client_trace_id` (1-64 of `A-Z a-z 0-9 - _`), empty or >20 parts.
- New part types: add a model in schemas.py, make `Part` a tagged union, add the name to
  `SUPPORTED_PART_TYPES`. Never loosen validation to "accept anything".
- Every reply lists six stages in this order: `backend_guard`, `clinical_guardrails`,
  `causal_engine`, `rag_retrieval`, `llm_explanation`, `output_guard` (one file each in
  `app/pipeline/`). Today only the first and last run; the rest return `"skipped"`.
  After a stage blocks, later stages are `"skipped"` and `outcome` is `"blocked"` (HTTP 200).
- Every app log line (logger `diacausal`, app/tracing.py) carries `[client_trace_id]` after
  the time and level (`[-]` when there is no valid ID, e.g. a rejected request), e.g. `19:33:11 INFO    [efc1a658] backend_guard: passed`. Uvicorn's own
  access lines (`"POST /api/v1/chat HTTP/1.1" 200`) do not.
  **Never log message text** — only sizes, stage results and IDs. Client values echoed in
  errors or logs go through `_show` in app/errors.py (short, ASCII-escaped).

## Sign-in (built) — see docs/explain/04-login-and-mfa.md

- `backend/app/auth/` (CAPTCHA, Argon2id, TOTP, sessions, CSRF, lockout, audit, admin CLI),
  `backend/app/db/` (SQLAlchemy 2 + Alembic; add a migration for every model change),
  `frontend/src/features/auth/` (designs 01–08). `/api/v1/chat` needs `require_clinician`.
- Secrets live in `backend/.env` (made by setup, never committed). Never log passwords,
  codes, CAPTCHA answers or message text. First admin: `scripts/create_admin.py`.
- Tests: the `client` fixture is already signed in; use `anon` for a stranger.

## Voice (built) — see docs/explain/12-voice.md

`POST /api/v1/transcribe` runs faster-whisper (`base`, int8) on this computer;
`frontend/src/features/voice/` records and puts the text **in the message box**, never
sends it. Never keep the audio; never log the transcript.

## Not built yet — where each piece goes

| Piece | Backend | Frontend / other |
|---|---|---|
| Docker | — | `docker/` |
| Clinical guardrails, causal engine, RAG, LLM | `backend/app/pipeline/<stage>.py` | — |

Each folder's README says how it connects.

## Tooling

- Node: `/opt/homebrew/opt/node@24/bin` (on PATH via `~/.zshrc`). Python: `/opt/homebrew/bin/python3.12`.
- Never use Anaconda's `python3` for the backend — always `backend/.venv/bin/python`.
- Pin exact versions in `backend/requirements*.txt`.
- Commit after each working step.
