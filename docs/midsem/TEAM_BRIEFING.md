# DiaCausal team briefing: the whole deck and the whole implementation

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

**For Pratham, Graceton and Advik (from Rhian).** Read this once, top to bottom, with the deck
(`Intelligent_Diabetes_CDSS_MidSem_updated.pptx`, 39 slides) open beside it. It is written the way we
will explain it to Mr. Rahul Jadhav and to the panel on 30 September. About 40 minutes.

Each slide has four parts:
- **On the slide:** what is on it.
- **Say:** the words to use (the same as the speaker notes).
- **Understand:** what it really means, one level deeper than you will say.
- **If asked:** the question most likely to come, with a short answer.

Part 2 then walks through the code, folder by folder, so you can open any file and say what it does.

---

## The one-minute story (everyone should be able to say this)

When metformin alone does not control an adult's type 2 diabetes, the doctor adds a second drug. There are three
common choices: an **SGLT2 inhibitor**, a **DPP-4 inhibitor** or a **sulfonylurea**. Which one will lower
*this* patient's HbA1c the most? Old hospital records mislead, because doctors give different drugs to different
kinds of patients (that is *confounding*).

DiaCausal works in four steps:
1. It removes any drug that is unsafe for this patient, using cited rules from drug labels.
2. It estimates each remaining drug's 6-month HbA1c change with a **95% range**, using causal-inference
   methods that correct for confounding. If the data cannot support a fair answer, it says **"insufficient
   evidence"** and gives no number.
3. It also shows weight change and low-sugar risk, and quotes **cited evidence** from WHO and FDA documents.
4. **The doctor decides.**

We test the methods on a synthetic India-calibrated cohort, because only there do we know the true answer. A real
Indian survey (NMB-2017) checks that our synthetic patients look real.

**Where we are:** about 64% of the whole project is built and tested. The interaction sheet asked for 25% by
23 September and 40% by 7 October; both are already met.

---

## Part 1: the deck, slide by slide

Presenters are suggestions: **Pratham** 1–3, 27, 31–34 · **Rhian** 4–7, 22–23, 26, 28 · **Advik** 8–13,
24–25, 30 · **Graceton** 14–21, 29. Slides 35–39 are backup, shown only if asked.

### 1–2 · Title, team (Pratham)
- **Say:** "Good morning. We are Group 28. Our project is an Intelligent Diabetes Clinical Decision Support
  System. It helps a doctor choose the second medicine for an adult with type 2 diabetes who already takes
  metformin. Our guide is Mr. Rahul Jadhav."
- **Understand:** "Clinical decision support" means the system *supports* the decision. It never makes it. This
  is also why we say "research prototype, not a medical device" everywhere.

### 3 · Presentation outline (Pratham)
- **Say:** read the ten headings in one breath. Stress "scope", "working of the system" and "interaction
  sheet", because our guide asked for those.

### 4 · Problem statement (Rhian)
- **On the slide:** a table of made-up numbers. High-HbA1c patients mostly got SGLT2i and lower-HbA1c patients
  mostly got sulfonylurea.
- **Say:** "Comparing the two groups directly gives −0.425, but comparing like with like and then averaging
  gives −0.15. The naive answer is about three times too big."
- **Understand:** this is **confounding by indication**, also called Simpson's paradox. The drug groups differ
  *before* treatment, so a straight comparison mixes the drug's effect with the difference between the patients.
  Everything else in the project exists to fix this fairly.
- **If asked "why not just use a machine-learning classifier?":** a classifier predicts *who* gets better. We
  need *what would happen under each drug* for one patient, which is a causal question.

### 5 · How DiaCausal works (Rhian)
- **On the slide:** seven steps: patient details → safety rules → propensity and overlap → estimates with 95%
  ranges (plus weight and low-sugar risk) → cost → cited evidence (RAG) → doctor decides. Every request is logged.
- **Understand:**
  - **Propensity** = the chance that a patient like this one got each drug. If that chance is below 0.05, too
    few similar patients got the drug, so we refuse to estimate.
  - The **dashed box** (evidence) is built and works on the website; it joins the chat app in October.
- **If asked "what is logged?":** the request ID, versions, rule IDs and statuses. **Never** patient values or
  message text.

### 6 · Block diagram (Rhian)
- **Say:** "A question goes to two pipelines at the same time. The RAG pipeline finds evidence in documents. The
  causal pipeline produces estimates or NOT_APPLICABLE. Both meet in the evidence-fusion layer, then the LLM
  writes the answer and a safety layer checks it."
- **Understand:** this is the team's original design. Today, the causal pipeline and the RAG pipeline are both
  built and tested *separately*. Joining them in the chat app is implementation Section 3 (target 3 Oct).

### 7 · Flowchart (Rhian)
- **Say:** walk the RAG column top to bottom, then the causal column, then the fusion column.
- **Understand, what is built vs designed:**
  - **RAG:** ingestion, chunking, BM25 + TF-IDF search and reciprocal rank fusion are built. The dense
    medical embedding and the cross-encoder reranker are Section 4.
  - **Causal:** the DAG, propensity, AIPW, DR-learner (CATE) and counterfactuals are built.
- **If asked "is the LLM trusted?":** no. Every sentence it writes must cite a passage that was shown, most of
  its words must appear in that passage, and it may contain no dose. If any sentence fails, we show quoted
  sentences instead.

### 8 · Safety rules (Advik)
- **Say:** the six rules:
  1. the doctor decides;
  2. safety rules run before any estimate;
  3. doses and thresholds come only from cited tables;
  4. we refuse to guess;
  5. every estimate has a 95% range;
  6. everything is logged.
- **Understand:** each rule is enforced by a **test**. For example, a test scans the code for hard-coded
  thresholds, and the output check refuses any dose-like text.

### 9 · Scope (Advik) *(new: the guide wrote "scope needs enhancement" in week 4)*
- **Say:** "In scope: adults on metformin, three drug classes, three outcomes with ranges, safety rules, cited
  evidence, for clinicians. Out of scope, where the system says so and stops: type 1, pregnancy, under-18s,
  insulin start, emergencies, doses, diagnosis, identifiers, real data for now. Future scope: more drug classes,
  Indian prices, hospital data with ethics approval, Indian languages."
- **Understand:** the "out of scope" items are *enforced*. The chat app's guards read them from
  `shared/guard_rules/rules.v1.json` and show an "Out of scope" notice (you can see this on slide 25).

### 10 · Hardware and software (Advik)
- **Say:** "An ordinary 8 GB laptop. Python 3.12 with NumPy, pandas, scikit-learn and FastAPI; React for the chat
  app; the website on Netlify with Supabase accounts. The RAG part uses PDF text extraction, a hybrid BM25 and
  TF-IDF search and quoted answers; optionally Gemini online or Ollama offline."
- **If asked "why no GPU?":** the estimators are regression and gradient-boosting models; a full benchmark
  takes about 15 minutes on a laptop CPU.

### 11 · System requirements (Advik)
- **Say:** "All nine functional requirements are built, including weight and low-sugar risk, cited evidence
  and the website with accounts. Prices show 'unavailable' until confirmed with a date and source."
- **Understand:** the non-functional targets are honest. Speed is measured (about 12 ms per request);
  coverage and accessibility (WCAG) are *not yet measured*, and the slide says so.

### 12 · Gantt chart (Advik) *(new: built from the interaction sheet)*
- **Say:**
  - "Every row follows our project interaction sheet. Weeks 0 to 6 are done and signed by our guide."
  - "Implementation is split into four sections, as the sheet asks. The diamonds are the sheet's deadlines:
    25% by 23 September and 40% by 7 October are already met. Section 3 is in progress. Our own target for all
    four sections is 6 October."
  - "Then guide evaluation, the final synopsis, the paper, and the evaluation, PCUBE and black book next year."
- **If asked "is 6 October realistic?":** Sections 1–2 took two weeks. Section 3 connects parts that already
  work and are tested; Section 4 is improvement, not new ground.

### 13 · Timeline chart (Advik) *(new)*
- **Say:** "Every entry of the interaction sheet, with its date and status. Everything up to week 7 is signed.
  Today is Synopsis Presentation-II."

### 14 · Architecture (Graceton)
- **Say:** "The clinician uses the website or the chat app, which call our FastAPI service. The API sends each
  request to the safety rules first, then the causal engine, then cost lookup. The RAG layer is built and reads
  only licence-cleared documents; it joins the API in October. Every request goes to the audit log."

### 15 · Data flow, DFD levels 0 and 1 (Graceton)
- **Say:** "Level 0: patient details come in; options with 95% ranges and sources go out; passages come from the
  guideline documents; IDs go to the audit store. Level 1 opens that box into six processes: validate, safety
  rules, causal engine, cost, RAG explanation, log and display. Each reads its own data store."

### 16 · Use case and sequence (Graceton)
- **Say:** "Three actors. The clinician enters a patient, views the comparison and evidence, and exports a
  summary. The evaluator reviews logs and runs the benchmark. The admin manages rules, sources and account
  approvals. The sequence shows one consultation: safety rules first, only allowed options go to the engine,
  then evidence, then the log."

### 17 · Working of the system (Graceton) *(new: the guide wrote "working of the system: not done" in week 6)*
- **On the slide:** demo patient 2, a 60-year-old woman with HbA1c 8.2%, eGFR 40, BMI 25.5 and past
  pancreatitis, taken through every step with the engine's real output.
- **Say:**
  - "Safety rules run first. The SGLT2 inhibitor is **excluded**, because eGFR is below 45 (rule R01). The
    DPP-4 inhibitor gets cautions for kidney dosing and pancreatitis (R04, R05). The sulfonylurea gets a
    kidney caution (R09)."
  - "Both remaining drugs have enough similar patients: propensity 0.54 and 0.23, above 0.05."
  - "Estimates: DPP-4i −0.68 (−1.09 to −0.27), sulfonylurea −0.82 (−1.21 to −0.42). The ranges overlap, so
    neither is clearly better, and we say so."
  - "The doctor decides; the log keeps only IDs and versions."
- **Understand:** this is the best slide to show that the system is **honest**. It does not rank drugs whose
  ranges overlap.

### 18 · Data and API (Graceton)
- **Say:** "Rules live in `rules.csv`: ten rules, each with a source, section and status. Unverified cut-offs are
  flagged for the doctor. Prices live in `prices.csv`. The API takes the patient's details and returns each
  option's estimate with its range, or insufficient evidence, plus exclusions, versions and a request ID."

### 19 · Datasets: what we use (Graceton)
- **Say:** "Six data sources:
  - the **synthetic cohort** (to train and grade the engine);
  - **safety rules** and **evidence sources** (real documents);
  - the **generator parameters** (each with a source and status);
  - our **60 test questions**;
  - and **NMB-2017**, real Indian data, to check realism.
  No public Indian dataset records which drug each patient got together with their HbA1c six months later, so
  the engine is trained and graded on synthetic data, where the true effect is known."

### 20 · Synthetic cohort (Graceton)
- **Say:** the five steps: draw 5,000 realistic patients; give drugs the way doctors tend to (this builds in
  confounding); compute each patient's result under all three drugs; keep only the drug they got; weight and
  low-sugar risk the same way. "The picture shows the first 8 patients: only these columns reach the
  estimators, the same columns a hospital record would have."
- **Understand:** because we also stored the *hidden* results (backup slide 35), we can measure each method's
  error exactly. On real data that is impossible.
- **If asked "who decided the numbers?":** all 117 numbers are in `data/params.yaml`, each with a source and a
  status. 9 are cited, 15 are assumed in direction from studies, and 93 are team-set, mostly method settings
  and plausibility limits. The loader refuses any number without a source.

### 21 · Real Indian data, NMB-2017 (Graceton)
- **Say:** "NMB-2017 is a nationwide survey of 7,496 Indian adults with HbA1c, free to use (CC0). It has no drug
  choice or follow-up, so it cannot train a causal engine, but it checks realism. Our synthetic patients match
  real Indian adults with diabetes on age (55 vs 54), BMI (26.4 vs 26.6) and sex. Our HbA1c is a little lower
  and narrower (8.6 vs 9.2), which we will fix and cite."
- **If asked "why not Pima?":** Pima is data from Native American women in the US, not Indians, and it has no
  drug or outcome.

### 22 · What's built (Rhian)
- **Say:** "Every module is done. 150 engine tests, 33 RAG tests and 19 website tests pass, plus 630 in the
  chat app."

### 23 · How the code works (Rhian)
- **Say:**
  - "The AIPW score starts with the outcome model's guess, then corrects it using patients who really got that
    drug, weighted by one over the propensity. If either model is right, the average is right; that is why it
    is called doubly robust."
  - "The DR-learner regresses these scores on patient details, and a robust (HC3) standard error gives each
    patient's 95% interval."
- **Understand:** **cross-fitting** means each patient's scores come from models trained on the *other*
  folds, so a model never grades its own training data.

### 24 · Website screens (Advik)
- **Say:** "diacausal.netlify.app runs the same engine in the browser and works offline. Try it shows three
  options with ranges, weight and low-sugar risk. Safety rules exclude or caution options with their sources. The
  Evidence tab answers only with quoted, cited sentences. Results shows the benchmark. Sign-in needs an approved
  account and an authenticator app."
- **Understand:** the browser engine gives **exactly** the same numbers as Python. A parity test checks this
  on every change.

### 25 · Chat app screens (Advik)
- **Say:** "FastAPI with React. Sign-in uses a password, a CAPTCHA with an audio option, and an authenticator
  app. The reply lists six pipeline stages; three run today. Guards remove identifiers such as phone numbers and
  refuse out-of-scope questions."
- **Understand:** the three stages still "skipped" (causal engine, RAG, explanation) are exactly Section 3.
  They are the only part of the design not yet joined.

### 26 · Accuracy (Rhian)
- **Say:**
  - "On synthetic data we know the truth: −0.211. The naive comparison is off by −0.159. IPW, matching and
    AIPW bring the bias to about 0.002."
  - "AIPW's 95% intervals contain the truth 90–95% of the time, and the DR-learner's per-patient intervals
    92.7–94.7%. All nine refutation checks pass."
- **If asked "90% is below 95%":** that is across 20 cohorts. With 20 repeats, 18 or 19 out of 20 is within
  normal random variation of 95%.

### 27 · Plots (Pratham)
- **Say:**
  - **Overlap** (top left): "Below the dashed line at 0.05 the system abstains."
  - **Balance** (top right): "After weighting, every detail is under 0.1, so the groups look alike."
  - **Bottom:** "Each dot is a new test patient; the estimates lie close to the diagonal."

### 28 · Evidence search results (Rhian)
- **Say:** "60 test questions. The right source is in the top five 93% of the time. Every quoted sentence cites a
  passage that really contains it, and no dose ever leaks. It correctly says 'insufficient evidence' for 80% of
  out-of-scope questions; our target is 90%, so the medical embedding model in Section 4 must improve this."
- **Understand:** we **tell** the panel the weak number ourselves. That builds trust.

### 29 · Demo (Graceton with Rhian at the laptop)
- **Do:** open diacausal.netlify.app (signed in no more than 15 minutes earlier) and click presets 1, 2 and 3.
  - **Preset 1:** three teal estimates.
  - **Preset 2:** red SGLT2i with its source; amber cautions.
  - **Preset 3:** grey "insufficient evidence" for the sulfonylurea.
  - Then the Evidence tab: the ketoacidosis chip, then a dose question, which is refused.
- **Backups:**
  - `cd web && python3 -m http.server 8080` (a local copy, no sign-in);
  - `DiaCausal_demo.mp4` (112 s).

### 30 · Completed vs planned (Advik)
- **Say:** "Completed is on the left. The plan follows our interaction sheet: the 40% check is already met; the
  60% and 80% checks come on 14 and 21 October, and we aim to finish all four sections by 6 October. Then guide
  evaluation, the final synopsis, the paper in December, and the evaluation, PCUBE and black book next year."

### 31 · Progress: about 64% (Pratham)
- **Say:** "Each part is weighted by its share of the year, and each percentage points to tests or files. Chat app
  about 95%, causal engine 90%, RAG 75%, joining them 10%, clinician evaluation 20%, report and paper 40%. That is
  about 64% overall."
- **If asked "why only 10% for joining?":** in the chat app, three of the six pipeline stages still return
  "skipped". That is Section 3, finishing this week.

### 32–34 · Conclusion, references, thank you (Pratham)
- **Say:** "The causal engine works and recovers the planted truth; the evidence search answers only with cited
  sentences; safety rules always run first; we are honest about uncertainty. Next: one chat app, a doctor's
  review and our IEEE paper. The doctor always decides."

### 35–39 · Backup slides (whoever is asked)
- **35 · Why synthetic is valid:** real records never show the other drug's result; simulation with a known truth
  is how causal methods are tested (the ACIC challenges and the IHDP benchmark). It proves the *method*, not the
  drug effects.
- **36 · Real Indian datasets:**
  - NMB-2017 (open, in our repo);
  - LASI (free request form);
  - NFHS-5 (registration);
  - CARRS (on request);
  - ICMR-INDIAB (tables only);
  - a Pune clinic study (on request).
  None has drug choice plus a later HbA1c.
- **37 · Path to a hospital:** records with ethics approval (DPDP Act 2023), the same code, checks against
  trials, a silent pilot, then a CDSCO device review.
- **38 · Phone screens.**
- **39 · Literature:** 16 papers reviewed; the comparison table shows what each one misses.

---

## Part 2: the implementation, folder by folder

Everything is on GitHub: `Rhian-Roy/DiaCausal-CDSS`. **Four parts** make up the system.

### A. The causal engine: `diacausal_engine/` (Python)
| File | What it does |
|---|---|
| `cohort.py` | Makes the synthetic cohort (5 steps above); `observed_view()` hides the truth columns |
| `config.py` | Loads `data/params.yaml`; refuses any number without a source and status |
| `dag.py` | The causal diagram: which details are confounders (adjusted for) and which are mediators (not adjusted for) |
| `guardrails.py` | Applies `data/rules.csv` **before** any estimate (exclude / caution) |
| `propensity.py` | Cross-fitted multinomial propensity (chance of each drug) and the 0.05 overlap rule |
| `estimators.py` | Naive, IPW, matching, AIPW (average effects with 95% intervals) |
| `fitting.py` | DR-learner: per-patient effects with HC3 95% intervals |
| `metrics.py`, `benchmark.py` | Bias, RMSE, coverage, PEHE, regret; 20 cohorts × 5,000 patients → `results/` |
| `refute.py` | 9 refutation checks (placebo, random common cause, subset) and E-values |
| `recommend.py` | One patient → Causal Output (safety first, estimates, secondary outcomes, cost, audit) |
| `api.py` | `POST /api/v1/recommend` (FastAPI) |
| `export_web.py` | Writes `web/model.json` so the website runs the same engine |

- **Run it:** `.venv/bin/python -m pytest tests/engine -q` (150 tests) ·
  `.venv/bin/streamlit run demo/streamlit_app.py`.

### B. The evidence search (RAG): `diacausal_rag/` (Python)
| File | What it does |
|---|---|
| `RAG/sources.csv` | The licence gate: only `cleared_ingest` sources that a named person checked go in |
| `ingest.py`, `pdf_text.py` | PDF/text → sentence-aware chunks of about 400 words with citations |
| `retrieve.py` | BM25 + TF-IDF, fused with reciprocal rank fusion; abstains when a question's words are poorly covered; hides dose text |
| `explain.py` | Quoted answer (default), or Gemini / Ollama, checked by `check_answer()` |
| `evaluate.py` + `eval/rag_gold.csv` | 60 questions → recall@5, abstention, citation precision, dose leaks |

- **Run it:** `.venv/bin/python -m pytest tests/rag -q` (33 tests) ·
  `.venv/bin/python -m diacausal_rag.explain "Can SGLT2 inhibitors cause ketoacidosis?"`.

### C. The website: `web/` (JavaScript, no framework)
- **Files:**
  - `engine.js` mirrors `recommend.py`; `evidence.js` mirrors `retrieve.py`; `explain.js` mirrors `explain.py`.
    Parity tests prove they match.
  - `auth.js` and `account.js` handle accounts: Supabase, admin approval and the authenticator app.
  - `sw.js` provides offline use.
  - `supabase/` holds the database migrations and the Gemini Edge Function.
- **Live:** https://diacausal.netlify.app.
- **Run it locally:** `cd web && python3 -m http.server 8080`.
- **Test it:** `.venv/bin/python -m pytest tests/web -q` (19 tests).

### D. The chat app: `backend/` (FastAPI) + `frontend/` (React + TypeScript)
| Where | What it does |
|---|---|
| `backend/app/pipeline/` | Six stages in order: `backend_guard` → `clinical_guardrails` → `causal_engine` → `rag_retrieval` → `llm_explanation` → `output_guard` |
| `backend/app/auth/` | CAPTCHA, Argon2id passwords, authenticator codes (TOTP), sessions, CSRF, lockout, audit |
| `backend/app/clinical/guardrails.v1.yaml` | The chat app's clinical thresholds (with sources) |
| `shared/guard_rules/rules.v1.json` | Words and patterns the guards block: identifiers, out-of-scope topics, emergencies |
| `backend/app/voice/` | Speech to text on the computer (faster-whisper); the text goes in the box, never sent automatically |
| `frontend/src/lib/chatFlow.ts`, `guards.ts` | Browser-side guards and the trace-ID logging (`[id] input passed` …) |
| `frontend/src/features/` | Sign-in, patient panel, voice |
| `compose.yaml`, `docker/` | One-command deployment with HTTPS (Caddy) |

- **Run it:** see `CLAUDE.md` → "Run".
- **Check it:** `python3 scripts/check_all.py` must end with "ALL 43 CHECKS PASSED".

### What Section 3 (this week) changes
The three "skipped" stages call parts A and B:
- `causal_engine.py` → `diacausal_engine`
- `rag_retrieval.py` → `diacausal_rag.retrieve`
- `llm_explanation.py` → `diacausal_rag.explain`

The reply then shows option cards and cited evidence inside the chat app. Every rule above stays (safety first,
no doses, 95% ranges, no patient values in logs).

---

## Ten questions each of us must be able to answer

| Question | Short answer |
|---|---|
| **Is this a medical device?** | No: a research prototype for clinician evaluation; the doctor decides. |
| **Why causal inference, not prediction?** | Prediction says *who* improves; we need *what would happen under each drug* for one patient. |
| **Why synthetic data?** | Only there is the true effect known, so methods can be graded; there is no public Indian data with drug + later HbA1c. |
| **What proves it works?** | Bias 0.159 → 0.002; 90–95% coverage; 9 of 9 refutation checks; 150 tests. |
| **What if data are thin?** | Propensity below 0.05 → "insufficient evidence", no number. |
| **How do you stop unsafe advice?** | Cited rules run first; doses never shown; an output check; the LLM must cite. |
| **Where does RAG get its facts?** | Only WHO 2018 and 7 FDA safety notices that passed the licence gate. |
| **Weakest result?** | RAG abstention 0.80 vs target 0.90; the fix is the medical embedding model (Section 4). |
| **How would a hospital use it?** | Ethics-approved records → same code → checks against trials → silent pilot → device review. |
| **Percent done?** | About 64% weighted; the sheet's 25% and 40% checks are met; target 100% implementation by 6 Oct. |

The full handbook (`EXPLAINING_DIACAUSAL.pdf`, 45 questions) and `DATASETS.pdf` go deeper.
