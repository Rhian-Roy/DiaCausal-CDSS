# How to know everything works

Three layers: **one command** checks almost everything automatically (part 1), a
**10-minute by-eye check** covers what only a person can judge (part 2), and part 3 says
honestly what is **not** tested yet. Part 4 fixes common problems; part 5 is how to
report one.

## Part 1 — the one command

| macOS / Linux | Windows |
|---|---|
| `python3 scripts/check_all.py` | `py scripts/check_all.py` |

(First time on a computer? Do the setup in [SETUP.md](SETUP.md) first.)

It takes a few seconds and prints `[PASS]` or `[FAIL]` per line, ending with
`ALL 43 CHECKS PASSED`. Those 43 lines are: 4 tool checks, 1 line for all 392 backend
tests, 1 line for all 238 frontend tests, build, lint, 33 live checks, the evaluation vignettes and 1 real-browser line. It starts its
own copy of the app on spare ports, so it does not disturb servers you already have
running.

It needs **Google Chrome** installed (section 8 drives it).

**On GitHub, automatically:** `.github/workflows/check.yml` runs the same two commands
(setup, then check) on Linux, Windows and macOS for every push and pull request, plus the
real-browser tests and a security audit (`pip-audit`, `npm audit`) on Linux. See the
green tick or red cross next to each commit, or the **Actions** tab.

### Which check proves which requirement

| Requirement | Proved by |
|---|---|
| Press Enter → console prints `input passed`, `ui guard passed`, `medical ui guard passed`, `output passed`, all with the same trace ID | Section 3: frontend test *"prints the four console lines with one trace ID and shows the reply"* (`frontend/src/pages/ChatPage.test.tsx`). By eye: part 2, step 2. |
| An empty message is blocked | Section 3 (browser side, never sent) and section 6 *"an empty message is blocked by backend_guard"* (server side) |
| The message goes to the Python backend through the API and a dummy reply comes back | Section 6 *"a question gets the dummy reply"*; section 7 *"a message sent via the page's /api reaches the backend"* |
| The reply appears in the chat | Section 3 (the page test finds the reply on screen). By eye: part 2, step 4. |
| The backend log prints the same trace ID | Section 6 *"backend log shows [id] on the request, every stage and the reply"*; backend tests in `backend/tests/test_logging.py` |
| Accept only `{"schema_version":"1.0","client_trace_id":…,"parts":[…]}` | Section 2: `backend/tests/test_validation.py` (20+ cases) |
| Unknown part types and text over 8000 characters are refused with a clear message | Section 2 and section 6 (*"image" part refused*, *over 8000 refused*) |
| Six stages in order; only the first and last run, the rest `skipped` | Section 2 (`test_chat.py`, `test_pipeline.py`) and section 6 |
| Foul language blocked (UI side, whiteboard "FOUL LANGUAGES … if found BLOCK"), medical allowlist wins, word never repeated | Section 2 `backend/tests/test_guard_rules.py`, section 3 `frontend/src/lib/guards.test.ts` + page test *"foul language fails the ui guard…"*, section 6 *"foul language is blocked by the server guard…"* |
| Medical UI guards: identifiers (notice 09), out of scope (10), emergency (11), language (12); same answer in browser and server | Sections 2 and 3 run all 47 cases in `shared/guard_rules/examples.v1.json` and 55 extra cases in `frontend/src/test/guardAgreement.json` on both sides; page tests *"guard notices (design/v1/09-12)"*; section 6 *"a patient identifier is blocked by the server guard"* |
| The guard rules version is logged with the trace ID, never the blocked word | Section 2 `test_rules_version_is_logged_with_the_trace_id`, section 6 *"the backend log shows the guard rules version…"* |
| Login page: user ID + password + CAPTCHA (Python `captcha` library, image + audio) | Section 3 `frontend/src/App.test.tsx` (*"first sign-in…"*, *"the CAPTCHA sits inside the form…"*); section 6 *"the CAPTCHA comes as an image and as audio"*, *"sign-in works…"* |
| MFA (6-digit code), backend authentication | Section 2 `backend/tests/test_auth.py` (wrong/reused code, lockout, timeouts…); section 6 *"sign-in works: user ID + password + CAPTCHA, then authenticator set-up and a 6-digit code"* |
| Wrong details → one message "Those details did not match" | Section 2 `test_wrong_password`, `test_unknown_user_gets_exactly_the_same_answer`; section 6 *"a wrong password gets…"* |
| Chat only for signed-in users; CSRF token required | Section 2 `test_chat_without_a_session_is_401`, `test_chat_without_the_csrf_header_is_403`; section 6 *"chat without signing in is refused (401)"*, *"…without the CSRF token is refused (403)"* |
| Master login = admin role (no shared login) | Section 2 `backend/tests/test_admin.py`; section 6 *"scripts/create_admin.py creates an admin account"* |
| Every chat request in the audit log (request_id + trace ID, no text) | Section 2 `test_every_chat_request_is_audited…`; section 6 *"every chat request is in audit_log…"* |
| Voice: Python speech-to-text, transcript into the box (never auto-sent), numbers marked, audio deleted | Section 2 `backend/tests/test_voice.py` (5 recorded clips through the real model, limits, deletion); section 3 `frontend/src/features/voice/voice.test.tsx`; section 6 *"speech-to-text: a recorded clip comes back as text"* |
| Patient panel: every field's range, both sides; unknown field refused; two patient parts refused | Section 2 `backend/tests/test_patient.py` (incl. a test that the browser's copy of the ranges matches the server's), section 3 `frontend/src/features/patient/patient.test.tsx`, section 6 *"the patient panel's details are accepted…"*, *"an impossible patient value is refused…"* |
| "New patient" clears the panel and the conversation | Section 3 *"New patient clears the panel AND the conversation"*, section 8 (real browser) |
| Patient values never logged (only which fields arrived) | Section 2 `test_patient_values_are_never_logged`, section 6 *"the log says which patient fields arrived, never their values"* |
| Clinical guardrails run before ranking; a "do not use" option never reaches the causal engine | Section 2 `backend/tests/test_guardrails.py` (one test per rule, plus the invariants), section 6 *"a contraindicated option is marked do-not-use, with its source"* |
| A rule with a TODO or no source never fires | Section 2 `test_the_incomplete_rule_is_refused_and_never_fires`, `test_strict_loading_raises_so_review_cannot_miss_it`; by hand: `.venv/bin/python -m app.clinical.check` |
| Without eGFR the stage abstains instead of guessing | Section 2 `test_without_egfr_the_stage_abstains_instead_of_guessing`, section 6 *"without eGFR the clinical guardrails abstain…"* |
| Every reply says the rules are a draft until a doctor reviews them | Section 2 `test_every_reply_says_the_table_is_a_draft`, section 3 `options.test.tsx`, section 6 |
| The deployed container works: HTTPS, security headers, no API docs in production, a body over 4 MB refused | Section 2 `backend/tests/test_health.py`; by hand: `docs/DEPLOY.md` checklist |
| The 25 evaluation vignettes behave as their table says | Section 8 (`eval/run_vignettes.py`, also runnable inside the container) |
| Two sign-in set-up requests at once give the same authenticator key | Section 2 `test_two_setup_requests_at_once_give_the_same_key` |
| Message text never written to the log | Section 2 (`test_message_text_is_never_logged`) and section 6 |
| The code type-checks, builds and has no lint problems | Sections 4 and 5 |
| The whole app really works in a real browser | Section 8: 9 Playwright tests in Google Chrome |
| Each stage says how long it took | Section 2 `test_every_stage_reports_how_long_it_took`, section 3 *"shows the time beside each stage"* |
| No known security problems in our libraries | The `audit` job in CI (`pip-audit`, `npm audit --omit=dev`), weekly Dependabot pull requests |
| Colours, fonts, layout match `design/` | By eye only: part 2, steps 1 and 7 |

**Are the tests themselves any good?** During development, AI review agents working under
our direction deliberately broke the code in small ways (skip a console line, reorder the
stages, stop trimming, let an empty message through, …) and checked that a test failed
each time. Where none did, a test was added (backend 46 → 53, frontend 41 → 49; commit
`4a3beec`). This is *mutation testing* done by hand — no mutation-testing tool (such as
mutmut or Stryker) has been run, so there is no mutation score yet.

You can also run the parts separately:

| What | Command (from the repo root) |
|---|---|
| Backend tests | `cd backend` then `.venv/bin/python -m pytest -v` (Windows: `.venv\Scripts\python -m pytest -v`; `-v` lists every test by name) |
| Frontend tests | `cd frontend` then `npm test` |
| Type-check + build | `cd frontend` then `npm run build` |
| Lint | `cd frontend` then `npm run lint` |

## Part 1b — the causal engine (its own command)

The 3-arm causal engine (`diacausal_engine/`, `demo/`, `data/`) has its own pinned
libraries and its own tests, so it does not need the chat app's setup:

```bash
python3.12 -m venv .venv && source .venv/bin/activate    # once
pip install -r requirements-engine.txt                    # once
python -m pytest tests/engine -q                          # about 3 min; must end "139 passed"
```

On GitHub the `engine` job in `.github/workflows/check.yml` runs the same tests, the quick
benchmark and `pip-audit` on Linux and macOS. `scripts/check_all.py` is unchanged (43 checks).

| Requirement | Proved by (`tests/engine/…`) |
|---|---|
| Every generator/engine number has a source and a status (CITED, ASSUMED-DIRECTIONAL, TEAM-SET); an unsourced one stops the program | `test_a_cohort.py`: *every_parameter_has_a_source*, *parameter_without_a_source_is_refused*, *invented_status*, *bare_number* |
| Synthetic cohort: 3 options, confounding by indication, all three true outcomes stored | `test_a_cohort.py`: *all_three_options_appear*, *confounding_by_indication_exists*, *true_potential_outcomes_are_stored* |
| The DAG decides what we adjust for; mediators never | `test_a_cohort.py`: *dag_adjustment_set_excludes_mediators*, *generator_only_uses_arrows_drawn_in_the_dag* |
| Asian-Indian BMI cut-offs (23 / 25) and plausibility ranges match the chat app | `test_a_cohort.py`: *bmi_cutoffs_match_the_backend*, *plausibility_ranges_match*; `test_h_demo.py`: *bmi_uses_asian_indian_cutoffs* |
| `data/rules.csv` is exactly Part 6 of the build guide; each rule has a source; bad rows refused; thresholds never in code | `test_b_guardrails.py` (all), incl. *no_clinical_threshold_is_typed_into_the_engine_code* |
| Safety rules run before any estimate; excluded options never get a number | `test_h_demo.py`: *safety_rules_run_before_the_estimate*; `test_j_invariants.py`: *excluded_options_always_cite_a_rule* |
| Cross-fitted multinomial propensity; propensity below 0.05 → "insufficient evidence" | `test_c_propensity.py` (all); `test_h_demo.py`: *rare_patient_gets_insufficient_evidence*; `test_j_invariants.py`: *low_propensity_always_means_insufficient_evidence* |
| Naive, IPW, matching, AIPW with 95% CIs; the correction works | `test_d_average_effects.py` (worked example −0.425 vs −0.15; viva IPW example; AIPW covers the truth) |
| DR-learner patient-level effects, each with a 95% interval | `test_e_dr_learner.py` |
| Bias, RMSE, coverage, PEHE, policy regret, balance | `test_f_metrics.py` |
| Benchmark writes `results/` (table, CSV, five figures) | `test_g_benchmark.py` |
| Every screen and API response shows the intended-use statement | `test_h_demo.py`: *demo_shows_the_intended_use*; `test_i_api.py`: *bad_requests_get_422…with_intended_use*, *unknown_route_still_carries_intended_use*; `test_j_invariants.py` |
| No drug doses anywhere | `test_h_demo.py`: *dose_pattern_catches_dose_text*, *rule_messages_themselves_contain_no_doses*; `test_j_invariants.py`: *no_reply_ever_contains_dose_text* (300 random patients) |
| Never green for "recommended"; red / amber / grey | `test_h_demo.py`: *demo_never_uses_green_success_boxes*; by eye (screens/) |
| Prices say "price unavailable" until confirmed | `test_h_demo.py`: *prices_stay_unavailable_until_confirmed* |
| API: unknown fields and implausible values rejected (422, plain English, value not echoed) | `test_i_api.py` |
| Logs and the audit trail never contain patient values | `test_h_demo.py`: *audit_log_records_decisions_but_never_patient_values*; `test_i_api.py`: *logs_carry_ids…no_patient_values* |
| No secrets in the repo; exact version pins | `test_j_invariants.py`: *no_secrets_are_committed*, *requirements_are_exactly_pinned* |
| Refutation (placebo treatment x20, random common cause, 80% subset) and E-value sensitivity; saved to `results/refutation.csv`, `results/evalues.csv` | `test_k_refute.py` |

**RAG early skeleton** (`python -m pytest tests/rag -q`, 13 tests, about 2 s):

| Requirement | Proved by (`tests/rag/test_rag_skeleton.py`) |
|---|---|
| Only sources with bucket `cleared_ingest` in `RAG/sources.csv` are ingested (IDF, ADA, NICE refused) | *only_licence_cleared_sources_are_ingested*, *real_licence_table_refuses_idf_and_admits_who* |
| Chunks never cross a section and carry source, version, section and page | *sections_are_never_mixed*, *long_sections_are_cut_to_the_chunk_size* |
| Hybrid BM25 + vector search with reciprocal rank fusion returns cited passages | *hybrid_search_finds_the_right_section_with_a_citation*, *reciprocal_rank_fusion* |
| Unsupported questions get INSUFFICIENT_EVIDENCE; passages with doses are withheld | *unsupported_questions*, *empty_index_abstains*, *passages_with_dose_text_are_withheld* |
| `docs/SOURCES.md` always matches the licence CSV | *sources_md_is_in_sync* |
| The committed corpus holds only `cleared_ingest` sources whose licence a team member confirmed (today S08, the FDA metformin/kidney communication); a draft licence is refused | *committed_corpus_holds_only_confirmed_licence_cleared_sources*, *a_draft_licence_is_refused_even_in_the_cleared_bucket* |

**Website** (`python -m pytest tests/web -q`, 16 tests, about 15 s; needs Node):

| Requirement | Proved by (`tests/web/test_web.py`) |
|---|---|
| `web/model.json` matches a fresh export of the engine (same params and rules hashes) | *model_json_is_fresh* |
| The browser engine gives the same statuses, rules and numbers as Python on 155 patients | *browser_engine_gives_the_same_answers_as_python* |
| Intended-use statement on the page; no dose text anywhere in the site | *site_files_carry_the_intended_use_and_no_doses* |
| No clinical threshold typed into the website code (all from `model.json`) | *no_clinical_threshold_is_typed_into_the_website_code* |
| Strict CSP holds (no inline script/style); Netlify and Vercel headers match | *no_inline_script_or_style_so_the_strict_csp_holds* |
| Installable (manifest, icons); every offline-cached file exists; results and docs copied | *installable_on_a_phone*, *every_file_the_offline_cache_lists_exists*, *results_and_docs_are_copied_for_the_site* |
| `web/evidence.json` matches a fresh export of the RAG index; the browser search gives the same passages, order and scores as Python on 40 questions | *evidence_json_is_fresh*, *browser_evidence_search_gives_the_same_passages_as_python* |
| Team details: B.Tech in Computer Engineering; Guide Mr. Rahul Jadhav | *team_details_are_correct* |
| Sign-in order: sign in → authenticator code → admin approval → intended use; Try it and Evidence are the locked pages; weak passwords refused | *sign_in_steps_come_in_the_right_order* |
| No account key in git (`config.json` says accounts off; the deploy script refuses to write into `web/`) | *no_account_key_is_committed* |
| The account code touches only the `profiles` table and two functions, never patient fields | *account_code_never_sends_patient_details* |
| Account database: row-level security, no direct writes, admin actions need the authenticator code, no clinical columns | *accounts_database_is_locked_down* |
| Works on an iPhone-sized screen: red, amber and grey cards, team details, Evidence answers with FDA citations and abstains when it should, local copy says sign-in is off, no sideways scrolling | *the_site_works_on_an_iphone_sized_screen* (skips without Chromium) |

## Part 2 — check by eye in a real browser (about 10 minutes)

Start both servers as in [SETUP.md, step 5](SETUP.md#5-try-it-yourself), open
http://localhost:5173 and the browser console. Put the browser and the backend
terminal side by side.

| # | Do | You should see |
|---|---|---|
| 1 | Look at the page next to `design/chat-desktop.png` | Dark pine-green top bar, serif "DiaCausal", "RESEARCH PROTOTYPE" badge, bold patient line with an "Example data" chip, a white message box with a mic and a green arrow button, the disclaimer under it |
| 1a | Look at the patient panel beside the conversation | "Patient details" with an **Example data** badge, the example patient filled in, "Category: Obese (≥25)" with the Asian-Indian cut-offs under it. Type `45` into HbA1c → a warning appears beside the field. Press **New patient** → panel and conversation both empty |
| 1b | Sign in as in [SETUP.md step 5c](SETUP.md#5c-sign-in-use-chrome) | Console: `login input passed`, `captcha passed`, `password passed`, then `mfa passed`; your name and **Sign out** top right |
| 2 | Type `HbA1c 8.4% on metformin. What should I add?` and press **Enter** | Console: four lines `[xxxxxxxx] input passed`, `… ui guard passed`, `… medical ui guard passed`, `… output passed` — the same 8 characters on each |
| 3 | Look at terminal 1 | Eight lines with that same `[xxxxxxxx]`: request received, six stages, reply sent. Your question's words do **not** appear |
| 4 | Look at the chat | "YOU ASKED" + your question; a white card "DIACAUSAL ANSWERED" with the dummy reply, "2 of 6 stages ran; the others are not built yet", and "Trace ID xxxxxxxx" matching the console |
| 5 | Press **Enter** on an empty box | "Type a question first." under the box; console shows `input passed` then a yellow warning `ui guard blocked`; nothing new in terminal 1 |
| 6 | Type a line, press **Shift+Enter**, type another | A new line in the box; nothing is sent |
| 7 | Open the device toolbar (**⌘⇧M** Mac / **Ctrl+Shift+M** Windows, with the console open), pick an iPhone | Compare with `design/chat-phone.png`: "PROTOTYPE" badge, short patient line, "Ask a question" placeholder |
| 7b | Press the **microphone**, say "HbA1c 8.4 percent on metformin, eGFR 62", press the square to stop | "Recording 0:03 / 0:30" while you speak, then the words appear **in the message box** (not sent) with the numbers marked underneath; console: `voice: … s recorded`, `voice: transcript put in the message box (not sent)` |
| 8 | Press **Tab** until the green send button is selected | A thick pine-green outline around it (keyboard users can see where they are) |
| 9 | Stop terminal 1 (**Ctrl+C**), then send a question | Red box "Couldn't get a reply … Check that the backend is running." Start terminal 1 again afterwards |
| 10 | Open http://localhost:8000 (needs internet: the page loads its look from a CDN) | The API's own documentation page (`/docs`); **POST /api/v1/chat → Try it out → Execute** sends a request by hand |

## Part 3 — what is not tested yet (and why)

| Not tested | Why |
|---|---|
| Docker | Not built yet (`docker/README.md`) |
| Voice with a real microphone and a real human voice | By hand only: the automated tests use five synthetic clips (`backend/tests/voice_clips/`) and, in the browser tests, a fake microphone |
| Scanning the QR code with a real phone | By hand only (SETUP.md step 5c); the automated checks compute the code from the key, as the phone would |
| The causal engine, RAG and the explanation | Not connected yet; they return `skipped` (prompts 06, 07, 09) |
| Whether the clinical rules are **clinically right** | The mechanism is tested; the table itself is a DRAFT until Member D checks every source and the collaborating doctor reviews it. Every answer says so |
| Whether the guard lists are clinically right | `rules.v1.json` is a **draft**: Member D must review every list and the collaborating doctor the clinical ones (status field in the file) |
| ~~The real page against the real backend~~ | **Closed.** Section 8 drives real Google Chrome with Playwright (`e2e/tests/chat.spec.js`): sign in with a CAPTCHA and a 6-digit code, ask a question, check the four console lines and the same trace ID in the backend log, the notices, scrolling, and the 390×844 phone layout |
| `contract.ts` and `schemas.py` staying the same | They are kept in sync by hand; section 6 catches some drift in what the backend sends |
| Every browser | Automated page tests run in a simulated browser (jsdom) plus real Google Chrome (section 8). Safari and Firefox tried by hand only. Safari's special keyboard behaviour for Hindi/Japanese input is covered by a simulated test only |
| Windows and Linux setup by a person | Run by hand on macOS only. GitHub's automatic check runs setup + check on Linux, Windows and macOS for every push — all three passed all 21 checks (pull request #1) |

## Part 4 — when something fails

| You see | Why | Fix |
|---|---|---|
| `command not found: python3.12` / `No suitable Python runtime found` | Python 3.12 not installed | [SETUP.md step 1](SETUP.md#1-install-the-tools-once-per-computer) |
| `[FAIL] backend Python is 3.12 (found: none…)` or `vitest: command not found` | Setup not done in this folder | `python3.12 scripts/setup.py` (Windows `py -3.12 scripts/setup.py`) |
| `Node.js … not supported` / `node: command not found` | Old or missing Node | Install Node 24 LTS (24.15+), open a new terminal |
| `No such file or directory: scripts/setup.py` | You have the old `main` without the chat app | [SETUP.md step 2](SETUP.md#2-get-the-code): switch to the chat-app branch |
| `bad interpreter` when starting the backend | The folder was moved or renamed after setup | Start it with `.venv/bin/python -m uvicorn …` as in SETUP.md, or delete `backend/.venv` and run setup again |
| Windows: `npm.ps1 cannot be loaded because running scripts is disabled` | PowerShell's script policy | Use **Command Prompt** instead of PowerShell, or type `npm.cmd` instead of `npm` |
| `Port 5173 is already in use` / `address already in use` (8000) | Another copy is already running — another terminal, or an app's preview | Stop the other one (**Ctrl+C** in its terminal), or just use it |
| Page shows *The server could not answer (HTTP 502)* | Backend (terminal 1) not running | Start terminal 1 |
| Page shows *HTTP 500*, or *Couldn't reach the DiaCausal server* | Backend crashed while answering (500: read the last lines of terminal 1), or the page's own server (terminal 2) stopped | Restart that terminal, then reload the page |
| Console shows none of the four lines | Console filter hides them, or wrong tab | Console level **Default** / **All levels**, clear the filter box |
| Tests fail right after `git pull` | Someone added a library | Run the setup script again |
| Anything else | | Report it (part 5) |

## Part 5 — reporting a problem

Tell the team (or open a GitHub issue):

1. What you did (the steps) and what you expected.
2. What happened instead — a screenshot of the page **and** the console.
3. The **trace ID** (8 characters, under the answer and on every console line), and the
   lines from the backend terminal that contain it.
4. Your system (macOS/Windows/Linux) and the output of `python3 scripts/check_all.py`
   (to save it to a file: `python3 scripts/check_all.py > check.txt`).

With the trace ID anyone can find exactly what the backend did with that message.
