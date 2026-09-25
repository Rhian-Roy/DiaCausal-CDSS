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
python3 scripts/check_all.py     # must end with "ALL 43 CHECKS PASSED"; Windows: py scripts\check_all.py
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
  `app/pipeline/`). Today `backend_guard`, `clinical_guardrails` and `output_guard` run; the rest return `"skipped"`.
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

## Patient panel (built) — see docs/explain/05-patient-panel.md

The panel sends a `patient` part alongside the text (`PatientPart` in schemas.py ↔
`contract.ts`); `parts` is a tagged union, so new part types are added, never loosened.
Ranges are plausibility limits in `app/patient_ranges.py` + `features/patient/ranges.ts`
(a test compares them); clinical thresholds belong in `app/clinical/guardrails.v1.yaml`.
Stages read `ctx.patient`. Never log patient values — only which fields arrived.

## Clinical guardrails (built) — see docs/explain/06-guardrails.md

`app/clinical/guardrails.v1.yaml` is the only place thresholds live; `app/clinical/rules.py`
loads it (a rule with TODO or no source never fires) and `pipeline/clinical_guardrails.py`
applies it **before** the causal stage, removing any "do not use" option. Never put a
clinical number in code, and never let a later stage put a removed option back.
Check the table with `.venv/bin/python -m app.clinical.check`.

## Deployment (built) — see docs/DEPLOY.md and docs/explain/11-deploy.md

`docker compose up --build -d` serves the page and the API from **one origin** with HTTPS
in front (Caddy). Security headers live in `backend/app/web.py` only; `/docs` is off when
`DIACAUSAL_ENV=production`; secrets come from `.env` at run time, never from the image.
The evaluation pack is `eval/` (25 synthetic vignettes + the SUS and feedback forms).

## Causal engine v0.3 (built, standalone) — see docs/CAUSAL_PLAN.md

`diacausal_engine/` compares three options added to metformin (SGLT2i, DPP-4i, sulfonylurea)
for one patient: the expected 6-month HbA1c change with a 95% interval. It is the "Causal
Inference Pipeline" column of the team flow chart and returns a structured **Causal Output**
(`schemas.CausalOutput`: APPLICABLE/NOT_APPLICABLE, intervention, outcome, effect, confidence,
assumptions) for the Evidence Fusion layer. Separate venv at the repo root:

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-engine.txt   # once
.venv/bin/python -m pytest tests/engine -q                                      # 137 tests
.venv/bin/python -m diacausal_engine.benchmark --quick                          # full: drop --quick
.venv/bin/streamlit run demo/streamlit_app.py                                   # the demo
.venv/bin/uvicorn diacausal_engine.api:app --port 8001                          # POST /api/v1/recommend
```

Rules that must never be broken:

1. Decision support only; the clinician decides. Every screen and API response (errors too)
   shows: "Research prototype for clinician evaluation; not a marketed medical device; not for
   unsupervised clinical use."
2. Safety rules run **before** any estimate. The engine's contraindication and kidney-function
   thresholds live only in `data/rules.csv` (Part 6 of docs/02_Causal_Engine_Build_Guide.md,
   verbatim; a test compares them), each with a source. Never hard-code or invent them (a test
   scans the code). An excluded option is never estimated. Never show drug doses (output check +
   tests). The chat app still uses `backend/app/clinical/guardrails.v1.yaml`; the two tables
   differ (docs/CAUSAL_PLAN.md §4) — when joined, the stricter action wins until the doctor decides.
3. Every estimate has a 95% interval. Propensity below 0.05 (`engine.overlap_min_propensity`)
   → "insufficient evidence", never a number.
4. Synthetic data only. Every number in `data/params.yaml` has a `source` and a `status`
   (CITED, ASSUMED-DIRECTIONAL or TEAM-SET); the loader refuses anything else. The Pima dataset
   is not Indian data and is not used.
5. Units: HbA1c %, change in percentage points, eGFR mL/min/1.73m2, cost INR/month. Asian-Indian
   BMI cut-offs (overweight >= 23, obese >= 25). Prices stay "price unavailable" until confirmed
   in `data/prices.csv` with a date and source.
6. Never weaken or delete a test to make it pass. No API keys or secrets in this public repo.
   Never log patient values (audit lines hold IDs, versions, statuses and rule IDs only).

After changing params.yaml or the estimators, rerun the full benchmark and commit `results/`.

## Not built yet — where each piece goes

| Piece | Backend | Frontend / other |
|---|---|---|
| Causal engine in the chat app (October) | `backend/app/pipeline/causal_engine.py` calls `diacausal_engine` on `ctx.options` only | designs 17 and 19; `contract.ts` + `schemas.py` together |
| RAG, evidence fusion, LLM explanation | `backend/app/pipeline/<stage>.py` | — |

Each folder's README says how it connects.

## Tooling

- Node: `/opt/homebrew/opt/node@24/bin` (on PATH via `~/.zshrc`). Python: `/opt/homebrew/bin/python3.12`.
- Never use Anaconda's `python3` for the backend — always `backend/.venv/bin/python`.
- Pin exact versions in `backend/requirements*.txt`.
- Commit after each working step.
