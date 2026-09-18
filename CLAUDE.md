# DiaCausal — working rules

Research prototype chatbot for clinician evaluation; **not a marketed medical device; not
for unsupervised clinical use.** That sentence appears on every screen and in every API reply.

## Layout

- `frontend/` — React + Vite + TypeScript + Tailwind v4 + shadcn/ui (Node 24 LTS)
- `backend/` — FastAPI + Pydantic v2 on Python 3.12, in its own venv at `backend/.venv`
- `design/` — the screens to match (`chat.html` / `login.html` hold the exact colours, fonts, spacing)
- `causal_engine/`, notebooks, `RAG/` — earlier research code; the backend will call into it later

## Run (from the repo root, one terminal each)

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000   # API on :8000, docs at /docs
cd frontend && npm run dev                                          # page on http://localhost:5173
```

## Test

```bash
cd backend && .venv/bin/python -m pytest
```

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
- Every backend log line starts with `[client_trace_id]` (app/tracing.py).
  **Never log message text** — only sizes, stage results and IDs.

## Tooling

- Node: `/opt/homebrew/opt/node@24/bin` (on PATH via `~/.zshrc`). Python: `/opt/homebrew/bin/python3.12`.
- Never use Anaconda's `python3` for the backend — always `backend/.venv/bin/python`.
- Pin exact versions in `backend/requirements*.txt`.
- Commit after each working step.
