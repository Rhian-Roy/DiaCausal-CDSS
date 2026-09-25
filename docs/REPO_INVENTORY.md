# Repository inventory — DiaCausal-CDSS (25 Sep 2026)

Written by Claude Code while inspecting the repo (Step 1). The only change in this step was adding
this document and `docs/CAUSAL_PLAN.md`. Every test result below was produced today in throwaway
environments outside the repo; `git status` stayed clean.

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

## 1. The short version

The repo holds **two separate projects**:

1. **The chat app** (`frontend/` + `backend/`). It is complete and well tested: sign-in with MFA,
   message guards, a patient panel, and a cited clinical-rules stage. Its six-stage pipeline stops
   short of any numbers: the `causal_engine`, `rag_retrieval` and `llm_explanation` stages return
   "skipped".
2. **Older research code** (`causal_engine/`, notebooks, root scripts). It compares only **two**
   arms, SGLT2i vs metformin, on made-up numbers with no sources. That is not our clinical question,
   but the estimator maths is clean and reusable.

Nothing yet compares the three add-on options (SGLT2i, DPP-4i, sulfonylurea). There is no
`data/rules.csv`, no `params.yaml` and no `results/` folder. Building those is Step 2.

## 2. Tech stack

| Part | What it uses | Versions (pinned where the repo pins them) |
|---|---|---|
| Frontend | React + Vite + TypeScript + Tailwind v4 + shadcn/ui; tests with Vitest + jsdom; lint with oxlint | react 19.3.0, vite 8.3.0, vitest 5.0.1, typescript 6.0.3, tailwindcss 4.3.3 |
| Backend | FastAPI + Pydantic v2 on Python 3.12, SQLAlchemy 2 + Alembic (SQLite), Argon2id, TOTP, CAPTCHA, faster-whisper for voice | fastapi 0.141.1, pydantic 2.13.5, uvicorn 0.53.0, PyYAML 6.0.3 (all exact pins in `backend/requirements.txt`) |
| End-to-end tests | Playwright driving Chrome (`e2e/`) | — |
| Research code | NumPy, pandas, scikit-learn, SciPy, Matplotlib, Streamlit; DoWhy and EconML for cross-checks; networkx for the DAG | **not pinned** (`requirements.txt` uses `>=`) |
| Deployment | One Docker image (page + API from one origin), Caddy for HTTPS (`Dockerfile`, `compose.yaml`) | python:3.12-slim, node:24, Caddy 2.10 |
| CI | GitHub Actions (`.github/workflows/check.yml`): `setup.py` + `check_all.py` on Linux, Windows and macOS; Playwright on Linux; pip-audit + npm audit | — |
| Sibling repo | `DiaCausal-RAG-Core`: a Streamlit RAG prototype (ChromaDB, BM25, sentence-transformers) | unpinned |

## 3. Folder by folder

| Folder / file | What it does | Status |
|---|---|---|
| `frontend/` | The chat page. It covers sign-in screens (designs 01–08), guard notices (09–12), the patient panel (13–16), and a list of options coloured by the guardrail stage. | Works. Estimates, intervals and ranking (designs 17–20) are not built. |
| `backend/app/` | FastAPI app. Endpoints: `POST /api/v1/chat` (signed-in clinicians only), `/api/v1/transcribe`, `/api/v1/auth/*`, `/api/health`. | Works. |
| `backend/app/pipeline/` | Six stages in order: `backend_guard` → `clinical_guardrails` → `causal_engine` → `rag_retrieval` → `llm_explanation` → `output_guard`. | The first two and the last run. `causal_engine.py` is a stub that returns "skipped". |
| `backend/app/clinical/` | `guardrails.v1.yaml` (15 draft rules, US FDA labels, not yet reviewed by a doctor), loader `rules.py`, checker `check.py`. | Works: 14 rules used, 1 refused (G13 still says TODO). |
| `backend/app/auth/`, `db/`, `voice/` | Sign-in, database and migrations, speech-to-text. | Works. |
| `backend/tests/` | 392 pytest tests covering the contract, guards, guardrails, patient panel, logging, auth, admin and voice. | **All pass** (see section 4). |
| `shared/guard_rules/` | Word lists and patterns shared by the browser and server guards, plus a reference checker. | Works: 47/47 cases match. |
| `scripts/` | `setup.py` (one-time setup), `check_all.py` (the 43-check "is everything OK" script), admin helpers. | Not run today (see section 4). |
| `e2e/` | Playwright tests in real Chrome. | Not run today. |
| `eval/` | 25 synthetic vignettes plus the SUS and doctor-feedback forms, and `run_vignettes.py`. | Not run today; `check_all.py` runs it. |
| `design/` | HTML and PNG designs: `chat.html`, `login.html` and `v1/01-20`. | Reference only. |
| `docker/`, `Dockerfile`, `compose.yaml` | The one-origin HTTPS deployment. | Built in an earlier PR; not run today. |
| `causal_engine/` | The older **2-arm** research package: data generator, DAG, 10 hand-written estimators, diagnostics, evaluation, library cross-checks, TF-IDF retrieval, guardrails, a fusion layer. | Runs. Not our 3-arm question (see section 6). |
| `tests/test_causal_engine.py` | Tests for the old package (1,300 lines). | 94 pass, **2 fail** (section 5). |
| `causal_inference_basics.py` | A console run of the ten "acts", written to `figures/basics_*.png`. | Uses the old package. |
| `causal_inference_implementation.py` | An even older DoWhy/EconML pipeline with its own generator. | Hard-coded Mac paths (section 5). |
| `diacausal_demo.py`, `smoke_streamlit.py` | The old 2-arm Streamlit demo and its headless smoke test. | The smoke test **passes**. |
| `build_notebook.py`, `verify_notebook.py`, `*.ipynb` | Notebook generator and checker; three notebooks. | The old package's teaching material. |
| `Datasets/` | `diabetes.csv` (Pima: Akimel O'odham women in Arizona, **not Indian data**, no treatment column); `synthetic_diabetes_ehr.csv` (2-arm, from the old pipeline). | Neither suits a 3-arm causal question. |
| `figures/`, `cate_analysis.png` | Plots from the old 2-arm code. Five of them (`act3_dag`, `act7_*`, `act8_*`) are made by no current script. | Old results. |
| `RAG/` | `sources.csv` (a licence table of 21 sources), `IDF_Rec_2025.pdf`, `Figure.ppt`. | See section 5 about the IDF PDF. |
| `docs/` | Team guides 01–08, SETUP, TESTING, DEPLOY, explainers, prompts, research worksheet. | Some pages are stale (section 5). |
| `docs/research/…worksheet.xlsx` | Member A's parameter worksheet: 25 rows, 5 verified, 6 "needs decision", 20 outstanding. | It mentions a `params.yaml` and `validate_params.py` that are **not in the repo**. |

## 4. What runs (checked today)

| What | How I ran it | Result |
|---|---|---|
| Backend tests | `pytest -q` in `backend/`, Python 3.12 venv built from `backend/requirements-dev.txt` | **392 passed** (369 non-voice + 23 voice; the Whisper model downloaded fine) |
| Frontend tests | `npx vitest run` on a copy of `frontend/` after `npm ci` (Node 22.22.2) | **238 passed** |
| Frontend build + lint | `tsc -b && vite build`, `oxlint` | Build OK, lint clean |
| Clinical rules table | `python -m app.clinical.check` | 14 rules usable, 1 refused (G13, TODO age cut-off) |
| Shared guard rules | `python shared/guard_rules/reference_guard.py` | 47/47 cases match |
| Old research tests | `pytest tests/ -q` with root `requirements.txt` + networkx + nbformat | **94 passed, 2 failed** in about 3 minutes |
| Old Streamlit demo | `python smoke_streamlit.py` | ALL SMOKE CHECKS PASSED |
| `scripts/check_all.py` (43 checks) | **Not run.** It needs `scripts/setup.py`, which writes `backend/.env` into the repo and starts live servers. The parts it wraps (backend tests, vitest, build, lint) were run above. | — |

## 5. What's broken or inconsistent

**Old research code (`causal_engine/` and root scripts)**

1. **2 old tests fail:** `TestRetrieval::test_the_provenance_table_reports_both_tiers` and
   `test_extraction_quality_is_reported_honestly` (`tests/test_causal_engine.py:920, 991`).
   - Both expect the "unreadable" guideline PDFs that were later deleted from `RAG/`.
   - This is not a code bug; the test data is gone. I have not changed these tests.
2. **Two arms only.** Everything assumes treatment is 0/1:
   - `TREATMENT="treatment_sglt2i"` (`causal_engine/data.py:91`);
   - `predict_proba(...)[:, 1]` (`estimators.py:384-390`).
3. **Clinical numbers hard-coded in code:**
   - `guardrails.py:141` (eGFR < 30), `:171` (30–45), `:281` (HbA1c ≥ 10);
   - `cdss.py:169-185`;
   - `data.py:290, 383`.

   CLAUDE.md forbids this. The same code also *fails open* when a value is missing: a missing eGFR
   defaults to 100 (`guardrails.py:141`).
4. **E-value interval bug** (`diagnostics.py:385-402`).
   - When the interval crosses zero, the E-value should be 1, but it comes out above 1.
   - For negative estimates it uses the bound farther from zero.
5. **Leakage** in `evaluate.predictive_vs_causal`. The causal model it is compared against was
   trained on the "held-out" rows too (`diacausal_demo.py:584`).
6. The generator's `adherence` "mediator" never affects the outcome (`data.py:362-380`), and
   `has_cvd` affects nothing. The DAG's `BMI → Treatment` edge is absent from the generator.
7. `guideline_fallback.py` quotes "ADA Standards of Care" pages from a file that `RAG/sources.csv`
   (X02) identifies as a short type-1 article. So those citations are wrong.
8. `causal_inference_implementation.py:667, 687` write to `/Users/rhor/FCRIT/...`, so the script
   fails on any other computer.
9. Root `requirements.txt` has problems:
   - it is unpinned;
   - it lacks `networkx` (needed by `dag.py`) and `nbformat` (needed by the notebook scripts);
   - CI never runs the old test suite.
10. The old demo shows "Not a clinical tool…", not the project's intended-use sentence. It also
    prints raw retrieved passages, so any dosing text inside a PDF could reach the screen
    (`diacausal_demo.py:382, 690`).

**Chat app and docs**

11. The chat app's rules table `backend/app/clinical/guardrails.v1.yaml` **differs from the team's
    reference table** (Part 6 of `docs/02_…`). The full side-by-side is in `docs/CAUSAL_PLAN.md` §4.
    For example:
    - SGLT2i is excluded below eGFR 30 in the yaml, but below 45 in Part 6.
    - Sulfonylurea at eGFR < 30 is "check first" in the yaml, but "exclude" in Part 6.
    - Part 6 R09 (SU, eGFR < 60) is missing from the yaml.
12. Two yaml rules can never fire in a live request: G01 (SGLT2i eGFR < 30) and G12 (SU eGFR < 30).
    The patient-level rule G00 stops every request with eGFR < 30 first.
13. Other rule-engine gaps:
    - an option rule with `action: abstain` would crash with `KeyError`
      (`clinical_guardrails.py:30, 83`);
    - `requires_field` is read but never enforced.
14. The `Dockerfile` copies neither `causal_engine/` nor `eval/`. So the vignette command in
    `docs/DEPLOY.md:71` fails inside the container, and the image has no scikit-learn or pandas.
15. Stale docs:
    - `docs/TESTING.md` says "ALL 35 CHECKS PASSED" and "2 of 6 stages ran" (the real counts are
      43 checks and 3 stages), and it lists Docker as not built;
    - CLAUDE.md says "only the first and last [stages] run"; the guardrails stage runs too;
    - `docs/explain/02-presenting-it.md` says "no clinical safety check yet" and mentions
      `PatientStrip.tsx`, which no longer exists;
    - `docs/SETUP.md:7-9` says the devcontainer is for the old Streamlit demo; it now runs the
      chat app.
16. README line 30 calls IDF 2025 "cleared". `RAG/sources.csv` S11 says "All rights reserved… remove
    the PDF from the public repo", yet `RAG/IDF_Rec_2025.pdf` is still committed. **The team should
    decide on this.**
17. Colours:
    - The PPT and causal guides say **grey** = insufficient evidence. Design 19 and
      `GuardNotice.tsx` use **amber**.
    - Design 20's step order differs from the backend's stage order.
    - Designs 14 and 16 show a "Compare options" button and an amber "Example data" badge; neither
      is built.
18. Slide 13 of the PPT guide names `POST /api/v1/recommend`, which doesn't exist yet. Step 2i adds
    it.
19. `e2e/node_modules` is committed to git: 525 of the repo's 810 tracked files.

**Sibling repo `DiaCausal-RAG-Core`**

20. `app/rag/fusion.py:93-110` **prints drug doses** ("100 mg once daily", "Max 8 mg/day") and
    hard-codes eGFR rules in Python. Both break our rules; don't reuse this code.
21. Its causal bridge calls `causal_engine.cdss.estimate_cate`, which doesn't exist, so it always
    falls back to a planted-effect toy model. Its evaluation numbers are therefore circular.
22. Other problems:
    - `requirements.txt` is unpinned;
    - the README mentions a LICENSE file that isn't there;
    - the seeded "guideline" files are summaries written in code, not verbatim sources.

**Secrets:** none found in either repo. I searched for API keys, tokens and `.env` files, including
the git history of RAG-Core. `.env` and `backend/.env` are gitignored.

## 6. What we can reuse for the 3-arm engine

| Reuse | From | How |
|---|---|---|
| The idea of cross-fitting a propensity model | `causal_engine/estimators.py:357-405` (`estimate_propensity`), `default_treatment_model()` | Same StratifiedKFold loop, but keep all 3 columns of `predict_proba` |
| IPW and AIPW formulas, influence-function standard errors | `estimators.py:408-465` (`ipw_ate`), `:559-640` (`aipw_ate`) | Generalise from T/(1−T) to one indicator per arm |
| DR-learner (AIPW pseudo-outcomes → second-stage regression) | `estimators.py:751-770` | Add a proper patient-level 95% interval (the old one has none) |
| `EffectEstimate` (value, SE, CI) | `estimators.py:63-96` | Same idea, re-implemented in the new package |
| SMD formula and the 0.1 balance rule | `diagnostics.py:210-260` | Rewrite for 3 arms (pairwise SMD) |
| Figure styles (overlap, love plot, CATE calibration by decile, recovery scatter) | `diagnostics.plot_overlap`, `plot_love`, `evaluate.plot_cate_calibration` | Same look, new data |
| Test patterns: seeded fixtures, "recovers the truth within tolerance", reproducibility | `tests/test_causal_engine.py` | Same style in `tests/engine/` |
| Plausibility ranges and Asian-Indian BMI categories | `backend/app/patient_ranges.py` | Mirrored in `data/params.yaml`, with a test that they match |
| Intended-use sentence | `backend/app/settings.py:23-26` | The exact same text |
| Colour tokens (red, amber, pine, grey) | `frontend/src/index.css:20-61` | Used in the Streamlit demo |
| Pinned versions of fastapi, uvicorn, PyYAML | `backend/requirements.txt` | Same pins, for an easy October merge |

**Do not reuse:**
- `causal_engine/guardrails.py` and `cdss.py` (numbers in code, 2-arm, fail open);
- `guideline_fallback.py` (wrong sources);
- the old generator's numbers (no sources, not Indian);
- the Pima dataset (not Indian, no treatment);
- RAG-Core's `fusion.py` (doses).
