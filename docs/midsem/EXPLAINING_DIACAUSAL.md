# Explaining DiaCausal — from start to end

**Group 28 · B.Tech Computer Engineering, Sem VII · FCRIT Vashi · Guide: Mr. Rahul Jadhav**
Pratham Pawar · Graceton Santhmayor · Rhian Roy Kuttikadan · Advik Saxena

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

This handbook is for **the guide meeting (Tuesday 29 September)** and **Progress Presentation-II
(Wednesday 30 September)**. It explains everything we have built, in the order we built it. For
each part it gives what it does, how it works, why we chose it, where the code is, how we know it
works, and the question you are most likely to be asked.

**Rules while presenting**
1. Say **"synthetic data"** every time you show a result. No real patient data has been used.
2. Never invent a number. Every number here comes from a file in `results/` or `docs/TESTING.md`
   (see the [numbers card](#9-numbers-card)).
3. Say what works **today**, what comes **next**, and **where the code is**. "Not built yet" is a
   good answer: it shows you know exactly where the edges are.
4. Safety first: the doctor decides, safety rules run before any estimate, doses are never shown,
   and the system says "insufficient evidence" instead of guessing.

---

## 1. Pitches

**One line.**
> DiaCausal helps a doctor choose the second diabetes drug after metformin by estimating, for this
> one patient, what each option would do. Safety rules run first, every number has a 95% range,
> and every explanation cites an approved source.

**30 seconds.**
> After metformin, Indian doctors usually add one of three drug classes: an SGLT2 inhibitor, a
> DPP-4 inhibitor or a sulfonylurea. Old records mislead, because different kinds of patients get
> different drugs. DiaCausal first removes unsafe options using cited drug-label rules. It then
> uses causal inference to estimate each remaining drug's six-month HbA1c change for this patient,
> with a 95% range, plus weight change and low-sugar risk. It explains the answer with quoted,
> cited passages from WHO and FDA documents. When the evidence is too thin it says so instead of
> guessing. It runs on a phone, behind approved sign-in with an authenticator app, and the doctor
> always decides.

**2 minutes (for the guide).**
1. **Problem.** Choosing the add-on to metformin is a *what-if* question: what would happen to
   this patient under each drug? Ordinary machine learning answers "what happened to people like
   this", which is confounded by who got which drug.
2. **Method.** On a synthetic, India-calibrated cohort where we know the true answers, we use:
   - propensity scores, to check that similar patients got each drug (overlap);
   - doubly robust estimators (AIPW for averages, the DR-learner per patient), each with a 95% interval.
   Every generator number has a source and a status.
3. **Safety.** Ten cited rules (nine from FDA drug labels, one team rule) run before any estimate. An excluded drug is never
   estimated. Doses are never shown. Propensity below 0.05, or a 95% range wider than 1.5
   points, means "insufficient evidence".
4. **Evidence (RAG).** The system searches only licence-cleared documents: WHO 2018 and seven
   FDA safety communications. It quotes the sentences that answer the question, with citations,
   and refuses questions the sources don't cover and any dose question.
5. **Proof.**
   - The benchmark runs 20 cohorts × 5,000 patients: the naive comparison is off by −0.159
     HbA1c points, AIPW by +0.002.
   - All 9 refutation tests pass.
   - The RAG test set: recall@5 0.933, citation precision 1.0, zero dose leaks.
   - Tests: 202 for the engine, RAG and website, plus 647 for the chat app. They run on Linux,
     macOS and Windows.
6. **Where it runs.**
   - A phone website (diacausal.netlify.app) with admin-approved accounts.
   - A Streamlit demo and an API.
   - A secure chat application with CAPTCHA and MFA sign-in, guards, a patient panel, clinical
     guardrails, voice input and Docker deployment. Since 29 September its pipeline runs the
     causal engine and the evidence search too (all six stages).
7. **Next (October).**
   - A better search model (medical embeddings + reranker), target 3 October.
   - A real-data adapter and evaluation tools, target 6 October (100% implementation).
   - Doctor review of the test questions and the clinician vignettes.
   - Results frozen on 16 October; then the paper.

**An everyday analogy (for non-technical listeners).**
> Think of a careful senior doctor with a pharmacist beside them. The pharmacist first crosses out
> any drug the patient must not take, reading the reason from the label. The senior doctor then
> compares the remaining drugs only against patients who really were similar. They give a best
> guess *with its uncertainty*, or say "we haven't seen enough patients like this one". A
> librarian hands over the exact pages that support each point. The junior doctor, our user,
> makes the decision.

---

## 2. The story from start to end

| When | What we built | Where / proof |
|---|---|---|
| July – August | Topic, proposal, literature. First research code: a 2-drug causal notebook, a small guideline retrieval (`causal_engine/`, `notebooks/`, `RAG/`). An early RAG prototype on the open-source Kotaemon framework (repo DiaCausal-RAG-Core). | Initial commit 27 Aug |
| Early September | **Data decision.** The Pima dataset is not Indian and not about drug choice, so we rejected it. We chose a **synthetic, India-calibrated cohort** where the true effect of every drug is known. Scope frozen: adults with type 2 diabetes on metformin; three add-on classes; outcome = 6-month HbA1c change. | `docs/01_Master_Plan.md` |
| 18 – 19 Sept | **Chat app: walking skeleton.** React page → FastAPI server → six-stage pipeline → reply, with one trace ID on every log line. One command checks everything. | PR #1, #2; `docs/explain/01` |
| 20 Sept | **Guards.** Foul language, patient identifiers, out of scope, emergency, language. The same rules file is used in the browser and on the server. | `shared/guard_rules/`; `docs/explain/03` |
| 20 Sept | **Sign-in.** CAPTCHA, Argon2id passwords, authenticator-app MFA, sessions, CSRF, lockout, audit log, admin command line. | `backend/app/auth/`; `docs/explain/04` |
| 20 Sept | **Voice input.** Speech-to-text runs on our own computer (faster-whisper) and puts the text *in the box*, never sends it. | `docs/explain/12` |
| 20 – 21 Sept | **Patient panel** (structured facts with units and plausibility ranges) and **clinical guardrails** (15 cited rules, applied before any ranking). | PR #5, #6; `docs/explain/05`, `06` |
| 20 – 21 Sept | **Deployment.** One Docker image, HTTPS through Caddy, security headers, reachable from a phone. Evaluation pack: 25 synthetic vignettes plus the SUS usability form. | PR #7; `docs/DEPLOY.md`, `eval/` |
| 25 Sept | **Causal engine v0.3**, built in ten steps: a) cohort → b) safety rules → c) propensity → d) naive/IPW/matching/AIPW → e) DR-learner → f) metrics → g) benchmark → h) Causal Output + Streamlit → i) API → j) invariant tests. | PR #11; `docs/explain/07` |
| 25 Sept | **Refutation tests and E-values**; the first RAG skeleton with its licence table. | PR #12 |
| 25 – 26 Sept | **Phone website** running the same engine in the browser (parity-tested against Python). **Accounts**: Supabase, authenticator MFA, admin approval. **Evidence tab** (first FDA source). | PR #13, #14; https://diacausal.netlify.app |
| 26 Sept | **Mid-sem kit.** Report (LaTeX), slides, Gantt chart, backup video, viva sheet. | PR #15; `docs/midsem/` |
| 26 Sept | **Engine extras**: weight change and hypoglycaemia risk (each with a 95% range), "too uncertain" abstention, printable consultation summary. Full benchmark rerun; the primary numbers are unchanged. | PR #16 |
| 26 Sept | **Full RAG.** WHO 2018 plus seven FDA safety communications; sentence-aware chunks; dose text kept out of the index; coverage abstention; explanations in three modes (quoted / Gemini free tier / local Ollama) behind one citation checker; a 60-question test set and evaluation; the Supabase Edge Function for Gemini; evidence on every option card. | PR #16; website redeployed |

**What "25% implementation" means for us.** The mentor asked for about 25%. Every core part now
works on its own: the causal engine, the evidence search with explanations, the website with
accounts, and the secure chat app. The largest remaining steps are:
- joining the engine and RAG into the chat app's pipeline;
- the doctor's review and the usability study;
- a better search model;
- the paper.

---

## 3. Every component, explained

Each part follows the same pattern: **What**, **How**, **Why**, **Where**, **Proof**, **Likely question**.

### Part A — The chat application (the secure front door)

#### A1. Walking skeleton and trace IDs
- **What:** A doctor types a question. The page checks it, labels it with an 8-character trace ID
  and sends it to our Python server. The server runs six stages in a fixed order:
  1. `backend_guard`
  2. `clinical_guardrails`
  3. `causal_engine`
  4. `rag_retrieval`
  5. `llm_explanation`
  6. `output_guard`

  The reply comes back with the same ID.
- **How:**
  - React + Vite + TypeScript on the page; FastAPI + Pydantic v2 on the server.
  - The API accepts exactly one JSON shape (`schema_version`, `client_trace_id`, `parts`). It
    refuses unknown fields, and anything wrong gets a 422 with a plain-English message.
  - Every log line carries the trace ID and **never the message text**.
- **Why:** Joining the pieces is where projects break, so we joined them first, while simple.
- **Where:** `backend/app/main.py`, `backend/app/schemas.py`, `backend/app/pipeline/`, `frontend/src/lib/chatFlow.ts`.
- **Proof:** `python3 scripts/check_all.py` prints 43 pass/fail lines, including 401 backend
  tests, 246 frontend tests and live server checks. GitHub runs it on Linux, Windows and macOS.
- **Q:** *"Do all six stages really run in the chat app?"*
  **A:** Yes, since 29 September (implementation Section 3). We built and validated the engine and
  RAG as standalone modules first, then plugged them into the stage slots that were already there.
  `causal_engine` runs only on the options the guardrails allow, and says which patient detail is
  missing instead of guessing; `rag_retrieval` and `llm_explanation` quote cited sentences; the
  output guard withholds anything that looks like a dose (`backend/tests/test_engine_stages.py`).

#### A2. Guards
- **What:** The guards block foul language, patient identifiers (notice 09), out-of-scope
  questions (10), emergencies (11) and unsupported languages (12). They never show or log the
  word they matched.
- **How:**
  - One rules file, `shared/guard_rules/rules.v1.json`, is loaded by both the browser and the
    server. The server has the final say, because a request can skip our page.
  - Both sides must give the same answer on 47 example cases plus 55 extra tricky cases.
  - The profanity list comes from LDNOOBW (CC BY 4.0), with clinical words removed and a
    medical allowlist added.
- **Where:** `frontend/src/lib/guards.ts`, `backend/app/pipeline/blocklist.py`; `docs/explain/03-guards.md`.
- **Q:** *"Why check twice?"*
  **A:** The browser check is for speed and friendliness. The server check is for security,
  because anyone can call the API directly.

#### A3. Sign-in with CAPTCHA and MFA (the "master login")
- **What:** Accounts are created by an admin. Sign-in needs a user ID, a password, a CAPTCHA,
  and then a 6-digit authenticator code.
- **How:**
  - Passwords are stored only as Argon2id hashes.
  - The CAPTCHA is an image plus audio, made offline by the Python `captcha` library.
  - MFA uses TOTP (Google/Microsoft Authenticator); its secret is encrypted in the database.
  - Sessions use `__Host-` cookies (HttpOnly, Secure, SameSite=Strict) with a CSRF token.
  - Idle timeout 15 minutes; hard limit 8 hours.
  - Five failures lock the account for 15 minutes.
  - An audit log records sign-ins and every chat request (IDs and outcomes only).
  - Built to OWASP ASVS level 1 and NIST SP 800-63B.
- **Where:** `backend/app/auth/`; `docs/explain/04-login-and-mfa.md`.
- **Q:** *"What is the master login?"*
  **A:** An admin *role*, not a shared password. Admin actions need the admin's own password
  plus a current code.

#### A4. Patient panel
- **What:** Age, diabetes duration, HbA1c, eGFR, BMI, yes/no histories and budget are entered in
  separate boxes with their units. They are sent as a structured `patient` part next to the question.
- **Why:** A parser guessing values from free text ("sugar 8.4", "no DKA hx") would change the
  recommendation. Structured facts are deliberate and checkable. An empty box means *unknown*.
- **How:**
  - Plausibility ranges live in `app/patient_ranges.py` and `features/patient/ranges.ts`; a test
    compares the two.
  - BMI uses the Asian-Indian cut-offs: overweight from 23, obese from 25.
  - Patient values are **never logged**.
- **Where:** `docs/explain/05-patient-panel.md`.

#### A5. Clinical guardrails (chat app)
- **What:** 15 cited rules (14 in use) decide **before any ranking** which options may be used.
  A "do not use" option is removed, so nothing later can rank it first.
- **How:**
  - Thresholds live only in `backend/app/clinical/guardrails.v1.yaml`, each with a source.
  - A rule marked TODO, or without a source, never fires.
- **Q:** *"The engine has its own rules table — why two?"*
  **A:** They were written at different times from different sources (`docs/CAUSAL_PLAN.md` §4).
  When they are joined, the stricter action wins until the doctor decides.

#### A6. Voice input
- **What:** Press the mic, speak, and the words appear **in the message box**. They are never sent
  automatically.
- **How:**
  - faster-whisper (the `base` model, int8) runs on our own server.
  - A prompt that names the drugs and units improves recognition.
  - A careful tidy-up step ("satagliptin" → sitagliptin, but never one real drug turned into another).
  - The audio is deleted after decoding, and the transcript is never logged.
- **Why:** A spoken question can contain patient details, so no cloud service is used.

#### A7. Deployment and evaluation pack
- **What:** `docker compose up --build -d` serves the page and the API from **one origin**, with
  HTTPS (Caddy) and strict security headers. `/docs` is off in production.
- **Why:** With one origin there is no CORS to get wrong, and the secure cookie works as designed.
  HTTPS is required for the microphone and for secure cookies.
- **Evaluation pack:** `eval/` holds 25 synthetic patient vignettes and the SUS usability and
  feedback forms, for the clinician study in October.

### Part B — The causal engine (the heart of the project)

#### B1. The question, and why it is causal
- **What:** For one adult on metformin, what would the 6-month HbA1c change be under an SGLT2
  inhibitor, a DPP-4 inhibitor or a sulfonylurea?
- **Why causal:** Old records mix the drug's effect with *who got it* (confounding by indication).
  **Worked example (made-up numbers):**
  - Pooled, SGLT2i vs SU looks like **−0.425**.
  - Comparing like with like, it is **−0.15**, about 3× smaller.
- **Say:** "Ordinary machine learning predicts what will happen. We need what *would* happen under
  each drug for the same patient."

#### B2. Synthetic, India-calibrated cohort with a known truth
- **What:** We simulate patients already on metformin:
  - age, sex, diabetes duration, HbA1c, eGFR, BMI;
  - heart disease, heart failure, past hypoglycaemia, past DKA, past pancreatitis, low income.

  Each patient gets a drug the way doctors tend to choose (confounding built in on purpose). We
  store the outcome under *all three* drugs, so the true answer is known.
- **Rules:**
  - Every number in `data/params.yaml` has a `source` and a `status`: CITED,
    ASSUMED-DIRECTIONAL or TEAM-SET. The loader refuses anything else.
  - A causal diagram (DAG) fixes which variables we adjust for, and never a mediator such as
    weight change.
- **Why synthetic:** Pima is not Indian data and has no drug choice. Real Indian records need
  ethics approval. A known truth is the only way to *prove* a method is right.
- **Where:** `diacausal_engine/cohort.py`, `data/params.yaml` (including its `dag:` section, read by `diacausal_engine/dag.py`).
- **Q:** *"Doesn't synthetic data prove nothing?"*
  **A:** It proves the *method* recovers a planted truth under realistic confounding, which you
  cannot check on real data. It does not prove real drug effects, and we never claim it does.
  `cohort.load_dataset()` already reads a real de-identified CSV once approved.

#### B3. Safety rules first
- **What:** Ten rules (R01–R10), each with its source. Nine come from the US FDA labels of
  dapagliflozin (FARXIGA), sitagliptin (JANUVIA) and glimepiride; R10 is a team rule pending
  clinician review. Three are EXCLUDE (R01, R02, R10); seven are CAUTION.
  - R01: SGLT2i not for glycaemic control at eGFR < 45.
  - R05: DPP-4i with past pancreatitis.
  - R07–R10: sulfonylurea and hypoglycaemia risk or kidney function.
- **How:** Rules run **before** any estimate. An excluded option is never estimated. Thresholds
  live only in `data/rules.csv`, and a test scans the code for hard-coded thresholds.
- **Doses:** never shown. An output check refuses any reply containing dose-like text.

#### B4. Propensity score and overlap
- **What:** The chance that a patient like this one received each drug. It comes from a
  multinomial logistic regression, cross-fitted over 5 folds and clipped for stability.
- **Why:** If almost nobody like this patient received a drug (propensity below **0.05**), there
  is no fair comparison, so the answer is **"insufficient evidence"**, never a number.
- **Balance proof:** before weighting, the groups differ by up to |SMD| 0.704; after IPW
  weighting, about 0.08 (0.0775 as stored). Under 0.1 counts as balanced.

#### B5. Average effects: naive, IPW, matching, AIPW
- **Naive:** compare group means. Biased on purpose, to show the problem.
- **IPW:** weight each patient by 1/propensity, so each drug group looks like the whole population.
- **Matching:** pair patients with similar propensity. Intervals come from a bootstrap.
- **AIPW (doubly robust):**
  - Estimate = outcome-model guess + an IPW correction of that guess's error.
  - It is correct if **either** the outcome model **or** the propensity model is right.
  - Its 95% interval comes from the influence function.

#### B6. Per-patient effects: DR-learner
- **What:** The expected change for *this* patient under each drug, plus the differences between
  drugs, each with a 95% interval.
- **How:** Regress the AIPW scores on the patient's features. The second stage is linear, and
  the intervals come from HC3 robust standard errors.
- **Q:** *"Why not a bigger model?"*
  **A:** Every number must carry a valid interval, and must be exactly reproducible in the phone
  browser. A linear second stage on doubly robust scores gives both.

#### B7. Secondary outcomes and "too uncertain" (added 26 Sept)
- **What:** Each estimated option also shows:
  - the **6-month weight change (kg)**, with a 95% range;
  - the **risk of any hypoglycaemia (%)**, with a 95% range.

  They come from the same cohort and method, generated from a separate random stream, so the
  HbA1c results are byte-for-byte unchanged.
- **Too uncertain:** if a 95% range is wider than `engine.max_interval_width` = 1.5 points
  (TEAM-SET, for the doctor to confirm), the option shows "insufficient evidence (too uncertain)".
- **Proof:** see the [numbers card](#9-numbers-card).
  - Weight, SGLT2i vs SU: truth −3.33 kg; estimate −3.33.
  - Hypoglycaemia, SU vs DPP-4i: truth +12.9 points; estimate +12.6 (+12.55 in the file).

#### B8. Benchmark, refutation and sensitivity
- **Benchmark:** 20 fresh cohorts × 5,000 patients, plus 2,000 test patients. We measure bias,
  RMSE, 95% coverage, PEHE (per-patient error), policy regret and abstention.
- **Refutation (all 9 pass):**
  - a placebo drug should show about zero effect;
  - adding a random common cause should change nothing;
  - an 80% subset should give about the same answer.
- **E-values:** how strong a hidden confounder would need to be to explain the effect away:
  1.72 (SGLT2i vs DPP-4i), 2.15 (SU vs DPP-4i), 1.57 (SGLT2i vs SU).
- **Where:** `python -m diacausal_engine.benchmark`, `results/`, five figures in `results/figures/`.

#### B9. Causal Output, Streamlit demo and API
- **Causal Output:** the structured JSON handed to the evidence-fusion layer (`schemas.CausalOutput`):
  - APPLICABLE / NOT_APPLICABLE;
  - intervention and outcome;
  - per-option status (estimate / excluded / insufficient evidence) with the effect, its
    interval, the propensity, the fired rules with sources, and the secondary outcomes;
  - comparisons, assumptions and versions;
  - the intended-use sentence.
- **Streamlit demo:** `streamlit run demo/streamlit_app.py`.
- **API:** `POST /api/v1/recommend` (FastAPI) returns the same object. Every request writes an
  audit line with IDs, versions and rule IDs only, never patient values.

### Part C — The phone website and accounts

#### C1. The website (https://diacausal.netlify.app)
- **What:** A phone-first installable web app (PWA) with these tabs:
  - **Try it:** the patient form, 3 presets, colour-coded option cards, a 95%-range chart, fair
    comparisons, a print summary;
  - **Evidence:** RAG;
  - **Results:** the benchmark;
  - **Learn;**
  - **About.**
- **How:**
  - The fitted model is exported to `web/model.json`, and `web/engine.js` repeats `recommend.py`
    step by step *in the browser*, so patient details never leave the phone.
  - Tests compare it with Python on 155 patients, including forced "too uncertain" cases.
- **Colours:** red = excluded by a cited rule; amber = caution; grey = insufficient evidence;
  pine = estimate with its 95% range. Nothing is ever green for "recommended".
- **Security:** a strict Content-Security-Policy (no inline scripts); no API keys in the repository.

#### C2. Accounts (Supabase)
- **What:** Sign up → set up an authenticator app → wait for an admin to approve → tick the
  intended-use box. Only approved accounts can open Try it and Evidence.
- **How:**
  - Row-level security: each person sees only their own profile.
  - Admin functions require an authenticator-verified (aal2) session.
  - Rhian is the admin and approves teammates from "Approve accounts (admin)".
- **Honest limit:** sign-in controls who can *use* the app. The model file itself is public,
  which is fine: it contains no patient data.

#### C3. Printable consultation summary (added 26 Sept)
- "Print or save as PDF" produces one clean page:
  - the patient as entered and the date;
  - the three options with ranges, weight and low-sugar risk;
  - the rule sources;
  - the versions and the intended-use sentence.
- There are no doses. Nothing is uploaded.

### Part D — RAG: evidence with citations (added 25–26 Sept)

#### D1. Licence gate: what we are allowed to use
- **What:** `RAG/sources.csv` lists 23 candidate sources plus 3 excluded ones, each with its
  licence, evidence and bucket. **Only rows in the `cleared_ingest` bucket that a team member
  has confirmed are read.** Everything else is refused in code and by tests.
- **In the index today (8 documents, 78 passages):**
  - **S01 WHO 2018** second- and third-line medicines guideline (CC BY-NC-SA 3.0 IGO);
  - seven **FDA Drug Safety Communications** (US government works):
    - metformin and kidney function;
    - saxagliptin/alogliptin and heart failure;
    - DPP-4 inhibitors and joint pain;
    - SGLT2 inhibitors: ketoacidosis and urinary infections;
    - acute kidney injury;
    - Fournier's gangrene;
    - the canagliflozin amputation warning.
- **Never ingested:** IDF 2025, ADA, NICE, KDIGO, RSSDI 2022 and textbooks (not licence-cleared).
- **Q:** *"Why not just use ADA or IDF guidelines?"*
  **A:** Their licences don't allow copying them into a tool. We cite them, but we don't ingest them.

#### D2. Ingestion and chunking
- **How:**
  - PDFs are converted with page markers and headings (`diacausal_rag/pdf_text.py`). FDA pages
    come from the official page's archived copy (`scripts/fetch_fda_dsc.py`).
  - Text is cut into passages of about 400 words that **never cross a section** and **end at a
    sentence**.
  - Every passage carries its source, version, section and page.

#### D3. Search: hybrid + fusion + abstention
- **How:**
  - **BM25** (exact words such as "eGFR") and **TF-IDF vector** search (similar wording) each
    rank the passages.
  - **Reciprocal rank fusion** merges the two rankings; the best 5 are kept.
- **Abstain** ("insufficient evidence") when:
  - the best keyword score is weak; or
  - the passages contain **less than 60%** of the question's words (`min_query_coverage`,
    TEAM-SET).
- **Doses:** dose-like text is **removed from the index itself**, and any passage containing a
  dose is withheld.

#### D4. Explanations (step 5 of the RAG pipeline)
- **Three modes behind one rule, "cite only the retrieved passages, otherwise abstain":**

  | Mode | Where | Cost | What it does |
  |---|---|---|---|
  | **Template** (default) | everywhere, offline | free | Quotes the sentences that best answer the question, each with its passage number. It cannot invent anything. |
  | **Gemini** free tier | website, approved users only | free | Rewords the passages in plain English. It receives only the question and the passage IDs; our server rebuilds the passages. Never patient details. |
  | **Ollama** local model | laptop / hospital computer | free, offline | The same, with nothing leaving the machine. |

- **Citation checker:** runs on every model answer. Each sentence must:
  - end with a citation to a passage that was shown;
  - share most of its words with that passage;
  - contain no dose.

  If any sentence fails, the quoted answer is shown instead, with a note saying why.
- **Dose questions** ("What dose of glimepiride…?") get: "DiaCausal never gives doses."
- **Where:**
  - `diacausal_rag/explain.py` and its browser mirror `web/explain.js`;
  - `supabase/functions/explain/` (the key is a Supabase secret; only approved, MFA-verified
    users can call it).

#### D5. Evidence fusion on the Try-it cards
- Each option card has **"Evidence for this option"**: the licence-cleared passages about that
  drug class and its fired rules. For example, DPP-4 inhibitor → the FDA joint-pain communication.

#### D6. Evaluation on a gold question set
- **Test set:** `eval/rag_gold.csv`, 60 questions:
  - 45 answerable, each with the source and section that answers it;
  - 10 out of scope;
  - 5 dose requests;
  - 20 of them flagged for the doctor to review.
- **Results** (`results/rag_eval_summary.csv`, template mode):

  | Measure | Value | Team target |
  |---|---|---|
  | Recall@5 (right source and section in the top 5) | **0.933** | ≥ 0.80 met |
  | Answerable questions answered | **0.978** | — |
  | Citation precision | **1.000** | ≥ 0.95 met |
  | Dose leaks | **0** | 0 met |
  | Out-of-scope questions refused | **0.800** | ≥ 0.95 **not met** |

- **Honest notes:**
  - The thresholds were tuned on this same set, so these numbers are optimistic.
  - The two out-of-scope misses are a gestational-diabetes diet question and a statin question.
    They are the reason for the October work: a medical embedding model and a reranker.

### Part E — Quality and safety across everything

| Suite | Count | How to run |
|---|---|---|
| Causal engine | 150 tests | `.venv/bin/python -m pytest tests/engine -q` |
| RAG | 33 tests | `.venv/bin/python -m pytest tests/rag -q` |
| Website (incl. browser parity) | 19 tests | `.venv/bin/python -m pytest tests/web -q` |
| Chat app backend / frontend | 401 / 246 tests | `python3 scripts/check_all.py` → "ALL 43 CHECKS PASSED" |

Some tests enforce project rules rather than features:
- the intended-use sentence on every reply;
- no doses anywhere;
- every number has an interval;
- no secrets in the repository;
- exact version pins;
- no clinical threshold typed into code.

**No test was ever weakened to make it pass.**

---

## 4. The guide meeting (Tuesday 29 Sept), about 15–20 minutes

**Goal:** show that far more than 25% works, and leave with decisions only the guide can make.

| Min | Who | Do | Say |
|---|---|---|---|
| 0–2 | Pratham | The one-line and 30-second pitches | "We've built the engine, the evidence search and the website; this is what we'll present." |
| 2–6 | Rhian | Laptop: `.venv/bin/python -m pytest tests/engine tests/rag tests/web -q` (start it first, it takes about 4 minutes), then open `results/results_table.tex` and `results/figures/ate_vs_truth.png` | Naive vs AIPW against the known truth; the 9/9 refutation tests; E-values |
| 6–10 | Graceton | Phone or laptop: the live website → presets 1–3 → weight and low-sugar lines → "Evidence for this option" → print summary | The colour code; the rule sources; "insufficient evidence" |
| 10–13 | Advik | Evidence tab: "SGLT2i and ketoacidosis" → quoted explanation; "Not in the sources" → abstains; a dose question → refused | Licence gate; citation checker; 0 dose leaks |
| 13–15 | Rhian | `docs/midsem/`: the slides, report and Gantt chart | What changed since the report draft |
| 15–20 | All | **Ask the guide** (below) | — |

**Decisions to ask the guide for**
1. **A doctor.** Needed for three things:
   - review of the 20 flagged test questions (`eval/rag_gold.csv`, column `doctor_review`);
   - the 25-vignette clinician review with the SUS form (`eval/`);
   - confirming the rule cut-offs.
2. **Thresholds.** Is 1.5 HbA1c points a sensible "too uncertain" limit? Is 60% question
   coverage a sensible "refuse" limit? Both are TEAM-SET, one line each (`data/params.yaml`,
   `diacausal_rag/config.yaml`).
3. **Sources.** Can the department help obtain written permission for the ICMR / RSSDI 2022
   guidelines? Today they are cite-only.
4. **Prices.** Is using the Jan Aushadhi list acceptable? Until it's confirmed, the app shows
   "price unavailable".
5. **Final deliverable.** Is the demo the website, the chat app with the engine plugged in, or
   both? This decides where October effort goes.
6. **The paper.** Target venue and timeline (results frozen on 16 October).

---

## 5. Panel script (Wednesday 30 Sept, 12–15 minutes)

Keyed to the final deck `Intelligent_Diabetes_CDSS_MidSem_updated.pptx` (35 slides + 5 backup). The owners
match the speaker notes; the full words for every slide are in `TEAM_BRIEFING.md`. Speak to the panel, not the
screen; about 20–25 seconds per design slide, longer on 23 (the 25%) and the demo.

| # | Slide | Who | Say (short version) |
|---|---|---|---|
| 1–2 | Title, team | Pratham | "Group 28; an Intelligent Diabetes Clinical Decision Support System; guide Mr. Rahul Jadhav." |
| 3 | Outline | Pratham | Read the headings; stress scope, interaction-sheet timeline and working of the system. |
| 4 | Problem | Rhian | The worked example: naive −0.425 vs fair −0.15. "Different patients get different drugs, so a naive comparison mixes the drug with who got it." |
| 5 | How it works | Rhian | Seven steps, all running in the chat app since 29 Sep: patient → safety rules → overlap → estimates with 95% ranges → cost → cited evidence → the doctor decides. |
| 6–7 | Block diagram, flowchart | Rhian | The same order as boxes and as a decision flow; "insufficient evidence" is a real branch. |
| 8 | Safety rules | Advik | Ten cited rules (R01–R10) run before any number; no doses; the intended-use sentence. |
| 9 | Scope | Advik | In scope / out of scope / future scope (the guide asked for this in week 4). |
| 10–11 | Hardware & software, requirements | Advik | A laptop or phone; Python 3.12, FastAPI, React, Supabase; functional and non-functional requirements, all built. |
| 12–13 | Gantt, timeline | Advik | Only the sheet's rows. 25% signed 23 Sep; 40% met 28 Sep; 60% met 29 Sep; 80% target 3 Oct; all four sections by 6 Oct. |
| 14–16 | Architecture, data flow, use case / sequence | Graceton | Layers and flows; patient values are never logged; dashed arrows on 16 are UML return messages. |
| 17 | Working of the system | Graceton | Demo patient 2 step by step: SGLT2i excluded (R01, eGFR 40), DPP-4i −0.68, SU −0.82, ranges overlap. |
| 18 | Data and API | Graceton | `rules.csv` columns; `POST /api/v1/recommend`; the Causal Output fields. |
| 19–21 | Datasets | Graceton | Synthetic cohort (why and how), NMB-2017 real Indian survey as a realism check. |
| 22 | What's built | Rhian | The status table; 202 engine/RAG/website tests + 647 chat app tests. |
| 23 | **Exactly what the 25% covers** | Rhian | Six steps; "at 25%, one patient goes in, unsafe drugs come out, each remaining drug gets a 6-month HbA1c change with a 95% range or 'insufficient evidence'." |
| 24 | How the code works | Rhian | AIPW = the outcome model's guess + a weighted correction; DR-learner + HC3 for one patient's range. |
| 25–26 | Website, chat app screens | Advik | The website's four tabs; the chat app's sign-in, guards, estimates and cited evidence. |
| 27 | Accuracy | Rhian | Naive off by −0.159 and never covers the truth; IPW/matching/AIPW ≈ 0.002; AIPW coverage 90–95%. |
| 28 | Plots | Pratham | Overlap (0.05 line), balance (all under 0.1), patient-level recovery. |
| 29 | RAG results | Rhian | recall@5 0.933, citation precision 1.0, 0 dose leaks; abstention 0.80 vs target 0.90 (said honestly). |
| 30 | Demo | Graceton (Rhian drives) | See the [demo runbook](#6-demo-runbook). |
| 31 | Completed vs planned | Advik | Completed list; plan keyed to the sheet's weeks 8–10, guide evaluation, Nov, Dec, Jan–Feb. |
| 32 | Progress ≈ 75% | Pratham | The weighted table; 0.2×95 + 0.25×90 + 0.2×75 + 0.15×85 + 0.1×20 + 0.1×40 ≈ 75. |
| 33 | Conclusion | Pratham | Engine + cited evidence in one chat app; safety first; honest uncertainty; the doctor decides. |
| 34 | References | Advik | IEEE style; WHO 2018, FDA labels and communications, AIPW / DR-learner papers, NMB-2017. |
| 35 | Thank you | All | "Thank you. We're happy to take questions." |
| 36–40 | Backup | whoever is asked | Why synthetic is valid · real Indian datasets · path to a hospital · phone screens · literature. |

**Hand-overs** (one sentence each, so the talk flows):
- Pratham → Rhian: "Rhian will explain why this is a causal problem."
- Rhian → Advik: "Advik will show the safety rules that run before any number."
- Advik → Graceton: "Graceton will walk through the design and our data."
- Graceton → Rhian: "Rhian will show what is built, and exactly what our 25% covers."
- Rhian → Advik: "Advik will show the screens."
- Advik → Rhian: "Rhian will show the accuracy results."
- Rhian → Pratham: "Pratham will show the plots."
- Pratham → Rhian: "Rhian will show how well the evidence search works."
- Rhian → Graceton: "Graceton will demo it live."
- Graceton → Advik: "Advik will compare completed and planned work."
- Advik → Pratham: "Pratham will show our progress and conclude."

---

## 6. Demo runbook

**Before the panel (15 minutes ahead)**
1. The laptop is charged, on the college Wi-Fi, with the browser zoomed to 125–150%.
2. Sign in at https://diacausal.netlify.app: password, then the authenticator code. The site
   signs out after **15 minutes idle**, so sign in close to your slot. Keep the authenticator
   phone with the person driving.
3. **Backup A (no internet, no sign-in):** a local copy.
   ```bash
   cd DiaCausal-CDSS/web && python3 -m http.server 8080
   ```
   Then open http://localhost:8080. It shows "Local copy: sign-in is switched off".
4. **Backup B:** `docs/midsem/DiaCausal_demo.mp4` (112 s, captioned), opened and paused on the first frame.
5. Only if the Gemini key has been set **and tested that morning**, the Gemini button may be
   shown. Otherwise don't press it; just say what it does.

**Live (about 3 minutes)**

| Step | Click | Say |
|---|---|---|
| 1 | Try it → **1 · Typical patient** | "Three estimates, each with a 95% range. SGLT2 inhibitor −0.93 (−0.98 to −0.87). Below each: weight change and the risk of any low sugar, e.g. sulfonylurea 9.9% vs DPP-4 inhibitor 1.8%." |
| 2 | **2 · eGFR 40, past pancreatitis** | "The SGLT2 inhibitor is red: excluded by rule R01 with its FDA label source, and never estimated. The DPP-4 inhibitor is amber: caution for R04 and R05." |
| 3 | **3 · Older, past hypoglycaemia** | "The sulfonylurea is grey: insufficient evidence. Almost no similar patient got it (propensity 0.006, below 0.05), so we refuse to guess." |
| 4 | Open **Evidence for this option** on the DPP-4 card | "Evidence fusion: licence-cleared passages about this drug class, with the source — here the FDA joint-pain communication." |
| 5 | **Print or save as PDF** | "A one-page consultation summary: patient as entered, ranges, rule sources, versions, no doses." |
| 6 | Evidence → **SGLT2i and ketoacidosis** | "The explanation quotes the FDA passages, each sentence numbered to its source." |
| 7 | Evidence → **Not in the sources** | "Glimepiride price in India isn't in our sources, so it says insufficient evidence instead of making something up." |
| 8 | Type "What dose of glimepiride should I start with?" | "Dose questions are always refused: doses come only from the label and the doctor." |
| 9 | Results tab | "The benchmark on synthetic data: naive vs corrected, against the known truth." |

**If anything fails:** "Here is the same demo, recorded yesterday." Play the video. Don't apologise at length.

---

## 7. Q&A bank

The detailed answers are in `docs/06_Viva_Prep.md`. These are the ones most likely on the day.

### Causal inference and statistics
1. **What is causal inference, in one line?** Estimating what *would* happen under each choice
   for the same patient, not just what happened to people who made that choice.
2. **What is confounding by indication?** Doctors choose drugs based on the patient, so the
   patient's condition affects both the drug and the outcome. The worked example: naive −0.425
   vs fair −0.15.
3. **What is a propensity score?** The probability that a patient like this received each drug,
   given their details. We use it to check overlap and to weight patients.
4. **Why 0.05?** Below that, fewer than 1 in 20 similar patients got the drug. Weights would
   exceed 20, and the estimate would rest on a handful of people. It is the standard positivity
   cut-off in `params.yaml`, marked TEAM-SET.
5. **What does "doubly robust" mean?** AIPW combines an outcome model and a propensity model. It
   stays unbiased if *either one* is right.
6. **AIPW vs DR-learner?** AIPW gives the *average* effect in the population. The DR-learner
   gives the effect *for this patient*, by regressing the AIPW scores on patient features.
7. **How do you get a 95% interval?** For AIPW, the influence function (mean ± 1.96 × SE). For
   the DR-learner, HC3 robust standard errors on the second-stage regression. For matching, a
   bootstrap.
8. **What is coverage and why does it matter?** The share of repeats where the 95% interval
   contains the truth. It should be about 95%. AIPW gets 0.95; naive gets 0.00.
9. **What is PEHE?** The average error in the per-patient effect (RMSE across patients). The
   DR-learner scores 0.105–0.117, against 0.184–0.192 for the T-learner.
10. **The S-learner's PEHE is similar. Why not use it?** Its point accuracy is similar in this
    simulation, but it gives no valid 95% interval, and our rule is that every number carries one.
11. **What are refutation tests?** Checks that should fail if the method were fooling itself: a
    placebo drug, a random common cause, a data subset. All 9 pass.
12. **What is an E-value?** How strong an unmeasured confounder would need to be, in risk-ratio
    terms, to explain the effect away. Ours are 1.57–2.15.
13. **What about unmeasured confounding in real data?** That is exactly what E-values quantify.
    In real data we'd also add a negative-control outcome. On synthetic data, we know there is
    none by construction.
14. **What is policy regret?** How much HbA1c benefit you'd lose by following the model's pick
    instead of the truly best allowed drug. DR-learner 0.011 points vs naive 0.062.

### Data
15. **Why not Pima or a Kaggle dataset?** Pima is data from Pima (Akimel O'odham) women in Arizona, USA, with no drug
    choice and no follow-up. It cannot answer our question.
16. **Where do the synthetic numbers come from?** Every one is in `data/params.yaml`, with a
    source and a status. Examples: ICMR-INDIAB, Misra 2009 (BMI cut-offs), Palmer 2016 and
    Tsapas 2020 (drug-effect directions), the TriMaster trial, and a team worksheet of Indian
    survey figures. Many are TEAM-SET, which is said openly. The loader refuses an unsourced number.
17. **When will you use real data?** After ethics approval, as a de-identified CSV.
    `cohort.load_dataset()` already reads it; we would rerun the benchmark checks.
18. **Is the cohort "India-calibrated"?** Its age, HbA1c, eGFR and BMI distributions and
    prevalences follow Indian sources, and it uses Asian-Indian BMI cut-offs (23 and 25).

### Safety, ethics and regulation
19. **Is this a medical device?** No. It is a research prototype for clinician evaluation, not
    for unsupervised clinical use. That sentence is on every screen and every API reply.
20. **What stops a dangerous suggestion?** Cited rules run first and remove unsafe options.
    Doses are never shown. Low overlap or a too-wide range means "insufficient evidence", and
    nothing is ever green for "recommended". The doctor decides.
21. **Where do the thresholds come from?** Nine rules from FDA labels (with section numbers) and
    one team rule pending review; any team-set cut-off is marked so and waits for a doctor to confirm
    it. They are in one table (`data/rules.csv`), never in code.
22. **What about patient privacy?**
    - The website computes on the phone, and patient values are never sent.
    - Logs hold IDs and outcomes, never values or message text.
    - Voice audio stays on our server and is deleted after decoding.
23. **Why no doses?** Dosing depends on details we don't model, and a wrong dose is directly
    harmful. Doses belong to the label and the prescriber.

### RAG and LLMs
24. **What is RAG?** Retrieval-augmented generation: first *find* the relevant passages in
    approved documents, then answer *only* from them, citing each one.
25. **Why not just ask ChatGPT or Gemini?** They can state things that aren't in any source and
    can't show where each claim came from. We need every sentence traceable to a licensed page,
    and a refusal when there is nothing.
26. **How do you stop the model inventing things?** The citation checker. Every sentence must
    cite a shown passage and share most of its words with it, and contain no dose. If not, we
    show the quotes instead. The default mode doesn't generate at all; it quotes.
27. **BM25 vs vector search?** BM25 matches exact terms ("eGFR", "pancreatitis"). Vector search
    matches similar wording. Rank fusion keeps passages that either method ranks highly.
28. **Why TF-IDF and not embeddings?** It is fully reproducible in the browser today. A medical
    embedding model and a reranker are the October upgrade, and there is a slot for them in the code.
29. **Abstention is 0.80, below the 0.95 target. Why?** Two out-of-scope questions (a
    gestational-diabetes diet question, statins) share enough words with our documents to slip
    through. We report it openly. The fix is semantic search and a reranker, then a held-out test set.
30. **Weren't the thresholds tuned on the test set?** Yes, and we say so: the numbers are
    optimistic. The doctor's review and a separate held-out set are the honest next test.
31. **Licences?** Each source has a licence row. Only confirmed, cleared sources are ingested:
    WHO under CC BY-NC-SA 3.0 IGO with attribution, and FDA texts as US government works. ADA,
    IDF and NICE are cite-only.
32. **Does Gemini see patient data?** No. Only the question and the IDs of the passages go to our
    server, which rebuilds the passages. Only approved, MFA-verified users can call it. The key
    is a server secret.
33. **Offline?** Yes. The quoted explanations need no internet, and a local model (Ollama) can
    reword them on a laptop or hospital PC (`docs/OFFLINE_INSTALL.md`).

### Software, security and engineering
34. **Why the same engine in Python and JavaScript?** So the phone computes privately. Tests
    compare the two on 155 patients and 100 questions, and they must agree.
35. **How are passwords and sessions protected?**
    - Chat app: Argon2id hashes, TOTP MFA, `__Host-` cookies, CSRF tokens, lockout, audit log.
    - Website: Supabase auth with MFA, row-level security and admin approval.
36. **How do you know it works on other computers?** GitHub CI runs everything on Linux, macOS
    and Windows, with exact version pins.
37. **What is the trace ID for?** To follow one message through the browser console and every
    server log line, without ever logging its content.
38. **Why Docker with one origin?** No CORS configuration to get wrong, secure cookies work, and
    HTTPS enables the microphone.

### Scope and future
39. **Why only three drug classes?** They are the common oral add-ons after metformin in India. A
    narrow scope lets us do it properly; GLP-1 and insulin are future work.
40. **Why HbA1c at 6 months?** It is the standard glycaemic outcome in trials and guidelines.
    Weight and hypoglycaemia are now secondary outcomes.
41. **What is left?**
    - The engine and RAG inside the chat app;
    - doctor review and SUS;
    - an embedding model and reranker;
    - results frozen 16 October;
    - the paper;
    - the final report.
42. **What would a hospital deployment look like?** An offline install on the hospital's own
    machines (`docs/OFFLINE_INSTALL.md`), a local de-identified dataset after ethics approval,
    and the same rules and tests.
43. **What is novel here?**
    - Causal per-patient estimates *with* intervals and abstention;
    - safety rules strictly before estimation;
    - licence-gated, citation-checked evidence;
    - all of it reproducible on a phone and validated against a known truth.
44. **What did each member do?** Each person answers for their own part in one sentence. Write
    yours here before the day, matching the slides you present: ____________________
45. **What if the doctor disagrees with the estimate?** Then the doctor is right to decide. The
    tool shows evidence and uncertainty and records the request; it never overrides.

---

## 8. Honest limitations and the October plan

**Limitations to state if asked**
- **Synthetic data:** the results prove the methods recover a planted truth, not real-world drug effects.
- **Search:** it is lexical (BM25 + TF-IDF). Abstention is 0.80, below target, and was tuned on
  the same test set.
- **Clinical review:** no doctor has reviewed the test set or the vignettes yet.
- **Chat app:** all six stages run since 29 September, but the explanation uses the quoted template
  by default; Gemini / Ollama are optional and always pass the citation checker.
- **Prices:** "price unavailable" until the Jan Aushadhi list is confirmed.
- **Rule cut-offs:** some are TEAM-SET and await clinician confirmation.

**October (as in the interaction sheet and the Gantt chart)**
- Done early: the engine and RAG inside the chat app pipeline (29 Sep, the sheet's 60% check).
- A medical embedding model and a reranker; a held-out test set (target 3 Oct, the 80% check).
- A real-data adapter and evaluation tools (target 6 Oct, 100% implementation).
- Doctor review of the 20 flagged test questions and the clinician vignettes; the SUS usability study.
- Guide evaluation 26–31 Oct; results frozen on 16 October; the IEEE-style paper; the final report.

---

## 9. Numbers card

All results are on **synthetic data**. Each row names its source file.

**Benchmark: 20 cohorts × 5,000 patients, 2,000 test patients** (`results/run_info.json`, `results/benchmark_summary.csv`)

| Comparison | Truth | Naive: bias / coverage | IPW | Matching | AIPW: bias / coverage |
|---|---|---|---|---|---|
| SGLT2i vs DPP-4i | −0.211 | −0.159 / 0.00 | +0.001 / 1.00 | −0.002 / 0.95 | **+0.002 / 0.95** |
| SU vs DPP-4i | −0.256 | −0.106 / 0.00 | −0.004 / 1.00 | −0.008 / 1.00 | **−0.003 / 0.95** |
| SGLT2i vs SU | +0.045 | −0.052 / 0.50 | +0.005 / 0.95 | +0.006 / 0.95 | **+0.005 / 0.90** |

**Per-patient effects and policy** (`benchmark_summary.csv`)

| Learner | PEHE (SGLT2i–DPP4i / SU–DPP4i / SGLT2i–SU) | Policy regret |
|---|---|---|
| DR-learner | 0.105 / 0.117 / 0.108; 95% coverage 0.94 / 0.95 / 0.93 | 0.011 |
| S-learner | 0.103 / 0.104 / 0.110 (no intervals) | 0.012 |
| T-learner | 0.189 / 0.192 / 0.184 | 0.029 |
| Naive | 0.214 / 0.197 / 0.169 | 0.062 |

**Other checks**
- **Balance:** largest |SMD| 0.70 before → 0.08 after IPW (0.7038 → 0.0775 in the file). Abstention in the benchmark: 2.5% of
  patient–option pairs.
- **Refutation** (`results/refutation.csv`): 9 of 9 pass.
- **E-values** (`results/evalues.csv`): 1.72 / 2.15 / 1.57 (confidence-interval limits 1.54 / 1.95 / 1.39).

**Secondary outcomes** (`benchmark_summary.csv`, sections `secondary_weight`, `secondary_hypo`)
- Weight, SGLT2i vs SU: truth −3.33 kg, AIPW −3.33 (coverage 1.00).
- Weight, SU vs DPP-4i: truth +1.50, AIPW +1.48.
- Hypoglycaemia, SU vs DPP-4i: truth +12.85 points, AIPW +12.55.
- Per-patient 95% coverage: weight 0.94–0.96; hypoglycaemia 0.93–0.94.

**Demo presets** (website engine, reference cohort n = 5,000)

| Preset | SGLT2i | DPP-4i | Sulfonylurea |
|---|---|---|---|
| 1 · Typical: 52 y, HbA1c 8.4, eGFR 88, BMI 27 | −0.93 (−0.98 to −0.87); −2.1 kg; low sugar 2.5% | −0.70 (−0.76 to −0.64); −0.4 kg; 1.8% | −0.94 (−1.00 to −0.88); +1.0 kg; 9.9% |
| 2 · eGFR 40, past pancreatitis | **Excluded** (R01) | −0.68 (−1.09 to −0.27), caution R04, R05 | −0.82 (−1.21 to −0.42), caution R09 |
| 3 · 80 y, eGFR 38, past hypoglycaemia | **Excluded** (R01) | −0.63 (−0.86 to −0.41), caution R04 | **Insufficient evidence** (propensity 0.006), caution R07–R09 |

**RAG** (`results/rag_eval_summary.csv`; 60 test questions; 78 passages from 8 documents)

| Recall@5 | Answered | Citation precision | Dose leaks | Out-of-scope refused |
|---|---|---|---|---|
| 0.933 | 0.978 | 1.000 | 0 | 0.800 |

**Tests** (`docs/TESTING.md`)
- Engine 150 · RAG 33 · website 19 (= 202).
- Chat app: backend 401 · frontend 246 · `check_all` 43 checks.
- CI on Linux, macOS and Windows.

---

## 10. Glossary

| Term | Plain meaning |
|---|---|
| HbA1c | Average blood sugar over about 3 months, in %. Our outcome is its change in percentage points. |
| eGFR | Kidney function, mL/min/1.73 m². Lower is worse; several rules depend on it. |
| SGLT2i / DPP-4i / SU | The three add-on drug classes, e.g. dapagliflozin / sitagliptin / glimepiride. |
| Confounding by indication | Sicker patients get certain drugs, so naive comparisons mislead. |
| Propensity score | The chance that a patient like this got each drug. |
| Overlap / positivity | Enough similar patients got each drug to compare fairly (propensity ≥ 0.05). |
| IPW | Inverse probability weighting: re-weight patients so the groups are comparable. |
| AIPW | Doubly robust average effect: outcome model + weighted correction. |
| DR-learner | Doubly robust per-patient effect with a 95% interval. |
| SMD | Standardised mean difference; below 0.1 = balanced. |
| Coverage | How often a 95% interval contains the truth (target about 0.95). |
| PEHE | Per-patient effect error (lower is better). |
| E-value | Strength a hidden confounder would need to explain the effect away. |
| DAG | A causal diagram deciding which variables to adjust for. |
| RAG | Find approved passages first, answer only from them, cite each. |
| BM25 / TF-IDF | Keyword ranking / word-weight vector similarity. |
| RRF | Reciprocal rank fusion: merges several rankings. |
| Recall@5 | The right passage is among the top 5. |
| Citation precision | The share of explanation sentences truly supported by the passage they cite. |
| Abstention | Saying "insufficient evidence" instead of answering. |
| TOTP / MFA | The 6-digit authenticator code; the second sign-in factor. |
| RLS | Row-level security: the database only returns rows the user may see. |
| PWA | A website that can be installed on a phone and work offline. |
| TEAM-SET | A value our team chose (with its reason), to be confirmed by a clinician. |

---

*Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised
clinical use. All results on synthetic data.*
