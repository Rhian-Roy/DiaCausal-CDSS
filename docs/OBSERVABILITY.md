# Observability: what each request actually did

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

The **Observability** screen (`#observability`, the link at the top right of every page) shows the real execution record of each
request: which steps ran, in which order, inside which other step, how long each took, whether it completed, abstained (with its
code), failed (with the error's class name), was skipped or never reached, and what it produced as IDs, codes, counts, versions and
settings. Every record is written by the code while it runs. Nothing on the screen is an example or a reconstruction.

Member C (full stack), with Member D (safety): Member D should review the "never recorded" list below.

## 1. Where the records come from

| Source | What it records | Where it is kept | Who can read it |
|---|---|---|---|
| **This browser tab** (`web/trace.js`) | every Compare (and each live update), every question in Patient Details, every Investigate search, as run on this device by `guards.js`, `engine.js`, `evidence.js`, `explain.js` and `card.js` | memory only, newest 50; a reload or a sign-out clears them; never stored, never sent | whoever is using this tab |
| **This computer's server** (`diacausal/observability/`) | every `POST /api/v1/ask` the DiaCausal server answers (clinic mode, `scripts/start_clinic.*`) | `logs/observability.sqlite3` on that computer (not in git, like `logs/audit.jsonl`); newest 1,000, none older than 30 days | only a client on that computer (127.0.0.1 or ::1); anything else gets HTTP 403 |

On the public website there is no server, so the page never asks for traces: it shows the tab's own runs. On the clinic laptop the
screen offers both. A question the browser sent to the server has a **server pipeline** span with the server's trace ID, and the
button "Open the server's trace of this request" opens the server's record of the same request (the request ID is the same in both,
in the console trace and in the `X-Request-Id` header; the server also sends `X-Trace-Id`).

## 2. What a trace looks like

A **trace** is one request. It holds **spans**, one per piece of work, in the order they started; a span's `parent_id` names the span
it ran inside. The server's `/ask` trace, as the code runs it (`diacausal/orchestrator/pipeline.py`, strictly one layer after the other,
nothing in parallel):

```
input guards                 layer  guards   diacausal.orchestrator.layers:input_guards_layer
rules                        layer  ci       diacausal.orchestrator.layers:rules_layer
causal engine                layer  ci       diacausal.orchestrator.layers:causal_layer
  safety rules               step   ci       data/rules.csv applied (RuleTable.apply)
  cohort support check       step   ci       propensity.support_check
  propensity overlap         step   ci       propensity.predict + overlap_check (threshold 0.05 from params.yaml)
  DR-learner estimate        step   ci       dr_learner.DRLearner.predict (skipped with NO_OPTION_LEFT_TO_ESTIMATE when no option is left)
  interval width check       step   ci       the engine's own limit (params.yaml engine.max_interval_width)
  secondary outcomes         step   ci       Engine._secondary (weight, hypoglycaemia)
  engine output check        step   ci       recommend.check_output
  shap drivers               part   ci       layers.shap_drivers_part (exact SHAP of the causal estimate, version C)
retrieval                    layer  rag      layers.retrieval_layer
  query processing           part   rag      layers.query_processing_part
explanation                  layer  llm      layers.explanation_layer
  prompt builder             part   llm      layers.prompt_builder_part (builds a prompt only when the local model will be asked)
output guards                layer  output   layers.output_guards_layer
  full output checks         part   output   layers.full_output_checks_part (the seven checks, only on a model's draft)
formatter                    layer  output   layers.formatter_layer
  evidence levels            part   output   layers.evidence_levels_part
```

A request the input guards stop has the first span "abstained" with the guard's code (e.g. `RED_FLAG`) and the other six layers as
**not run**, with no time. A layer that raises an exception is "failed" with the exception's class name, and the layers after it are
"not run". The browser's Compare trace has the same idea with the browser's own steps (input check, causal engine with the same seven
engine steps, evidence for each option, explanation, answer card, render), because `web/engine.js` reports the same steps through
an optional `opts.step` hook.

**Request status:** completed; **partial** (an answer was returned, but at least one layer abstained, e.g. the retrieval found no
passage that passed its checks); **blocked** (an input check stopped it, HTTP 422 on the server); **failed** (an error, HTTP 500);
**cancelled** (browser only: newer patient details replaced a live update before it was shown); **running**.

Each span's summary is what that step produced. For example the causal engine layer records each option's status, the rule IDs that
fired, why an option got no estimate (`LOW_OVERLAP`, `TOO_UNCERTAIN`, `OUTSIDE_COHORT`), the method, the comparisons made and the
versions (engine, params hash, rules hash, cohort); the retrieval layer records the status, the abstain code, the index version, the
search settings and each passage's chunk ID, source ID, licence bucket and its BM25, TF-IDF and fusion scores. **Retrieval scores rank
passages against the question; they are not a measure of accuracy or clinical validity.**

The screen draws, for one trace: the header (IDs, times, status, HTTP status, versions), the **lifecycle** (the top-level steps as
boxes in order, coloured by status), **From the inputs to the answer** (what each stage handed on, each row naming the span it was read
from), and the **timeline** (every span with a bar for when it ran, indented under its parent, filterable by pipeline, each row opening
to its fields and summary). The engine card shows what the engine behind the traces was fitted on: the synthetic reference cohort
(n, seed, patients per arm, share below the overlap threshold), the treatment, outcome and adjusted variables with their roles in the
DAG, the models and the settings, plus the pipeline exactly as `diacausal/registry.py` lists it.

## 3. What is never recorded

The same rule as the console trace (`diacausal/tracing.py`) and the audit line: **no patient values, no question text, no passage
text, no prompt, no model reply, no keys.** A summary may hold numbers, booleans and short label strings only
(`recorder.safe` / `trace.js safe`: longer strings, or strings with other characters, become `<not kept>`); and every field is chosen by
name in `diacausal/observability/summaries.py` and `web/trace.js describe`. Sizes are allowed (the question's length in characters,
which patient fields arrived).

Per-patient numbers (each option's estimate and interval, its propensity, the drivers' contributions) stay on the answer card the
clinician sees. The trace records which options got an estimate and why the others did not. Cohort-level effects (ATE) are not
computed by a request at all: they come from the offline benchmark (`results/benchmark_summary.csv`, the Analysis tab). The engine
card's numbers describe the synthetic reference cohort and the configuration, never a patient.

Tests prove it: `tests/orchestrator/test_observability.py` sends a patient with HbA1c 9.87 and the questions "zebra-test" and "…quokka?"
through `/api/v1/ask` and searches the SQLite file's bytes, the stored JSON and every observability endpoint's reply for them;
`tests/web/observability_check.cjs` types HbA1c 9.87 and three questions into the real page and searches the browser's records and
the screen's text.

## 4. SHAP, LIME and this screen

SHAP and LIME **explain a model's prediction**; this screen **records what the system did**. They are different things and neither
replaces the other. The drivers of each estimate (exact SHAP of the causal estimate, version C, `diacausal/xai/cate_shap.py`) are a
real step of the request, so they appear as the **shap drivers** span with the method, the comparator and how many clear drivers each
option has. The XAI-only baseline (SHAP + LIME on a predictor, version A) is never run for a request; its results are on the Analysis
tab. Observability runs no SHAP, LIME or any other model computation of its own.

## 5. How it works in the code

| Piece | File |
|---|---|
| Trace and span recording (context variable, so concurrent requests never mix; `step()` is a no-op when no trace is running) | `diacausal/observability/recorder.py` |
| What each layer and part produced (IDs, codes, counts, versions, settings) | `diacausal/observability/summaries.py` |
| The store (SQLite from Python's standard library; one write per request; retention) | `diacausal/observability/store.py` |
| The engine card (read once at server start from the fitted engine) | `diacausal/observability/engine_facts.py` |
| The layers as spans, and "not run" for the layers a stopped request never reached | `diacausal/orchestrator/pipeline.py` |
| The parts as child spans (only while a trace runs) | `diacausal/registry.py` `part_function` |
| The engine's seven steps | `diacausal/causal_inference/recommend.py` `Engine.recommend` (`with step(...)` around the existing lines) |
| Trace start and finish, `X-Trace-Id` | `diacausal/api/routes_v1.py` |
| `GET /api/v1/observability/summary`, `/traces`, `/traces/{trace_id}`, `/engine` | `diacausal/api/routes_observability.py` |
| The browser's recorder and its summaries | `web/trace.js` |
| The browser's steps | `web/app.js` (`drawLive`, `compareCard`, `askInThread`, `askServer`, `searchAndShow`) and `web/engine.js` (`opts.step`) |
| The screen | `web/observability.js`, `#view-observability` in `web/index.html`, the "Observability" block of `web/styles.css` |

The API's list endpoint takes `q` (trace ID or request ID prefix), `status`, `pipeline` (`ci`, `rag`, `llm`, `output`) with an
optional `pipeline_status`, `since` / `until` (seconds since 1970), `problems=true`, `sort=time|duration`, `order=desc|asc`, `limit`
(1–200) and `offset`; it returns the list columns only, never the spans. A trace ID is 16 lower-case hexadecimal characters; anything
else is refused (422) without being repeated. The service worker never caches an `/api` reply.

**Settings.** `DIACAUSAL_OBSERVABILITY=off` switches recording and the endpoints off (404) on that computer. `DIACAUSAL_TRACE_DB=<path>`
moves the store (the tests use a temporary file for every test: `tests/conftest.py`). No new dependency: `sqlite3` is in Python's
standard library, and the browser side is plain JavaScript.

**Reliability.** Recording never changes what is computed: the card and the engine's output are byte-for-byte the same with recording
on and off (tested on the three demo patients), and the browser engine gives the same answer with and without its step hook (tested).
A trace that cannot be written (disk full, locked file) is logged by its exception class and the clinician's reply goes out unchanged
(tested). A summary that cannot be built becomes `summary_error: <class>` on that span; the work goes on.

**Cost.** The extra work is a few dictionary writes per step and one SQLite insert per request (about 2 ms). Measured on the
development container (26 Oct, 30 `/ask` requests each way over the three demo patients, after 3 warm-up requests): median 236.6 ms with
recording on, 246.2 ms off; mean 254.8 ms on, 252.9 ms off: the difference is within run-to-run noise. A first version re-read
`params.yaml` for one setting in the drivers summary and cost about 110 ms per request; the summaries now read settings from the
engine and the retriever already in memory, so nothing is loaded again for a trace.

## 6. How to use it

1. Open the website (or the clinic laptop's `http://127.0.0.1:8000`) and use it as usual: Compare, ask, search.
2. Press **Observability** at the top right. The summary counts what this tab ran (or, on the clinic laptop, everything stored there:
   choose "This computer's server (stored)").
3. Search by trace or request ID, filter by status or by the stage a request reached, show only errors and warnings, sort by time or
   duration, page through. **Refresh** reloads.
4. Press a trace ID to open it. Read the lifecycle left to right, then the table "From the inputs to the answer", then open any row
   of the timeline for its details. The chips show one pipeline at a time.
5. A recent error or warning in the list above the table opens its trace the same way.

## 7. Limits (honest)

- The retriever does not report how many candidates it scored before the top 5, so a trace lists the passages it returned, not the
  candidates. Changing the retriever to report them was out of scope (it would change `hybrid.py`, which `web/evidence.js` mirrors).
- A request the API refuses before the pipeline starts (HTTP 422 for a malformed body) has no trace: it never reached the code that
  starts one. The console still logs `[-] ask: rejected (N problems)`.
- Durations are wall-clock times on whatever computer ran the step; the browser's are rounded to 0.1 ms and depend on the device.
- The store is per computer, and the browser's records are per tab. There are no user accounts on the clinic server, so "only this
  computer" is the access rule; anyone who can use that computer can read its traces (which hold no patient data).
- The engine's internal steps inside `web/engine.js` are reported through a hook the engine calls; the other browser steps are timed
  around the calls in `app.js`. Loading `evidence.json` (cached after the first time) is not a separate span.

**How to explain this to the guide (3 lines):** Every request now leaves a step-by-step record of what really ran: the checks, the
safety rules, each step of the causal engine, the evidence search, the explanation and the output checks, with times and results.
It records structure only (IDs, codes, counts), never a patient's values or the question, and it never changes the answer. That lets
us show, for any answer, exactly how it was produced and where a request stopped or failed.
