# DiaCausal — working rules

@AGENTS.md

Research prototype chatbot for clinician evaluation; **not a marketed medical device; not
for unsupervised clinical use.** That sentence appears on every screen, in every chat reply
(`intended_use`) and in the API docs.

## Layout

- `frontend/` — React + Vite + TypeScript + Tailwind v4 + shadcn/ui (Node 24 LTS)
- `backend/` — FastAPI + Pydantic v2 on Python 3.12, in its own venv at `backend/.venv`
- `design/` — the screens to match (`chat.html` / `login.html` hold the exact colours, fonts, spacing)
- `legacy/` — the earlier 2-arm research code (`causal_engine/`, notebooks, scripts; restructure step 1). Its tests run from
  inside it (`cd legacy && ../.venv/bin/python -m pytest tests -q`); nothing under `diacausal/` may use it. `knowledge_sources/` holds
  `sources.csv` (the licence register) and `corpus/`. The backend will call `diacausal/causal_inference/` and `diacausal/rag/`
  instead (see "Not built yet" below)

All commands run from the repo root. The `( ... )` keeps each `cd` inside its own line,
so a whole block can be pasted at once.

## Setup (once per checkout — `.venv` and `frontend/node_modules` are not in git)

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
Check the table with `(cd backend && .venv/bin/python -m app.clinical.check)`.

## Deployment (built) — see docs/DEPLOY.md and docs/explain/11-deploy.md

`docker compose up --build -d` serves the page and the API from **one origin** with HTTPS
in front (Caddy). Security headers live in `backend/app/web.py` only; `/docs` is off when
`DIACAUSAL_ENV=production`; secrets come from `.env` at run time, never from the image.
The evaluation pack is `eval/` (25 synthetic vignettes + the SUS and feedback forms).

## Causal engine v0.3 (built, standalone) — see docs/CAUSAL_PLAN.md

`diacausal/causal_inference/` (with `diacausal/config.py`, `diacausal/guards/rules_loader.py`; the old `diacausal_engine/` holds shims) compares three options added to metformin (SGLT2i, DPP-4i, sulfonylurea)
for one patient: the expected 6-month HbA1c change with a 95% interval (plus secondary outcomes:
weight change in kg and hypoglycaemia risk in %, each with a 95% interval; an option whose range is
wider than `engine.max_interval_width` abstains as "too uncertain"). It is the "Causal
Inference Pipeline" column of the team flow chart and returns a structured **Causal Output**
(`schemas.CausalOutput`: APPLICABLE/NOT_APPLICABLE, intervention, outcome, effect, confidence,
assumptions) for the Evidence Fusion layer. Separate venv at the repo root:

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-engine.txt   # once
.venv/bin/python -m pytest tests/engine -q                                      # 149 tests
.venv/bin/python -m diacausal.causal_inference.benchmark --quick                          # full: drop --quick
.venv/bin/streamlit run demo/streamlit_app.py                                   # the demo
.venv/bin/uvicorn diacausal.api.main:app --port 8001                          # POST /api/v1/recommend
```

Rules that must never be broken:

1. Decision support only; the clinician decides. Every screen and API response (errors too)
   shows: "Research prototype for clinician evaluation; not a marketed medical device; not for
   unsupervised clinical use."
2. Safety rules run **before** any estimate. The engine's contraindication and kidney-function
   thresholds live only in `data/rules.csv` (Part 6 of docs/02_Causal_Engine_Build_Guide.md,
   verbatim; a test compares them), each with a source. Never hard-code or invent them (a test
   scans the code). An excluded option is never estimated. Never show drug doses (output check +
   tests). The chat app still uses `backend/app/clinical/guardrails.v1.yaml`; the tables were merged on 4 Oct 2026
   (docs/RULES_MERGE.md): `data/rules.csv` (R01–R11) is never weaker than the YAML (a test checks it) and the stricter
   action wins until the doctor decides; every rule not merged is listed there with its reason.
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

## Website (built) — see docs/WEBSITE.md

Live at https://diacausal.netlify.app. `web/` is a static phone-first PWA; `web/engine.js`
mirrors `recommend.py` using `web/model.json` from `python -m diacausal.causal_inference.export_web`, and
`web/evidence.js` mirrors `diacausal/rag/retrieve/hybrid.py` and `diacausal/rag/index/` using `web/evidence.json` from
`python -m diacausal.rag.export_web` (rerun after any change; `tests/web` fails if stale).
Never type a threshold into `web/*.js`; no inline script or style (strict CSP in `web/netlify.toml` =
`web/vercel.json`). Accounts: Supabase project `diacausal` (`supabase/migrations/`, RLS, admin approval,
TOTP); `web/auth.js` + `account.js`; Patient Details and Investigate need an approved account. **Never commit
the Supabase key**: `web/config.json` stays `"accounts": "off"`; `scripts/web_config.py` writes the
deploy copy only. Patient values and questions never leave the device (the website has no online model: P07 removed
the button, P08 removed the Edge Function).
`web/explain.js` mirrors `diacausal/llm/providers/template.py` and `diacausal/guards/output_guards.py` (template + citation checker).
Look: `design/screens-v2/` is the only design source (`handoff/HANDOFF.md`); colours, fonts and spacing come
only from `web/styles/tokens.css` (copied from the handoff); fonts are self-hosted in `web/fonts/` (SIL OFL).
Tabs: Patient Details, Investigate, Analysis, Guide, About (`#patient-details` …); `#try`, `#evidence`,
`#results`, `#learn` still work. `.venv/bin/python -m pytest tests/web -q` (24 tests; the two browser tests
need Node, `tests/e2e/node_modules` and Chromium or Google Chrome). Full chat app hosting: docs/HOSTING_CHAT_APP.md.

## API contract v1 (built) — see docs/INPUT_RANGES.md and docs/PLAN_2026-10.md §8.4

`diacausal/api/schemas/` holds the v1 Pydantic models (`PatientV1`, `AskRequestV1`, `GuardResultV1`,
`EligibleOptionsV1`, `CausalOutputV1`, `DriverV1`, `EvidenceChunkV1`, `EvidenceBundleV1`, `LLMRequestV1`,
`AnswerDraftV1`, `GuardedDraftV1`, `AnswerCardV1`): `schema_version` "1.0", unknown fields rejected.
`CausalOutputV1` is the engine's `CausalOutput` by subclassing (never rename its fields); it only adds optional
per-option `drivers`. They generate `openapi.json` (`scripts/export_openapi.py`), which generates
`web/types.d.ts` (`scripts/make_types.sh`, openapi-typescript 7.13.0); `tests/contract` (64 tests, in CI) validates
every example in `tests/contract/examples/` and fails if either generated file is stale. `PatientV1` ranges are
TEAM-SET plausibility bounds from `docs/INPUT_RANGES.md` (clinical thresholds stay in `data/rules.csv`). The chat
app's `backend/app/schemas.py` and the engine API's own models are unchanged; P14 builds `/api/v1/ask` on these.

## Pipeline and `/api/v1/ask` (built, P14) — see docs/PLAN_2026-10.md sections 8.3 to 8.5

`POST /api/v1/ask` (`diacausal/api/routes_v1.py`, in the same app as `/recommend`: `uvicorn diacausal.api.main:app`) runs
`diacausal/orchestrator/pipeline.py`, which calls the layers **only through `diacausal/registry.py`** (`LAYERS`, in order:
input guards, rules, causal engine, retrieval, explanation, output guards, formatter) and returns `AnswerCardV1`.
Layers are `fn(context) -> None` in `orchestrator/layers.py`; stubs are in `orchestrator/stubs.py`. To replace a stub, build
the real function and change its one line in the registry (`stubs()` lists what is still a pass-through: input guards P15,
SHAP drivers P25, evidence levels P24, prompt builder P22, full output checks P23).
Every layer runs inside `diacausal/tracing.py` (`layer(name, request_id)` or `@traced`): `[rid] entered X layer`,
`executing`, then `passed (N ms)`, `abstained ... reason=CODE` or `failed ... error=ExceptionClass`. A layer that correctly
cannot go on raises `AbstainSignal(CODE)` (a code, never free text). **Never log patient values, the question, prompts,
passages or secrets**: only IDs, layer names, statuses, codes, durations and exception class names. The route turns any
internal error into a plain 500 with the request ID (a pydantic error message would repeat the input). Tests: `tests/orchestrator` (CI runs them).

## Input guards (built, P15) — see docs/PLAN_2026-10.md section 8.6

`diacausal/guards/input_guards.py`: seven deterministic guards (scope, identifier, red flag, injection, range and unit, length and
language, dose request), each returning `GuardResultV1`; `run_input_guards` runs all seven (never stopping early) and lists them in
the order of 8.6. The word lists (identifiers, emergency phrases, out-of-scope topics, foul language, the "not"/"history of" cues) are
read from `shared/guard_rules/rules.v1.json`, the same file the chat app uses: edit them there. The numeric triggers and the new lists
(length, language share, glucose 54 and 400 mg/dL, honorifics, injection phrases, dose patterns, the drug-in-general words) are in
`data/params.yaml` section `guards`, all TEAM-SET. A block stops the request in the pipeline's first layer (`/ask` answers HTTP 422:
`message` plus one `problems` entry per blocking check; an emergency is shown first). **A message never repeats what matched.**
A question framed as general drug knowledge ("can SGLT2 inhibitors cause ketoacidosis?") is not an emergency unless a present-state
word is also there; `tests/guards/test_shared_cases.py` keeps every answerable RAG gold question passing and every dose question refused.

## Query processing (built, P16)

`diacausal/rag/retrieve/query_processing.py` turns the question into a `QueryPlan`: normalise (NFKC, one dash, case folded),
**append** abbreviations and spelling variants from `knowledge_sources/query_synonyms.csv` ("DKA" also searches "diabetic
ketoacidosis"; `status` IN-CORPUS means every word of the expansion is in the corpus, a test checks it) and brand-to-generic
names from `knowledge_sources/brand_generic.csv`, and split into at most 3 sub-queries (never where the second part points
back with "it", "they", "this"; it lost the subject of a gold question). **The expanded sub-queries feed BM25 only; the vector
search always gets the original question** (`Retriever.search(question, plan)`; without a plan it is the search it always was,
which is what `web/evidence.js` mirrors). **`brand_generic.csv` holds no brand names: every row is `TODO-VERIFY` and only a row
with a brand and status VERIFIED ever applies. Never write a brand name from memory; Member B verifies them against a
CDSCO or manufacturer label.** A question word counts as covered if it or a word of its expansion is in the passages.
`python -m diacausal.rag.evaluate` runs the gold questions through the plan, as the pipeline does.

## XAI baseline, version A (built, P17) — see docs/XAI_PLAN.md and results/xai/README.md

`diacausal/xai/baseline.py` (plus `truth.py`, the true effect modifiers derived from `params.yaml`): the benchmark's S-learner
(HistGradientBoostingRegressor, engine settings) trained on FACTUAL data only (12 features + one-hot drug -> observed HbA1c change),
asked "what if drug a?" by switching the drug columns, limited to the options the SAME rules leave; the lowest prediction is its
pick; it never abstains. TreeSHAP in `tree_path_dependent` mode (exact; the interventional mode is off by a constant ~0.002 on this
model class with shap 0.52.0) and LIME (seeded, 10 seeds per preset). Scored against the true potential outcomes:
`python -m diacausal.xai.baseline [--quick]` writes `results/xai/` (needs `pip install -r requirements-xai.txt`: shap 0.52.0 and
lime 0.2.0.1 are pinned there and NOT in requirements-engine.txt; `shap`, `lime` and matplotlib are imported lazily so the module
imports without them). **Version A is a baseline for the Analysis tab only: never import it from `web/`, the API, the pipeline or
anything a doctor sees (a test scans for it).** SHAP and LIME explain models, not causes. CI job `xai` runs `tests/xai`.

## Dense search (built, P18, OFF) — see docs/RAG_DENSE.md

`diacausal/rag/index/dense.py` embeds every chunk once with a local sentence-embedding model (`bge-small-en-v1.5` or
`pubmedbert-base-embeddings`, both chosen in `diacausal/rag/dense.yaml`; MIT and Apache-2.0) and saves `embeddings.npy`,
`chunks.jsonl`, `index_meta.json` under `knowledge_sources/index/dense/<model>/`; `hybrid.py` adds its ranking to the reciprocal
rank fusion **only when `dense.yaml` says `enabled: true` (it is false)**. Dense search only reorders what the keyword searches
found and never changes abstention; it is given the original question; no dose text is embedded; a stale index is an error. The
website and `config.yaml` are untouched (own file, so `web/evidence.json` does not change). Libraries: `requirements-dense.txt`
(torch; not needed by CI, the engine or the website). `python -m diacausal.rag.evaluate --dense-ablation` writes
`results/rag_dense_eval.csv` and `rag_dense_paired.csv` (recall@5, MRR, nDCG@5, dev / held-out split): no clear gain yet.
Never copy code from DiaCausal-RAG-Core.

## Source-aware ranking (built, P19, OFF) — see docs/RAG_RANKING.md

`diacausal/rag/retrieve/ranking.py` + `diacausal/rag/ranking.yaml` (`enabled: false`; its own file so `web/evidence.json` and the
website do not move): BM25 top 20 (per sub-query) + dense top 20 (if `dense.yaml` is on) + TF-IDF in full -> reciprocal rank fusion
(k = 60) -> re-sort by (fusion score rounded to `fusion_round_decimals`, `authority_tier`, `india_relevance`, section match,
patient-condition match) -> only the latest version of a source. The tiers are new columns of `knowledge_sources/sources.csv`
(values proposed from each row's issuer and kind of document, unknowns marked UNKNOWN / unknown; Member B and the doctor must
confirm them; never invent one). `Retriever.search(question, plan, conditions)`; `/ask` passes the patient's yes/no conditions.
Only order changes: candidates and abstention are the keyword ranking's. Tuned on the train split of `eval/rag_gold.csv` only
(`python -m diacausal.rag.evaluate --ranking-tune`, `--ranking-ablation`); results in `results/rag_ranking_*.csv`: no demonstrated
gain, so it ships off. Switching it on makes Python differ from `web/evidence.js` (P27).

## Local model via Ollama (built, P21, OFF) — see docs/LLM_BENCH.md

`diacausal/llm/providers/ollama.py` asks a local Ollama server for a structured answer: `POST /api/generate` with the JSON schema of
`AnswerDraftV1` in `format`, `options {temperature 0, num_ctx 4096}`, `stream false`, a 60 s timeout (all read from
`diacausal/llm/llm.yaml`, where `provider` is `template` by default and the two candidate model TAGS live: **never type a tag
anywhere else**; a test greps for it). The model is used only when BOTH `llm.yaml provider: ollama` AND the request's `mode: ollama`
say so. **Any** error, timeout, bad HTTP status, invalid JSON, schema failure, a claim that cites a passage that was not shown or is not
supported by it, or a number that is not in the causal output (plan 8.10 check 3) falls back to `providers/template.py`; the reply
carries `fallback: CODE` and never the model's text. The prompt is a plain version of plan 8.9 (`prompt.v2.txt`, `build_json_prompt`;
P22 refines it). `python scripts/bench_llm.py --model candidate_a|candidate_b|--all` runs the 20 golden questions
(`eval/llm_golden.csv`, a draft for Members B and D to review) and writes `results/llm/`. Needs Ollama running with the tags pulled
(`ollama pull <tag from llm.yaml>`); the tests use a fake server and need neither. The website never uses a model.

## Not built yet — where each piece goes

| Piece | Backend | Frontend / other |
|---|---|---|
| Causal engine in the chat app (October) | `backend/app/pipeline/causal_engine.py` calls `diacausal.causal_inference` on `ctx.options` only | designs 17 and 19; `contract.ts` + `schemas.py` together |
| RAG in the chat app (built standalone in `diacausal/rag/` and `diacausal/llm/`: licence gate, WHO 2018 + FDA S08/S19–S23, sentence-aware chunks, BM25 + TF-IDF, RRF, coverage abstention, `explain.py` template/Ollama + citation checker, `eval/rag_gold.csv` + `evaluate`; `tests/rag` 33; website Evidence tab). Still to do: switching dense search on (built, off), reranker, doctor review of the gold set | `backend/app/pipeline/rag_retrieval.py`, `llm_explanation.py` call `diacausal_rag` | `docs/03_RAG_Build_Guide.md`; only `cleared_ingest` sources |

Each folder's README says how it connects.

Restructure progress (docs/RESTRUCTURE_PLAN.md): steps 1 to 7 are done. `diacausal/config.py` is the one place for `ROOT`,
`DATA_DIR`, `WEB_DIR`, `RESULTS_DIR`, `KNOWLEDGE_DIR`, `ARMS`, `CONTRASTS`, the params loader and `load_rag_config`;
`diacausal/__init__.py` holds `INTENDED_USE` and `__version__`; `dag`, `schemas`, `cohort`, `propensity`, `estimators`, `dr_learner` (split out of estimators), `fitting`, `refute`, `metrics`, `recommend`, `figures`, `benchmark` and `export_web` are in
`diacausal/causal_inference/` (the engine's FastAPI app is `diacausal/api/main.py`; `uvicorn diacausal.api.main:app`). The RAG code is `diacausal/rag/`
(`ingest/` = `chunking`, `licence_gate`, `pdf_text`; `index/` = `bm25`, `tfidf`; `retrieve/` = `hybrid`, `rerank`; `evaluate`, `export_web`,
`sources_table`, `config.yaml`). The explanation writer is `diacausal/llm/` (`explain` = the switch, `prompt_builder` + `prompt.v1.txt`, `providers/template`, `providers/ollama`) and the citation checker
`sentences` / `check_answer` is `diacausal/guards/output_guards.py` (web/explain.js mirrors it); `diacausal_rag/` now holds only shims, the rules loader is `diacausal/guards/rules_loader.py`. The old `diacausal_engine.*` paths of the moved modules are shims
(the same module object, or for the split `estimators` a list of re-exports; `tests/test_shims.py`). New code imports from `diacausal`.

`diacausal/registry.py` lists every importable module; `tests/test_imports.py` imports each one and fails if a module is
missing from the list. Update it whenever a module moves (docs/RESTRUCTURE_PLAN.md).

## Tooling

- Node: `/opt/homebrew/opt/node@24/bin` (on PATH via `~/.zshrc`). Python: `/opt/homebrew/bin/python3.12`.
- Never use Anaconda's `python3` for the backend — always `backend/.venv/bin/python`.
- Pin exact versions in `backend/requirements*.txt`.
- Commit after each working step.
