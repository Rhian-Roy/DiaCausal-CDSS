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
.venv/bin/python -m pytest tests/engine -q                                      # 190 tests
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
`#results`, `#learn` still work. `.venv/bin/python -m pytest tests/web -q` (26 tests; the two browser tests
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
the real function and change its one line in the registry (`stubs()` lists what is still a pass-through: nothing since P25;
the input guards (P15), the prompt builder (P22), the full output checks (P23), the evidence levels (P24) and the SHAP drivers (P25) are real).
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

`diacausal/llm/providers/ollama.py` only TALKS to a local Ollama server (`request_draft`): `POST /api/generate` with the JSON schema of
`AnswerDraftV1` in `format`, `options {temperature 0, num_ctx 4096}`, `stream false`, a 60 s timeout (all read from
`diacausal/llm/llm.yaml`, where `provider` is `template` by default and the two candidate model TAGS live: **never type a tag
anywhere else**; a test greps for it). The model is used only when BOTH `llm.yaml provider: ollama` AND the request's `mode: ollama`
say so. What comes back is NOT trusted: the output guards layer runs the seven checks of plan 8.10 on it (next section) and the template
answers instead of anything that fails. The prompt is plan 8.9 (`prompt.v2.txt`, saved verbatim in docs/PROMPT_TEMPLATE.md), built by
`prompt_builder.build_llm_prompt(request, eligible, causal, drivers, evidence)` (P22; see "Prompt builder" below).
`python scripts/bench_llm.py --model candidate_a|candidate_b|--all` runs the 20 golden questions
(`eval/llm_golden.csv`, a draft for Members B and D to review) and writes `results/llm/`. Needs Ollama running with the tags pulled
(`ollama pull <tag from llm.yaml>`); the tests use a fake server and need neither. The website never uses a model.

## Output guards (built, P23) — see docs/TESTING.md "Output guards"

`diacausal/guards/output_guards.py` `run_output_guards(text, passages=, number_sources=, eligible=, causal=, drivers=, min_support=)` runs the
seven checks of docs/PLAN_2026-10.md 8.10 on a model's draft and returns a `GuardedDraftV1`: 1 parse (AnswerDraftV1), 2 citations (each claim
cites retrieved chunk IDs it is supported by: a bad claim is DROPPED, none left = ABSTAIN), 3 numbers (every number is in the causal output
or the drivers, or is a cited page or version; fails the whole draft), 4 dose_threshold, 5 excluded_option (an excluded option described
positively), 6 insufficient_wording (effect wording for an option marked insufficient), 7 identifier_causal (an identifier = BLOCK; causal
wording about a driver = fallback). All of 2 to 7 always run, so every failed ID is recorded. Word lists and patterns are in
`diacausal/guards/output_guards.yaml` (own file: `data/params.yaml`'s hash feeds `web/model.json`); 5, 6 and the causal half of 7 are WORD
LISTS that catch the obvious wordings, not every paraphrase. This module never imports `diacausal.llm` (a test enforces it) and `sentences` /
`check_answer` in it are mirrored by `web/explain.js`: change those two together with it, the rest is Python only.
The explanation layer asks the model (`ctx.model_reply`); the output guards layer's `full output checks` part calls `diacausal/llm/answer.py`
`resolve`: PASS -> `diacausal/output/parser.py` keeps only the question context, at most 4 claims and the limitations; anything else ->
`template_instead(...)`. `AnswerCardV1` carries `fallback_used`, `failed_checks`, `fallback_reason` (a CODE) and `dropped_claims`; the
effects table always comes from `CausalOutputV1`. The trace has `[rid] output guards: model draft FALLBACK checks=numbers reason=GUARD_NUMBERS`
(codes only). **Never log or keep the model's text.**

## Prompt builder (built, P22) — see docs/PROMPT_TEMPLATE.md

`diacausal/llm/prompt_builder.py` `build_llm_prompt` fills the plan 8.9 template from `AskRequestV1`, `EligibleOptionsV1`, `CausalOutputV1`,
the DRIVERS mapping (empty until P25) and `EvidenceBundleV1`, and returns a `BuiltPrompt` (text, token estimate, which passages were shown,
shortened or left out, and the `number_sources` the number check reads). The explanation layer's `prompt builder` part (no longer a stub)
builds it **only when the model will be asked**. The budget is **1,900 tokens, estimated as words x 1.4** (`prompt_budget_tokens`,
`tokens_per_word`, `max_passages` in `llm.yaml`); at most 5 passages, cut at SENTENCE ENDS (a passage whose first sentence does not fit is left
out); the question, patient summary, causal JSON (minified) and drivers are never shortened. Every `<` from outside is written `&lt;`, line breaks
become spaces, the template is filled in one pass (a `{...}` in the question is inert), no patient identifier or request ID appears (a question
the identifier guard blocks raises `PromptError`). A `PromptError` (a CODE) sends the request to the template. The words x 1.4 estimate
under-counts the real token count (see the calibration in docs/PROMPT_TEMPLATE.md). Edit the template in `prompt.v2.txt` and plan 8.9 together;
`tests/llm/test_prompt_budget.py` compares them and a snapshot (`UPDATE_SNAPSHOTS=1` to accept a deliberate change).

## Evidence levels and the answer card (built, P24) — see docs/ANSWER_FORMAT.md

`diacausal/causal_inference/evidence_level.py`: plan 8.11's rule (Insufficient: propensity below 0.05, interval wider than 1.5, or the
retrieval abstained; Low: wider than 1.0, propensity below 0.10, or fewer than 2 cited passages; Moderate otherwise; **High never on synthetic
data**, `load_rule` refuses `high_enabled: true`). The cut-offs are `data/params.yaml` group `evidence_level` (TEAM-SET; the two Insufficient
ones must equal `engine.overlap_min_propensity` and `engine.max_interval_width`, a test checks). `assess` gives the level and its one-line reason,
`abstain_card` the four lines of the 8.11 abstain card exactly; `web/engine.js` mirrors them word for word (`evidenceLevel`, `abstainCard`;
tests/web compares them). An option the engine abstained on for overlap now carries `confidence.propensity` (never an estimate) so the card can
quote it. The `evidence levels` part runs in the formatter layer (after retrieval); an Insufficient option shows NO estimate on the card.
`AnswerCardV1` gained `cautions` (check-first rules with ID and source). The website builds the same card (`web/card.js`, validated against
AnswerCardV1 in tests/web) and draws screens 17 (leader: interval vs DPP-4i excludes 0, HbA1c only), 21 (no clear difference, trade-offs first)
and 19 (no estimate) in `web/app.js` `renderCard`, in Patient Details (Compare, and a question with the patient filled in) and Investigate.
No inline style: glyph positions are set through the CSSOM. The benchmark writes `results/evidence_level_coverage.csv` (interval coverage by
level; shown on the Analysis tab).

## Drivers of the estimate, version C (built, P25) — see docs/XAI_PLAN.md sections 3 and 4

`diacausal/xai/cate_shap.py`: exact SHAP of the DR-learner's LINEAR final stage, per comparison: `phi_j = beta_j (x_j - mean_j) / scale_j`,
base = `beta_0` (the cohort's average effect), `base + sum(phi) = estimate` (raises above 1e-9; `shap.LinearExplainer` with
`shap.maskers.Independent(X, max_samples=len(X))` agrees to 1e-9 in tests/xai). 95% interval of each contribution from the final stage's HC3
covariance (`phi ± z |(x - mean)/scale| sqrt(V_jj)`), same assumptions as the engine's interval, no bootstrap. A driver is CLEAR when that interval
excludes zero; the card shows up to `xai.max_drivers` (params.yaml, TEAM-SET, 3) clear drivers per option against DPP-4i, largest first, never
padded, only for options shown with an estimate, plus "all other details together" (joint interval). `web/engine.js` `explainEffect`,
`effectDrivers`, `otherDetails` mirror it (tests/web: 155 patients, 1e-9). The pipeline's `shap drivers` part is real; drivers also go to the
prompt and the number check. **Drivers describe the estimate, never a cause.** Version C's metrics: `python -m diacausal.xai.cate_shap_benchmark
[--quick]` -> `results/xai/causal_shap_metrics.csv` (incl. `modifier_top3_overlap`), `causal_shap_presets.csv`. The pipeline must never import
`cate_shap_benchmark` or version A (it borrows A's metric helpers; a test checks).

## XAI with RAG, and the A–D table (built, P26)

- **Drivers steer retrieval:** each comparison's top driver joins the search as ONE extra keyword ranking
  (`query_processing.add_drivers`, terms in `knowledge_sources/driver_terms.csv`, every term checked IN-CORPUS). It only REORDERS the question's
  own candidates: abstention, the candidate pool and the coverage check stay the question's (tests/rag/test_driver_queries.py). The website keeps
  the plain search (`web/evidence.js` has no plan).
- **Prompt and guards:** DRIVERS (P25) is in the prompt with plan 8.9 rule 6. The number check compares "88" and "88.0" as one number, but
  only trailing zeros after a point are dropped ("04" of a date never lets a "4" through). Causal wording about a driver is also caught by its
  card label (params.yaml `xai.labels`).
- **A–D table:** `python scripts/xai_ablation.py [--quick]` (diacausal/xai/ablation.py) runs A (XAI-only), B (engine), C (B + exact SHAP)
  and D (C + retrieval and writing) on the 20 benchmark cohorts and writes `results/xai_ablation.csv` (version, metric, comparison, mean, 95% t-interval,
  n_reps), `results/xai/ablation_chart.png` and `shap_A_vs_C.png`. B's numbers repeat under C and D. D's retrieval and writing rows come from
  fixed question sets (`n_reps` 0). `driver_passage_hit_rate` stays EMPTY until Members B and D write `eval/xai_driver_evidence.csv`.
  The Analysis tab shows the table and both charts; Guide → Cautions has the SHAP sentence. Rerun after any change to params.yaml.

## Licences of the Indian sources (P19, DONE except two open items) — see docs/LICENCE_REGISTER.md

`knowledge_sources/sources.csv` rows S02, S04, S05, S06, S18 carry the 9 Oct 2026 audit: S02 `cleared_ingest` (conditional CC BY-NC-SA, not yet
confirmed by a member, nothing ingested), S04 and S05 `verbatim_only`, S06 `unknown`, S18 `not_allowed` until PMBI replies. **Never ingest or
display anything whose bucket is not `cleared_ingest` and confirmed** (a test checks the manifest and `web/evidence.json`). **Open:** NPPA prices
not retrieved; PMBI permission for Jan Aushadhi prices. Until both are cleared `data/prices.csv` stays empty and the UI says "price
unavailable". Never copy a price, a dose or a licence term from memory; the audit files live outside the repo in `Docs/licence_audit_2026-10-09/`.

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
