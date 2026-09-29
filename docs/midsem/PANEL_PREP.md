# DiaCausal panel prep pack: from zero to ready

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

**For all four of us (Pratham, Rhian, Advik, Graceton), before Synopsis Presentation-II on 30 September.**
This pack assumes you know **nothing** about the project. Read it in this order:

| Part | What it gives you | Time |
|---|---|---|
| 1 | The whole project in plain words (the story you tell) | 10 min |
| 2 | **The 25%**: exactly where it starts and ends, step by step, with the file and the proof | 20 min |
| 3 | **Every abbreviation** expanded and explained (SGLT2i, eGFR, AIPW, HC3, RRF, TOTP, CSRF …) | 20 min |
| 4 | The implementation in minute detail: every folder, every file, every number | 45 min |
| 5 | The numbers card: every figure we quote, with its source file | 5 min |
| 6 | **118 panel questions with answers**, including the hard ones | 60 min |
| 7 | How to learn it fast with NotebookLM and Claude (audio/video overviews, quizzes, mock viva) | 10 min |
| 8 | On the day: checklist, rescue lines, what never to say | 5 min |

The deck is `Intelligent_Diabetes_CDSS_MidSem_updated.pptx` (35 slides + 5 backup). The slide-by-slide script
is `TEAM_BRIEFING.md`. The interactive explainer page (with narration and a quiz) and the narrated video
`DiaCausal_explainer.mp4` teach the same story visually.

---

## Part 1 · The whole project in plain words

### 1.1 The problem, told as a story
A 58-year-old man in Pune has **type 2 diabetes**. He already takes **metformin**, the usual first medicine, but
his **HbA1c** (his average blood sugar over the last 2–3 months) is still 8.4%, above the usual target of about
7%. His doctor must **add a second medicine**. Three common choices are:

| Option | Short name | Example molecule | What it does, in one line |
|---|---|---|---|
| Sodium–glucose co-transporter-2 inhibitor | **SGLT2i** | dapagliflozin | Makes the kidneys pass extra sugar out in the urine; usually some weight loss |
| Dipeptidyl peptidase-4 inhibitor | **DPP-4i** | sitagliptin | Helps the body's own insulin-boosting hormones last longer; weight-neutral |
| Sulfonylurea | **SU** | glimepiride | Squeezes more insulin out of the pancreas; cheap; can cause low sugar and weight gain |

**Which one will lower *this* patient's HbA1c the most, safely?** That is the question DiaCausal answers.

### 1.2 Why this is hard: confounding
You might think: "look at old hospital records, see which drug lowered HbA1c most on average". That gives the
**wrong answer**, because doctors do not hand out drugs at random. For example, patients with very high HbA1c
are more often given an SGLT2i, and very high HbA1c also falls more over 6 months *whatever* drug is given. So
the raw average mixes up **the drug's effect** with **who got the drug**. This mix-up is called
**confounding** (more precisely, *confounding by indication*).

On our synthetic data the true difference between SGLT2i and DPP-4i is **−0.211** HbA1c points. The naive
comparison says −0.370: it is off by **−0.159**, and its 95% interval **never** contains the truth. Our causal
methods (IPW, matching, AIPW) bring the error down to about **0.002**. That one comparison is the heart of the
project.

### 1.3 What DiaCausal does, in four steps
1. **Safety first.** Ten cited rules from drug labels (for example "SGLT2i not for HbA1c lowering when eGFR is
   below 45") remove or flag unsafe options **before any number is calculated**.
2. **A fair estimate for this patient.** For each remaining drug: the expected **6-month HbA1c change with a 95%
   range**, corrected for confounding. If too few similar patients got that drug (propensity below 0.05), it
   says **"insufficient evidence"** instead of guessing.
3. **More context.** Weight change and low-sugar (hypoglycaemia) risk, each with a 95% range; cost (shown as
   "price unavailable" until prices are confirmed); and **cited evidence** quoted from WHO and FDA documents
   (the RAG part).
4. **The doctor decides.** The system never recommends a dose and never makes the decision.

### 1.4 Why synthetic data, and why that is honest
To grade a causal method you must know the **true** answer, and in real records you never see what *would*
have happened with the other drug. So, like published causal-inference benchmarks (ACIC challenges, IHDP), we
generate **5,000 synthetic, India-calibrated patients** whose true drug effects we planted. Then we measure how
close each method gets. A **real Indian survey (NMB-2017)** is used only to check our synthetic patients look
realistic. We never claim real-world drug effects; that needs hospital data with ethics approval (future work).

### 1.5 What exists today (four pieces of software)
| Piece | What it is | Where |
|---|---|---|
| **Chat app** | The secure front door: FastAPI server + React page; sign-in with password + CAPTCHA + authenticator code; guards; patient panel; clinical guardrails; voice; Docker. Since 29 Sep its six-stage pipeline runs the causal engine and the evidence search. | `backend/`, `frontend/` |
| **Causal engine** | Python library: synthetic cohort, safety rules, propensity/overlap, IPW/matching/AIPW, DR-learner, benchmark, refutation, E-values; Streamlit demo and an API | `diacausal_engine/`, `data/`, `demo/` |
| **Evidence search (RAG)** | Licence gate → WHO 2018 + 7 FDA notices → hybrid BM25 + TF-IDF search → quoted, cited answers; abstains or refuses doses | `diacausal_rag/`, `RAG/` |
| **Website** | Phone-first PWA at diacausal.netlify.app: the same engine and search in the browser, accounts with admin approval and TOTP | `web/`, `supabase/` |

### 1.6 Where we are
- The Project Interaction Sheet asked for **25% by 23 September**: our guide **signed** it.
- **40% by 7 October**: met on **28 September** (Section 2: evidence search, secondary outcomes, website).
- **60% by 14 October**: met on **29 September** (Section 3: engine + evidence inside the chat app).
- **80% by 21 October**: our target is **3 October** (Section 4a: better search model).
- **100% implementation**: our target is **6 October** (Section 4b: real-data adapter, evaluation tools).
- Whole project (implementation + evaluation + report/paper), weighted: **about 75%** (Part 5 shows the sum).

---

## Part 2 · The 25%: exactly where it starts and ends

### 2.1 What the 25% is
The interaction sheet splits implementation into **four sections**. **Section 1 is the 25%**, signed by our guide
on **23 September** (week 7: "coding details; 25% done"). It has two halves:

- **Half A: the chat app's front door.** Everything a doctor touches before any medicine is compared.
- **Half B: the causal engine core.** Everything needed to turn *one patient* into *an honest estimate per drug*.

**The 25% in one sentence (learn this by heart):**
> "At 25%, one patient goes in, unsafe drugs come out, and each remaining drug gets its expected 6-month HbA1c
> change with a 95% range, or 'insufficient evidence'. That runs in the Streamlit demo and the API, behind a
> secure chat app front door."

Deck slide **23** ("Implementation – Exactly What the 25% Covers") shows it as six rows.

### 2.2 The six steps of the 25%, in detail

#### Step 1 · Chat app front door (Half A) · `backend/app/`, `frontend/src/`
**Plain words:** a doctor signs in safely, types a question, fills in the patient's details, and the system
refuses anything unsafe or off-topic before doing any work.

| Part | What happens | File(s) | Key numbers |
|---|---|---|---|
| Sign-in step 1 | User ID + password + a 6-digit **CAPTCHA** (picture, with an audio option) | `app/auth/routes.py`, `captcha.py`, `passwords.py` | Password ≥ 12 characters; CAPTCHA works once and expires in 5 min |
| Password storage | Stored only as an **Argon2id** hash (a slow, salted, one-way scramble) | `passwords.py` | Common passwords refused |
| Sign-in step 2 | 6-digit code from an **authenticator app** (TOTP) | `mfa.py` | Code changes every 30 s; MFA secret encrypted at rest (Fernet) |
| Lockout | Too many wrong tries → the account locks | `throttle.py` | 5 failures → 15 min lock; growing delays; per-IP limit |
| Session | Secure cookie `__Host-diacausal_session` + a **CSRF** token header on every change | `sessions.py` | Idle sign-out 15 min (warning at 2 min left); max 8 h |
| Guards (browser + server) | Block identifiers (Aadhaar, ABHA, Indian mobile, PAN, e-mail), abuse, out-of-scope topics (type 1, pregnancy, under 18, DKA/HHS, starting insulin) and emergencies (e.g. very low sugar) | `frontend/src/lib/guards.ts`, `backend/app/pipeline/backend_guard.py`, shared list `shared/guard_rules/rules.v1.json` | The matched word is **never** shown or logged |
| Patient panel | Structured fields, never parsed from the sentence: age, sex, diabetes duration, HbA1c, eGFR, BMI, ASCVD, CKD, heart failure, past DKA, recurrent genital/urinary infection, past pancreatitis, past hypoglycaemia, budget | `frontend/src/features/patient/`, `PatientPart` in `backend/app/schemas.py` | Plausibility ranges in `app/patient_ranges.py` = `ranges.ts` (a test compares) |
| Clinical guardrails | YAML rules G00–G16: "abstain", "do not use", "check first", "info" per option | `app/clinical/guardrails.v1.yaml`, `rules.py`, `pipeline/clinical_guardrails.py` | e.g. eGFR < 30 → whole question abstains (metformin contraindicated) |
| Contract + tracing | One strict JSON shape; unknown fields → HTTP 422; every log line starts with the message's 8-hex **trace ID**; message text is never logged | `schemas.py`, `errors.py`, `tracing.py` | Text ≤ 8,000 characters; ≤ 20 parts |

**Proof:** `python3 scripts/check_all.py` → 43 checks (401 backend tests + 246 frontend tests + build + lint +
33 live checks + vignettes + a real-browser check).

#### Step 2 · Synthetic cohort (Half B) · `diacausal_engine/cohort.py`, `data/params.yaml`
**Plain words:** we create 5,000 realistic but made-up Indian patients, decide which drug each "got" the way
real doctors tend to decide, and record what happened, *and* what would have happened under the other drugs.

How it is generated (5 steps):
1. **Patient details:** age (mean 55, SD 10, 30–85), 45% female, diabetes duration (gamma, mean 7 y), HbA1c
   (≥ 7.0%, mean about 8.6%), eGFR (82 at age 55, falling 0.8 per year of age, ≥ 30), BMI (mean 26.5), and
   history flags (ASCVD 15%, heart failure 5%, past hypoglycaemia 8%, past DKA 1%, past pancreatitis 1.5%, low
   income 40%). CKD = eGFR < 60 (KDIGO).
2. **Who gets which drug:** a multinomial logit "doctor" model. Higher HbA1c → more SGLT2i; lower eGFR → less
   SGLT2i; higher BMI, ASCVD, heart failure → more SGLT2i; older age and past hypoglycaemia → less SU; low
   income → more SU (cheapest). This **deliberately builds in confounding**.
3. **The true effect of each drug for each patient:** e.g. SGLT2i base −0.75, stronger at higher HbA1c and
   weaker at lower eGFR; DPP-4i base −0.56; SU base −0.80, weaker with longer diabetes. Sizes are
   ASSUMED-DIRECTIONAL from meta-analyses (Tsapas 2020, Palmer 2016) and treatment-selection studies (Dennis
   2022, TriMaster 2023).
4. **Outcome:** 6-month HbA1c change = drift (−0.15) + regression to the mean (−0.20 per % above 8.5) + the
   drug's effect + noise (SD 0.60). Secondary outcomes (weight in kg, any hypoglycaemia yes/no) come from their
   own random stream.
5. **Hide the truth:** `observed_view()` keeps only what a real hospital would see (details, the drug given,
   the outcome under that drug). The hidden columns (outcomes under the other drugs, true effects) are kept
   aside for grading.

**Every number** has a `source` and a `status` (CITED / ASSUMED-DIRECTIONAL / TEAM-SET); `config.py` refuses
to start otherwise. Count: **117 numbers = 9 CITED, 15 ASSUMED-DIRECTIONAL, 93 TEAM-SET** (we say this
openly).

#### Step 3 · Safety rules first (Half B) · `data/rules.csv`, `diacausal_engine/guardrails.py`
**Plain words:** before any maths, remove the drugs that are unsafe for this patient, and flag the risky ones,
each with its source.

| Rule | Drug | If | Action | Source (status) |
|---|---|---|---|---|
| R01 | SGLT2i | eGFR < 45 | **Exclude** | FARXIGA label, Sec 1 (verified) |
| R02 | SGLT2i | type 1 diabetes | **Exclude** | FARXIGA label (verified) |
| R03 | SGLT2i | past ketoacidosis | Caution | FARXIGA 5.1 (to confirm) |
| R04 | DPP-4i | eGFR < 45 | Caution (dose adjustment; we never show doses) | JANUVIA 2.2 (verified) |
| R05 | DPP-4i | past pancreatitis | Caution | JANUVIA 1, 5.1 (verified) |
| R06 | DPP-4i | heart failure | Caution | JANUVIA 5.2 (verified) |
| R07 | SU | past hypoglycaemia | Caution | Glimepiride 5.1 (verified) |
| R08 | SU | age ≥ 65 | Caution (cut-off team-set) | Glimepiride 2.1, 8.5 |
| R09 | SU | eGFR < 60 | Caution (cut-off team-set) | Glimepiride 2.1, 8.6 |
| R10 | SU | eGFR < 30 | **Exclude** (team-set, pending review) | Team rule |

**Rule:** an excluded option is **never estimated** (a test checks this on 155 patients). Thresholds live
**only** in `rules.csv`; a test scans the code for hard-coded thresholds.

#### Step 4 · Propensity + overlap (Half B) · `diacausal_engine/propensity.py`
**Plain words:** for a patient like this, how likely was each drug? If almost no similar patient got a drug,
we cannot compare fairly, so we refuse.

- **Propensity score** = probability of receiving each drug given the patient's details. Model: multinomial
  **logistic regression** (StandardScaler + LogisticRegression, three probabilities adding to 1).
- **Cross-fitting:** 5 folds; each patient's score comes from a model trained on the other 4 folds, so no
  patient is scored by a model that has seen them.
- **Overlap rule:** if this patient's probability for a drug is **below 0.05** → **"insufficient evidence"**,
  no number. (For weighting, probabilities are clipped at 0.01 so no weight exceeds 100.)
- **Balance check:** after weighting, the largest **SMD** across all details falls from **0.70 to 0.08**
  (below the 0.1 rule of thumb, Austin 2009).

#### Step 5 · Average effects (Half B) · `diacausal_engine/estimators.py`
**Plain words:** show that the naive comparison is biased and that our three causal methods remove the bias.

| Method | Idea in one line |
|---|---|
| **Naive** | Just compare the average outcomes of each drug group (biased by confounding) |
| **IPW** | Weight each patient by 1 / (their chance of getting the drug they got), so each group looks like the whole cohort |
| **Matching** | Pair each patient with the most similar patient (by propensity) who got the other drug; 95% interval by 100 bootstrap resamples |
| **AIPW** | Outcome model's prediction + an IPW-weighted correction of its error; right if **either** model is right ("doubly robust") |

Outcome model for AIPW: HistGradientBoostingRegressor (200 trees, depth 3, learning rate 0.05), cross-fitted.

#### Step 6 · This patient's estimate (Half B) · `diacausal_engine/estimators.py`, `fitting.py`, `recommend.py`
**Plain words:** turn the average into a personal estimate for *this* patient, with an honest range.

- **DR-learner:** take each training patient's AIPW score (a "pseudo-outcome": a noisy but unbiased guess of
  their personal effect) and fit a **linear regression (OLS)** of those scores on patient details.
- **HC3 robust standard errors** give each patient's **95% interval** (robust even when noise differs between
  patients).
- **Output (`recommend.py`):** for each of the three options: *excluded* (with rule and source), or
  *insufficient evidence* (with the reason), or *estimate* (value, 95% range, propensity), plus cautions,
  assumptions, versions, and the intended-use sentence. This is the **Causal Output** (`schemas.CausalOutput`).
- **Where it runs at 25%:** the Streamlit demo (`demo/streamlit_app.py`) and the API
  `POST /api/v1/recommend` (`diacausal_engine/api.py`, port 8001).

### 2.3 Where the 25% ends (and what is beyond it)
```
 ┌──────────────────────── THE 25% (Section 1, signed 23 Sep) ─────────────────────────┐
 │ Chat app front door: sign-in (password + CAPTCHA + TOTP), guards, patient panel,    │
 │ clinical guardrails, trace-ID logging                                                │
 │ Causal engine core: synthetic cohort → safety rules → propensity + overlap →         │
 │ IPW / matching / AIPW → DR-learner: 6-month HbA1c change with a 95% range            │
 │ (or "insufficient evidence"); Streamlit demo + API                                   │
 └───────────────────────────────────────────────────────────────────────────────────────┘
   ↓ beyond the 25%
 Section 2 (met 28 Sep = 40%): benchmark (20 cohorts) + 9 refutation checks + E-values ·
   weight and low-sugar outcomes · "too uncertain" abstention · evidence search (RAG) with a
   60-question test · website with accounts
 Section 3 (met 29 Sep = 60%): causal engine + RAG + explanation inside the chat app (all 6 stages)
 Section 4 (targets 3 and 6 Oct): medical embeddings + reranker · real-data adapter · evaluation tools
```

### 2.4 How to present the 25% (a 90-second script for slide 23)
> "The interaction sheet asked for 25% by 23 September, and our guide signed it. This slide shows exactly what
> that 25% is. It has two halves. First, the chat app's front door: sign-in with a password, a CAPTCHA and an
> authenticator code; guards that block identifiers and off-topic questions; the patient panel; and clinical
> guardrails. Second, the causal engine core: we generate 5,000 synthetic Indian patients with known true
> effects; safety rules from drug labels run first and remove unsafe drugs; a propensity model checks that
> similar patients received each drug, and below 0.05 we say 'insufficient evidence'; IPW, matching and AIPW
> remove the confounding bias; and the DR-learner gives this patient's 6-month HbA1c change with a 95% range.
> So at 25%, one patient goes in, unsafe drugs come out, and each remaining drug gets an honest estimate. Everything
> after this slide, the benchmark, the evidence search, the website and the joined chat app, goes beyond the 25%."

### 2.5 If the panel says "show us the 25% working"
1. **Fastest:** the website, preset 2 (Try it tab): SGLT2i red "excluded, R01"; DPP-4i and SU with 95% ranges.
2. **Streamlit:** `.venv/bin/streamlit run demo/streamlit_app.py` → pick a preset.
3. **API:** `.venv/bin/uvicorn diacausal_engine.api:app --port 8001` → open `http://localhost:8001/docs` →
   `POST /api/v1/recommend` → "Try it out".
4. **Chat app:** sign in → fill the patient panel (use the example) → ask "What should I add to metformin?" →
   the reply lists six stages, the estimates with 95% ranges, and cited evidence.
5. **Tests:** `.venv/bin/python -m pytest tests/engine -q` (150 tests, about 3 min).

### 2.6 Why "25% signed" but "about 75% now" (they will ask)
- The sheet's percentages are **minimum checkpoints by date**: 25% (23 Sep), 40% (7 Oct), 60% (14 Oct),
  80% (21 Oct), 100% (December).
- We **claim** only the checkpoints we can prove: 25% signed; 40% met 28 Sep; 60% met 29 Sep. We do **not**
  claim 80% yet (that needs Section 4a).
- The "about 75%" is our **weighted estimate of the whole project** (software + clinician evaluation + report
  and paper), each weight with evidence (Part 5). It is an estimate, and we say so.

---

## Part 3 · Every abbreviation, expanded and explained

Grouped by topic. "Where" says where it appears in DiaCausal.

### 3.1 Medicine and diabetes
| Short form | Full form | Plain meaning | Where in DiaCausal |
|---|---|---|---|
| **T2D / T2DM** | Type 2 diabetes (mellitus) | The body does not use insulin well; blood sugar stays high. Most adult diabetes | The only disease in scope |
| **T1D** | Type 1 diabetes | The body makes no insulin; needs insulin from the start | Out of scope (guard); rule R02 |
| **HbA1c** | Haemoglobin A1c (glycated haemoglobin) | % of haemoglobin with sugar attached = average blood sugar over 2–3 months. Target usually about 7% | The main outcome: 6-month change in percentage points |
| **pp / points** | Percentage points | A change from 8.4% to 7.9% is −0.5 points (not −0.5%) | All HbA1c changes |
| **eGFR** | Estimated glomerular filtration rate | How well the kidneys filter, in mL/min/1.73 m² (normal ≈ 90+; < 60 = reduced; < 30 = severe) | Safety rules R01, R04, R09, R10; guardrails G00–G12 |
| **mL/min/1.73 m²** | Millilitres per minute per 1.73 m² body surface | The unit of eGFR, scaled to an average body size | Units rule |
| **BMI** | Body mass index | Weight (kg) ÷ height (m)². **Asian-Indian cut-offs:** overweight ≥ 23, obese ≥ 25 (Misra 2009) | Patient panel; cohort; display |
| **CKD** | Chronic kidney disease | Long-term kidney damage; here eGFR < 60 (KDIGO) | Cohort flag; guardrail G15 |
| **ASCVD** | Atherosclerotic cardiovascular disease | Heart attack, stroke, blocked arteries | Panel; doctors prefer SGLT2i (G16 info) |
| **HF** | Heart failure | The heart pumps poorly | Rule R06; G07; G16 |
| **DKA** | Diabetic ketoacidosis | A dangerous acid build-up; an emergency. SGLT2i carry a warning | R03, G03; DKA questions are out of scope |
| **HHS** | Hyperosmolar hyperglycaemic state | Extremely high sugar with dehydration; an emergency | Out-of-scope guard |
| **Hypo** | Hypoglycaemia | Blood sugar too low (shaky, sweaty, confused; can be dangerous) | Secondary outcome; R07; G10–G11 |
| **SGLT2i** | Sodium–glucose co-transporter-2 inhibitor | Kidneys pass sugar in urine; weight loss; e.g. dapagliflozin, empagliflozin | Option 1 |
| **DPP-4i** | Dipeptidyl peptidase-4 inhibitor | Prolongs gut hormones (incretins) that raise insulin after meals; e.g. sitagliptin | Option 2 |
| **SU** | Sulfonylurea | Makes the pancreas release more insulin; cheap; hypo and weight gain; e.g. glimepiride, gliclazide | Option 3 |
| **GLP-1 RA** | Glucagon-like peptide-1 receptor agonist | Injectable (or oral) drugs for sugar and weight; e.g. semaglutide | Not in scope (future) |
| **RCT** | Randomised controlled trial | Patients randomly assigned to drugs: the gold standard, no confounding | Source of our effect sizes; real-data validation |
| **CVOT** | Cardiovascular outcome trial | RCT testing heart safety of a diabetes drug | Background for G16 |
| **SMBG** | Self-monitoring of blood glucose | Finger-prick tests at home | Not used |
| **EHR / EMR** | Electronic health / medical record | The hospital's digital patient records | Future real-data step |

### 3.2 Guidelines, regulators, data sources (India and world)
| Short form | Full form | What it is | Where |
|---|---|---|---|
| **WHO** | World Health Organization | UN health agency; its 2018 guideline on second- and third-line diabetes medicines is in our RAG | RAG source S01 |
| **FDA** | US Food and Drug Administration | US drug regulator; drug labels and safety communications | rules.csv, guardrails, RAG (7 notices) |
| **DSC** | Drug Safety Communication | An FDA public safety notice | RAG sources |
| **PI / USPI** | (US) prescribing information | The official drug label | Rule sources |
| **KDIGO** | Kidney Disease: Improving Global Outcomes | International kidney guideline group (CKD definition; SGLT2i for kidney protection) | CKD rule; R01 note |
| **ADA / EASD** | American Diabetes Association / European Association for the Study of Diabetes | Joint diabetes treatment guidance | Background |
| **RSSDI** | Research Society for the Study of Diabetes in India | Indian diabetes guidelines; licence not yet cleared, so not in our RAG | Future source |
| **ICMR** | Indian Council of Medical Research | India's medical research body | ICMR-INDIAB |
| **ICMR-INDIAB** | ICMR–India Diabetes study | National survey of diabetes prevalence (Lancet D&E 2023) | params source |
| **LASI** | Longitudinal Ageing Study in India | Survey of 45+ adults with biomarkers incl. HbA1c; free request form | Backup slide 37 |
| **NFHS-5** | National Family Health Survey, round 5 | India's DHS survey; glucose, self-reported diabetes | Backup slide 37 |
| **DHS** | Demographic and Health Surveys | International survey programme that hosts NFHS data | Backup |
| **CARRS** | Centre for cArdiometabolic Risk Reduction in South Asia | Cohort in Delhi, Chennai, Karachi; data on request | Backup |
| **NMB-2017** | The 2017 nationwide Indian survey of adults at high risk of type 2 diabetes (Nagarathna et al., Diabetes Res Clin Pract 2020; Mendeley Data, CC0) | 7,496 real adults (1,986 with diabetes): age, sex, BMI, HbA1c; **no drug, no follow-up**. We use it **only** as a realism check | `data/reference/nmb2017.csv`, slide 21 |
| **CC0 / CC BY-NC-SA** | Creative Commons licences (public domain / attribution, non-commercial, share-alike) | Licences of NMB-2017 and WHO 2018 | Licence gate |
| **CDSCO** | Central Drugs Standard Control Organisation | India's drug and medical-device regulator | Future device question |
| **SaMD** | Software as a Medical Device | Software that is itself a medical device | Why we say "not a medical device" |
| **MDR 2017** | Medical Devices Rules, 2017 (India) | India's device regulation | Future |
| **IEC** | Institutional Ethics Committee | Approves research on patients' data | Real-data step |
| **DPDP Act** | Digital Personal Data Protection Act, 2023 | India's data-privacy law | Real-data step; "patient values never leave the device" |
| **ABHA** | Ayushman Bharat Health Account | India's 14-digit health ID | Blocked by the identifier guard |
| **PAN** | Permanent Account Number | Indian tax ID | Blocked by the identifier guard |
| **INR** | Indian rupee | Cost unit (INR/month) | Cost step |
| **Jan Aushadhi** | Pradhan Mantri Bhartiya Janaushadhi Pariyojana | Government generic-medicine stores; the planned price source | "price unavailable" until confirmed |

### 3.3 Causal inference and statistics
| Short form | Full form | Plain meaning | Where |
|---|---|---|---|
| **CI** | Confidence interval | A range that, over many repeats, contains the truth 95% of the time | Every estimate |
| **SE** | Standard error | How much an estimate would wobble across repeats; 95% CI ≈ estimate ± 1.96 × SE | All estimators |
| **SD** | Standard deviation | Spread of values around the mean | Cohort parameters |
| **DAG** | Directed acyclic graph | The causal diagram: arrows = "causes"; tells us what to adjust for | `dag.py`, params `dag:` |
| **Confounder** | — | Affects both the drug choice and the outcome (e.g. HbA1c, eGFR, duration) | Adjusted for |
| **Mediator** | — | Caused by the drug, on the way to the outcome (e.g. weight change) | **Never** adjusted for |
| **ATE** | Average treatment effect | Average difference in outcome if everyone got drug A vs drug B | Benchmark (truth −0.211 for SGLT2i vs DPP-4i) |
| **CATE** | Conditional average treatment effect | The effect for patients with given details: the "personal" effect | DR-learner output |
| **ITE** | Individual treatment effect | One person's true effect; never observable in real data | Known only in synthetic data |
| **PS / propensity** | Propensity score | Probability of getting each drug given the patient's details | `propensity.py` |
| **Overlap / positivity** | — | Every kind of patient has some chance of each drug; we require ≥ 0.05 | Abstention rule |
| **IPW** | Inverse probability weighting | Weight = 1 ÷ propensity of the drug received; re-balances groups | `estimators.ipw` |
| **PSM** | Propensity score matching | Pair similar patients who got different drugs | `estimators.matching` |
| **AIPW** | Augmented inverse probability weighting | Outcome model + IPW correction; **doubly robust** | `estimators.aipw` |
| **DR** | Doubly robust | Correct if either the propensity model or the outcome model is correct | AIPW, DR-learner |
| **DR-learner** | Doubly robust learner (Kennedy 2023) | Regress AIPW pseudo-outcomes on patient details → personal effects | `DRLearner` |
| **T-learner / S-learner** | Two-model / single-model learner | Simple baselines: separate outcome models per drug, or one model with the drug as a feature | Benchmark baselines |
| **OLS** | Ordinary least squares | Standard straight-line regression | DR-learner second stage |
| **HC3** | Heteroskedasticity-consistent (type 3) standard errors | Robust SEs that stay honest when noise differs between patients | DR-learner 95% intervals |
| **Heteroskedasticity** | — | Noise size differs across patients | Why HC3 |
| **Cross-fitting** | — | Split into K folds; predict each fold with models trained on the others (K = 5) | Propensity and outcome models |
| **HGB** | HistGradientBoostingRegressor | A fast tree-ensemble model from scikit-learn | AIPW outcome model |
| **SMD** | Standardised mean difference | Difference in means ÷ pooled SD; < 0.1 = balanced | Balance check 0.70 → 0.08 |
| **RMSE** | Root mean squared error | Typical size of an error (penalises big misses) | Benchmark |
| **Bias** | — | Average error (estimate − truth) | Benchmark: naive −0.159, AIPW +0.002 |
| **Coverage** | — | Share of 95% intervals that contain the truth (target ≈ 0.95) | Benchmark |
| **PEHE** | Precision in estimating heterogeneous effects | RMSE of personal effects vs the true personal effects | DR-learner 0.105–0.117 |
| **Regret** | Policy regret | How much HbA1c lowering is lost by choosing the model's best drug instead of the truly best drug | DR-learner 0.011 points |
| **E-value** | — (VanderWeele & Ding 2017) | How strong a hidden confounder would need to be (as a risk ratio with both drug and outcome) to explain the effect away | `evalues.csv` (1.57–2.15) |
| **Refutation** | — | Stress tests: fake treatment should give zero; adding a random confounder or using 80% of data should not move the estimate | `refute.py`, 9 of 9 pass |
| **Placebo test** | — | Shuffle the treatment labels; the "effect" must vanish | 20 shuffles each |
| **RTM** | Regression to the mean | Very high values tend to fall on re-measurement anyway | Built into the cohort outcome |
| **SUTVA** | Stable unit treatment value assumption | One patient's drug does not affect another's outcome | Stated assumption |
| **Logit** | Log-odds | log(p / (1 − p)); used in the drug-assignment and hypo models | Cohort generator |
| **Seed** | Random seed | A fixed number so results are repeatable | 2026 (reference cohort), 7 (benchmark) |
| **IHDP / ACIC** | Infant Health and Development Program / Atlantic Causal Inference Conference data challenges | Standard semi-synthetic causal benchmarks | Why synthetic is valid |

### 3.4 Evidence search and AI (RAG, LLM)
| Short form | Full form | Plain meaning | Where |
|---|---|---|---|
| **AI / ML** | Artificial intelligence / machine learning | Computers learning patterns from data | Project domain |
| **RAG** | Retrieval-augmented generation | First **retrieve** passages from trusted documents, then write an answer **only** from them, with citations | `diacausal_rag/` |
| **LLM** | Large language model | A text-generating AI (e.g. Gemini, Llama); optional here, always checked | `explain.py` |
| **BM25** | Best Matching 25 (Okapi BM25) | Classic keyword ranking: rewards rare words that appear often in a passage (k1 = 1.5, b = 0.75) | `retrieve.py` |
| **TF-IDF** | Term frequency–inverse document frequency | Word-weight vectors compared by cosine similarity | `retrieve.py` |
| **RRF** | Reciprocal rank fusion | Combine two rankings: score = Σ 1 / (60 + rank) | Hybrid search (k = 60, Cormack 2009) |
| **Chunk / passage** | — | A piece of a document (about 400 words, never crossing a section) | 78 passages from 8 documents |
| **Top-k** | — | Keep the best k passages (k = 5) | Retrieval |
| **Recall@5** | — | Share of questions whose correct source is in the top 5 | 0.933 |
| **Abstention** | — | Saying "insufficient evidence" instead of answering | 0.800 on out-of-scope questions |
| **Citation precision** | — | Share of cited sentences really found in the cited passage | 1.000 |
| **Gold set** | — | Hand-made test questions with known right sources (`eval/rag_gold.csv`, 60 questions) | Evaluation |
| **Embedding** | — | A vector that captures meaning; a *medical* embedding model is Section 4a | Future |
| **Reranker** | — | A second model that re-orders the top passages more carefully | Section 4a |
| **Hallucination** | — | An AI stating something not in its sources | Prevented by the citation checker |
| **Gemini** | Google's LLM (free tier, online) | Optional rewriter, via a Supabase Edge Function; key never in the repo | Website button |
| **Ollama** | Local LLM runner | Offline option (llama3.2:3b) | `explain.py` |
| **RAGAS** | RAG assessment framework | Measures faithfulness etc.; planned for LLM modes | Report Table 5.x |
| **NLP** | Natural language processing | Computers handling text | Background |
| **PDF** | Portable Document Format | Source documents' format | `pdf_text.py` |

### 3.5 Software, web and security
| Short form | Full form | Plain meaning | Where |
|---|---|---|---|
| **CDSS** | Clinical decision support system | Software that helps (not replaces) a clinician's decision | Project title |
| **UI / UX** | User interface / user experience | What the user sees and how it feels | `frontend/`, `web/` |
| **API** | Application programming interface | A way for programs to talk to each other | `/api/v1/chat`, `/api/v1/recommend` |
| **REST** | Representational state transfer | A style of web API using HTTP verbs (GET, POST) and URLs | Our APIs |
| **HTTP / HTTPS** | Hypertext transfer protocol (secure) | The web's protocol; HTTPS is encrypted (TLS) | Caddy adds HTTPS |
| **TLS** | Transport Layer Security | The encryption under HTTPS | Deployment |
| **JSON** | JavaScript Object Notation | A text format for structured data `{"key": "value"}` | Every API message |
| **YAML** | "YAML Ain't Markup Language" | Human-readable config format | `params.yaml`, `guardrails.v1.yaml` |
| **CSV** | Comma-separated values | A simple table file | `rules.csv`, `prices.csv`, results |
| **FastAPI** | — | A Python web framework (fast, typed) | `backend/`, engine API |
| **Pydantic** | — | Python data validation from type hints (v2) | `schemas.py` (`extra="forbid"`) |
| **Uvicorn** | — | The server program that runs FastAPI | Run commands |
| **React / Vite / TS** | React UI library / Vite build tool / TypeScript | The chat app's page, its dev server/bundler, and typed JavaScript | `frontend/` |
| **Tailwind / shadcn/ui** | — | CSS utility framework / copy-in UI components | Chat app styling |
| **Streamlit** | — | Python library for quick data apps | `demo/streamlit_app.py` |
| **HTTP 422 / 401 / 403 / 423 / 429** | Status codes | 422 = invalid input; 401 = not signed in; 403 = forbidden (e.g. no CSRF token); 423 = locked; 429 = too many attempts | Chat app errors |
| **CAPTCHA** | Completely Automated Public Turing test to tell Computers and Humans Apart | The distorted-digits image (and audio) that stops bots | Sign-in |
| **MFA / 2FA** | Multi-factor / two-factor authentication | Something you know (password) + something you have (phone) | Sign-in |
| **TOTP** | Time-based one-time password (RFC 6238) | 6-digit code from an authenticator app, new every 30 s | Sign-in, website accounts |
| **Argon2id** | — | Winner of the Password Hashing Competition; slow and memory-hard, so guessing is expensive | Password storage |
| **Hash / salt** | — | One-way scramble of a password; a random salt makes equal passwords look different | `passwords.py` |
| **Fernet** | — | Symmetric encryption (from the `cryptography` library) | MFA secrets at rest |
| **CSRF** | Cross-site request forgery | A trick where another site makes your browser act for you; blocked by a secret token header | `X-CSRF-Token` |
| **XSS** | Cross-site scripting | Injecting a script into a page; blocked by the CSP | Website, chat app |
| **CSP** | Content Security Policy | Browser rule listing what scripts/styles may run; ours forbids inline scripts | `netlify.toml`, `web.py` |
| **CORS** | Cross-origin resource sharing | Browser rule for calling another domain; not needed (one origin) | Deployment |
| **Cookie `__Host-`** | — | A cookie prefix that forces Secure, path /, no domain: harder to steal or overwrite | Session cookie |
| **RLS** | Row-level security (PostgreSQL / Supabase) | Each database row readable only by the right user | Website accounts |
| **Supabase** | — | Hosted PostgreSQL + authentication + Edge Functions | Website accounts, Gemini function |
| **Edge Function** | — | A small server function run by Supabase | `supabase/functions/explain/` |
| **PWA** | Progressive web app | A website that installs like an app and works offline | `web/` (service worker `sw.js`) |
| **Netlify** | — | Static website host | diacausal.netlify.app |
| **Docker / Compose** | — | Packs the app into containers; Compose starts them together | `docker compose up --build -d` |
| **Caddy** | — | Web server that adds HTTPS automatically | Deployment |
| **CI** | Continuous integration | Tests run automatically on every change (GitHub Actions: Linux, macOS, Windows) | `.github/workflows/` |
| **ORM** | Object-relational mapper | Python objects ↔ database tables | SQLAlchemy 2 |
| **SQLAlchemy / Alembic** | — | Database library / its migration tool | `backend/app/db/` |
| **Trace ID** | — | An 8-hex label for one message, printed on every log line | `[efc1a658] backend_guard: passed` |
| **WCAG** | Web Content Accessibility Guidelines | Accessibility standard | Not yet measured (said honestly) |
| **OWASP ASVS** | Open Worldwide Application Security Project – Application Security Verification Standard | Security checklist we follow for sign-in | `throttle.py` |
| **NIST SP 800-63B** | US National Institute of Standards and Technology guideline on authentication | Password and lockout guidance | `throttle.py` |
| **SUS** | System Usability Scale | 10-question usability survey (score out of 100; ≥ 68 is above average) | Clinician evaluation, `eval/` |
| **κ (kappa)** | Cohen's kappa | Agreement between raters beyond chance (≥ 0.61 = substantial) | Planned vignette study |
| **LTS** | Long-term support | Node 24 LTS | Tooling |
| **Faster-whisper** | — | Local speech-to-text (Whisper "base", int8) | Voice input |

---

## Part 4 · The implementation in minute detail

Everything is in one GitHub repository, `Rhian-Roy/DiaCausal-CDSS`. Think of it as **four buildings on one
campus** that share the same rules:

```
            ┌──────────── data/ (params.yaml, rules.csv, prices.csv) ────────────┐
            │                                                                       │
  diacausal_engine/  ──►  demo/ (Streamlit) · api.py (POST /api/v1/recommend)       │
        │   └── export_web ──► web/model.json ──► web/engine.js (website)          │
        │                                                                           │
  diacausal_rag/ (RAG/sources.csv licence gate) ──► export_web ──► web/evidence.json│
        │                                                                           │
  backend/ (FastAPI chat app) ── app/engines.py loads BOTH ── six pipeline stages   │
  frontend/ (React page) ── talks only to /api/...                                  │
            └────────────── tests/, backend/tests, frontend tests, scripts/check_all ┘
```

### 4.1 The data files (the "rule book")
| File | What is inside | Why it matters |
|---|---|---|
| `data/params.yaml` | Every number the cohort and engine use (117), each with `value`, `unit`, `source`, `status`, `note` | No invented numbers: the loader refuses a bare number |
| `data/rules.csv` | R01–R10 safety rules: drug, field, operator, value, action, message, source, section, status | Thresholds live only here; a test compares them with the build guide |
| `data/prices.csv` | Monthly cost in INR, only when confirmed with a date and source | Until then: "price unavailable" |
| `data/reference/nmb2017.csv` | The real Indian survey (realism check only) | The engine never reads it (a test checks) |
| `RAG/sources.csv` | Every candidate document with its licence and a `cleared_ingest` yes/no by a named person | Only cleared sources enter the search |
| `eval/rag_gold.csv` | 60 test questions: 45 answerable, 10 out of scope, 5 dose requests | RAG evaluation |
| `eval/vignettes.v1.json` | 25 synthetic patient cases for the clinician study | Planned evaluation |

### 4.2 The causal engine, `diacausal_engine/` (Python 3.12, NumPy, pandas, scikit-learn, SciPy)
| File | What it does, in detail |
|---|---|
| `config.py` | Loads `params.yaml` into a typed `Params` object; refuses any entry without `source` and a valid `status`; computes the params hash for the audit |
| `dag.py` | The causal diagram as code: lists confounders (duration, HbA1c, eGFR), treatment predictors (age, BMI, ASCVD, HF, history flags, income), outcome predictors (sex) and the mediator (weight change, never adjusted for) |
| `cohort.py` | `generate_cohort(params, n, seed)`: the 5-step generator (Part 2, step 2); returns all columns incl. hidden potential outcomes; `observed_view()` drops the hidden ones |
| `guardrails.py` | Reads `rules.csv`; `apply(patient)` → for each option: allowed / caution (rule IDs, messages, sources) / excluded. Runs **before** any estimate |
| `propensity.py` | `crossfit_propensity()` (5 folds, StratifiedKFold) with StandardScaler + multinomial LogisticRegression; `clip()` at 0.01; `overlap_check()` at 0.05; `support_check()` flags a patient outside the cohort's range |
| `estimators.py` | `naive`, `ipw`, `matching` (1-nearest-neighbour on the logit propensity, with replacement; bootstrap 100), `crossfit_outcomes` (HistGradientBoosting per option), `aipw_scores` (the influence-function score φ), `aipw`, `pseudo_outcomes`, `DRLearner` (OLS + HC3), `t_learner`, `s_learner` |
| `fitting.py` | `fit_all()`: fits everything once on the reference cohort (seed 2026, 5,000 patients) so the demo and API answer instantly |
| `recommend.py` | One patient → **Causal Output**: validation of units and ranges → safety rules → overlap → DR-learner estimate with 95% range → width check (wider than 1.5 points → "too uncertain") → secondary outcomes (weight, hypo) → cost → assumptions → audit line (IDs, versions, rule IDs; **no patient values**) |
| `schemas.py` | Pydantic models for the Causal Output: `status` APPLICABLE / NOT_APPLICABLE, intervention, outcome, effect, confidence, assumptions, intended use |
| `metrics.py` | bias, RMSE, coverage, mean CI width, PEHE, policy regret, abstention rate, SMD |
| `benchmark.py` | 20 fresh cohorts × 5,000 patients + 2,000 test patients each → `results/benchmark_summary.csv`, `results_table.tex`, `run_info.json`, figures |
| `refute.py` | 9 refutation checks (3 contrasts × placebo / random common cause / 80% subset) and E-values → `refutation.csv`, `evalues.csv` |
| `figures.py` | Overlap, balance (love plot), recovery and calibration plots |
| `api.py` | FastAPI `POST /api/v1/recommend` and `GET /api/v1/health`; errors also carry the intended-use sentence |
| `export_web.py` | Writes `web/model.json` (coefficients, rules, settings) so the website gives identical numbers |

**The maths in plain symbols** (for the curious panel member):
- Propensity: e_a(x) = P(drug = a | details x).
- IPW mean for drug a: average of  1{got a} · Y / e_a(x).
- AIPW score for drug a: φ_a = μ_a(x) + 1{got a} · (Y − μ_a(x)) / e_a(x), where μ_a is the outcome model's
  prediction. The ATE of a vs b = mean(φ_a − φ_b); its SE from the spread of φ (influence function).
- DR-learner: regress (φ_a − φ_b) on x with OLS; the CATE for a new patient = x·β; 95% CI = ± 1.96 × HC3 SE.
- Overlap: if e_a(x) < 0.05 → abstain. Width: if CI width > 1.5 points → abstain ("too uncertain").

**Tests (`tests/engine/`, 150):** `test_a_cohort` (generator, truth, engine never reads real data) ·
`test_b_guardrails` (rules verbatim, no hard-coded thresholds, excluded never estimated) · `test_c_propensity`
(cross-fitting, overlap) · `test_d_average_effects` (IPW/matching/AIPW recover the truth) ·
`test_e_dr_learner` (coverage) · `test_f_metrics` · `test_g_benchmark` · `test_h_demo` · `test_i_api` ·
`test_j_invariants` (no doses anywhere, intended use everywhere, no patient values in logs) · `test_k_refute` ·
`test_l_secondary`.

### 4.3 The evidence search, `diacausal_rag/` (RAG)
| Step | File | What happens (with the numbers) |
|---|---|---|
| 1 Licence gate | `RAG/sources.csv`, `ingest.py` | Only rows with `cleared_ingest = yes` are read: WHO 2018 (CC BY-NC-SA 3.0 IGO) + 7 FDA Drug Safety Communications (US public domain). RSSDI, IDF and others wait for licence clearance |
| 2 Text | `pdf_text.py`, `scripts/fetch_fda_dsc.py` | PDF/HTML → clean text; sections kept |
| 3 Chunking | `ingest.py` | Sentence-aware chunks of about 400 words, never crossing a section → **78 passages from 8 documents**, each with source ID, title, section |
| 4 Dose masking | `retrieve.py` | Dose-like text (e.g. "10 mg once daily") is hidden from the index and never shown |
| 5 Search | `retrieve.py` | Two rankings: **BM25** (k1 1.5, b 0.75) and **TF-IDF** cosine; combined by **RRF** (k = 60); keep the top **5** |
| 6 Abstain | `retrieve.py` | "Insufficient evidence" if the best BM25 score < 1.0 **or** the top passages cover < 60% of the question's content words; dose questions are refused |
| 7 Explain | `explain.py` | **Template** (default, offline): up to 4 sentences quoted **verbatim** from the passages, each with [n]. Optional **Gemini** (online, via Supabase Edge Function) or **Ollama** (offline, llama3.2:3b) rewrite it |
| 8 Check | `explain.py` `check_answer()` | Every sentence must cite a retrieved passage and share ≥ 60% of its content words with it; no doses; otherwise fall back to the template |
| 9 Evaluate | `evaluate.py` | On 60 gold questions: recall@5 **0.933**, answered **0.978**, abstention **0.800**, citation precision **1.000**, dose leaks **0** |

Tests: `tests/rag/` (33). The prompt for LLMs is versioned in `prompt.v1.txt`.

### 4.4 The website, `web/` (plain JavaScript, no framework)
| File | Role |
|---|---|
| `index.html`, `styles.css`, `app.js` | Tabs: Home, **Try it** (patient form, 3 presets, colour-coded option cards, 95%-range chart, print summary), **Evidence** (question box, chips, quoted answer), **Results** (benchmark tables and figures), About |
| `engine.js` + `model.json` | The engine in the browser: mirrors `recommend.py` exactly (a parity test compares 47 cases + 55 tricky cases, and 155 patients) |
| `evidence.js` + `evidence.json`, `explain.js` | The RAG search and the quoted explanation in the browser, mirroring `retrieve.py` and `explain.py` |
| `auth.js`, `account.js` | Supabase sign-up, **admin approval**, TOTP, sign-out after 15 min idle |
| `sw.js`, `manifest.webmanifest` | PWA: installable, works offline |
| `netlify.toml` (= `vercel.json`) | Strict CSP (no inline script or style), security headers |
| `config.json` | Stays `"accounts": "off"` in the repo; the deploy copy is written by `scripts/web_config.py` (the Supabase key is never committed) |
| `supabase/migrations/*.sql` | Tables with **RLS**; `is_admin` kept private; approvals |
| `supabase/functions/explain/` | The Gemini Edge Function: receives only the question + passage IDs; the key is a Supabase secret |

**Privacy:** patient values never leave the device. Tests: `tests/web/` (19, need Node).

### 4.5 The chat app, `backend/` + `frontend/`
**Request contract** (`backend/app/schemas.py` ↔ `frontend/src/lib/contract.ts`, changed together):
```json
{"schema_version": "1.0", "client_trace_id": "efc1a658",
 "parts": [{"type": "text", "text": "What should I add to metformin?"},
           {"type": "patient", "age_years": 58, "sex": "male", "hba1c_percent": 8.4, "egfr_ml_min_1_73m2": 72, "...": "..."}]}
```
Unknown fields → 422. Text ≤ 8,000 characters (counted as characters, not bytes). 1–20 parts.

**What happens when the doctor presses Enter** (the browser console shows each line with the trace ID):
1. `[id] input passed` → `[id] ui guard passed` → `[id] medical ui guard passed` (browser guards,
   `chatFlow.ts`, `guards.ts`).
2. `POST /api/v1/chat` (needs a signed-in clinician + CSRF token).
3. The server runs **six stages** (`backend/app/pipeline/`, one file each), in this order:

| # | Stage | What it does | Can block? |
|---|---|---|---|
| 1 | `backend_guard` | Empty message, abuse, identifiers, out of scope, emergency (same rules file as the browser) | Yes |
| 2 | `clinical_guardrails` | Applies `guardrails.v1.yaml` (G00–G16) to the patient panel: may abstain for the whole question; marks each option allowed / check first / **do not use** | Yes (abstain) |
| 3 | `causal_engine` | Calls `diacausal_engine` on the allowed options only; needs age, sex, duration, HbA1c, eGFR, BMI (names any missing field); a "do not use" option gets **no number** | Skips if fields are missing |
| 4 | `rag_retrieval` | `diacausal_rag` search on the question; may say "insufficient evidence" | No |
| 5 | `llm_explanation` | Builds the reply: estimates part + evidence part (quoted, cited) + a short written answer | No |
| 6 | `output_guard` | Withholds an empty reply, a blocked word, or **anything dose-like** in the answer, evidence or passages | Yes |

After a block, later stages say "skipped" and `outcome` is "blocked" (HTTP 200).
4. The browser checks the reply's shape and trace ID (`checkOutput` in `api.ts`) → `[id] output passed` →
   shows the answer card: estimates (`EstimatesList.tsx`), cited evidence (`EvidenceList.tsx`), six stages.

**Other chat app parts:** `app/auth/` (sign-in, Part 2 step 1) · `app/db/` (SQLAlchemy 2 + Alembic migrations)
· `app/voice/` (faster-whisper "base" int8 on our own computer; ≤ 30 s; the text goes into the box and is
never sent automatically; audio never kept) · `app/tracing.py` (log format
`19:33:11 INFO    [efc1a658] backend_guard: passed`; never the message text or patient values) ·
`app/web.py` (security headers; `/docs` off in production) · `compose.yaml` + Caddy (one origin with HTTPS) ·
`scripts/create_admin.py` (first admin) · `eval/` (25 vignettes, SUS and feedback forms).

**Tests:** backend 401 (`backend/tests/`, incl. `test_engine_stages.py` for Section 3), frontend 246 (Vitest +
jsdom), and `scripts/check_all.py` (43 checks, including live servers on spare ports and a real browser).

### 4.6 How the pieces were built (the timeline in one table)
| When | What | Section |
|---|---|---|
| Jul–Aug | Topic, literature (16 papers), abstract, proposed system, requirements, design (sheet weeks 0–6) | — |
| Sep, weeks 6–7 | Chat app: skeleton → guards → sign-in (CAPTCHA, MFA) → patient panel → guardrails → voice → Docker | 1 |
| Sep, week 7 | Causal engine v0.3: cohort, rules, propensity, estimators, DR-learner; Streamlit + API | 1 (**signed 23 Sep**) |
| 24–26 Sep | Benchmark + refutation + E-values; website + accounts; weight and hypo outcomes | 2 |
| 25–28 Sep | RAG: licence gate, WHO + FDA, hybrid search, explanations, gold set, evaluation, Edge Function | 2 (**40% met 28 Sep**) |
| 28 Sep | NMB-2017 realism check; datasets doc; screenshots | — |
| 29 Sep | Engine + RAG + explanation inside the chat app; output guard for doses | 3 (**60% met 29 Sep**) |
| by 3 Oct | Medical embedding model + reranker, held-out questions | 4a (80%) |
| by 6 Oct | Real-data adapter (same columns as `observed_view`), evaluation tools | 4b (100%) |

---

## Part 5 · The numbers card (say only these)

All on **synthetic data** unless marked. Source file in brackets.

| What | Number | Source |
|---|---|---|
| True ATE, SGLT2i vs DPP-4i | −0.211 points | `results/run_info.json` |
| Naive estimate / bias / coverage | −0.370 / **−0.159** / 0% | `benchmark_summary.csv` |
| IPW / matching / AIPW bias (SGLT2i vs DPP-4i) | +0.001 / −0.002 / **+0.002** | same |
| AIPW 95% coverage (3 contrasts) | 0.90–0.95 over 20 cohorts | same |
| DR-learner per-patient coverage | 0.927–0.947 | same |
| PEHE: DR-learner vs T-learner vs naive | 0.105–0.117 vs 0.184–0.192 vs 0.169–0.214 | same |
| Policy regret: DR-learner vs naive | 0.011 vs 0.062 points | same |
| Balance (largest SMD) before → after weighting | 0.70 → 0.08 | same |
| Refutation checks passed | 9 of 9 | `refutation.csv` |
| E-values (estimate / CI) | 1.72 / 1.54 (SGLT2i–DPP-4i); 2.15 / 1.95 (SU–DPP-4i); 1.57 / 1.39 (SGLT2i–SU) | `evalues.csv` |
| Weight, SU vs DPP-4i | truth +1.50 kg, AIPW +1.48 | handbook numbers card |
| Hypoglycaemia, SU vs DPP-4i | truth +12.85 points, AIPW +12.55 | same |
| Benchmark size | 20 cohorts × 5,000 patients, 2,000 test patients each | `run_info.json` |
| Parameters by status | 117 = 9 CITED + 15 ASSUMED-DIRECTIONAL + 93 TEAM-SET | `DATASETS.md` |
| RAG | recall@5 0.933 · answered 0.978 · abstention 0.800 · citation precision 1.000 · dose leaks 0 | `rag_eval_summary.csv` |
| RAG corpus | 8 documents (WHO 2018 + 7 FDA), 78 passages | `diacausal_rag` |
| Tests | engine 150 · RAG 33 · website 19 · chat app 401 + 246 · `check_all` 43 | `docs/TESTING.md` |
| NMB-2017 (real) | 7,496 adults; 1,986 with diabetes | `data/reference/README.md` |

**Demo presets (website, reference cohort):**
| Preset | SGLT2i | DPP-4i | SU |
|---|---|---|---|
| 1 · 52 y M, HbA1c 8.4, eGFR 88, BMI 27 | −0.93 (−0.98 to −0.87) | −0.70 (−0.76 to −0.64) | −0.94 (−1.00 to −0.88) |
| 2 · 60 y F, HbA1c 8.2, eGFR 40, BMI 25.5, past pancreatitis | **Excluded** (R01) | −0.68 (−1.09 to −0.27), caution R04, R05 | −0.82 (−1.21 to −0.42), caution R09 |
| 3 · 80 y M, HbA1c 8.0, eGFR 38, past hypo, ASCVD | **Excluded** (R01) | −0.63 (−0.86 to −0.41), caution R04 | **Insufficient evidence** (propensity 0.006) |

**Progress sum:** 0.20 × 95 (chat app) + 0.25 × 90 (engine) + 0.20 × 75 (RAG) + 0.15 × 85 (joining) + 0.10 × 20
(clinician evaluation) + 0.10 × 40 (report and paper) = 19 + 22.5 + 15 + 12.75 + 2 + 4 = **75.25 ≈ 75%**.

---

## Part 6 · Panel questions with answers

How to answer: **one plain sentence first, then one technical sentence, then the proof (a number or a file).**
If you do not know: *"We have not measured that yet; here is how we would."* Never invent a number.

### A. The project and the problem
**1. What is your project in one sentence?**
A clinical decision support system that, for an adult with type 2 diabetes already on metformin, removes unsafe
add-on drugs using cited rules and estimates each remaining drug's 6-month HbA1c change with a 95% range, using
causal inference, with quoted evidence; the doctor decides.

**2. Who is the user?**
A clinician (doctor) treating adults with type 2 diabetes. Not patients. That is why sign-in needs an approved
account, and every screen says "not for unsupervised clinical use".

**3. Why only these three drugs?**
SGLT2i, DPP-4i and sulfonylureas are the three most common oral add-ons to metformin in India, with clear labels.
GLP-1 receptor agonists, pioglitazone and insulin are future scope (slide 9).

**4. Why must the patient already be on metformin?**
Metformin is first-line in WHO and ADA guidance, so "what to add second" is the common real decision. It is
contraindicated below eGFR 30, so the cohort starts at 30 and the chat app abstains below 30 (G00).

**5. Why the 6-month HbA1c change?**
HbA1c reflects about 3 months of blood sugar, and trials of these drugs report 24–26 weeks. It is the standard
glycaemic outcome, so our effect sizes can be anchored to trial meta-analyses.

**6. What is new in your project?**
Three things together in one clinician tool: cited safety rules that run first; per-patient causal estimates with
honest 95% ranges and "insufficient evidence" when data are thin; and quoted, cited evidence. It is calibrated
for India (Asian-Indian BMI cut-offs, India-calibrated cohort). Most papers we reviewed do only one of these
(slide 40: 16 papers).

**7. How is this different from asking ChatGPT?**
A general chatbot can invent facts or doses and gives no uncertainty. Our numbers come from a causal engine with
95% ranges; our text is only quoted from licence-cleared WHO/FDA passages with citations; doses are never shown;
and safety rules run before anything else.

**8. Is this really AI / ML?**
Yes, but constrained: a multinomial logistic regression (propensity), gradient-boosted trees (outcome model), a
doubly robust learner (causal ML) and information retrieval, with an optional LLM that must pass a citation
checker.

**9. Why "decision support", not "decision making"?**
Because the clinician is responsible and knows things the system does not (preferences, other illnesses, cost).
We show options, ranges and sources; we never rank a single "best" drug or give a dose.

**10. Why is this important for India?**
ICMR-INDIAB (Lancet Diabetes & Endocrinology 2023) estimated about 101 million people with diabetes in India.
Add-on choices are frequent, costs matter (sulfonylureas are cheap), and Asian-Indian patients have different BMI
cut-offs, so a tool calibrated for India is useful.

**11. What exactly does the doctor see?**
For each option: an estimate with a 95% range, or "excluded" with the rule and source, or "insufficient evidence"
with the reason; cautions; weight change and low-sugar risk with ranges; cost or "price unavailable"; cited
evidence; and the intended-use sentence.

**12. What should a doctor do with "insufficient evidence"?**
Treat it as "the data cannot answer this fairly for this patient", not as "the drug is bad". The doctor decides on
clinical judgement, as today.

### B. The 25% and our progress
**13. What exactly is your 25%?**
Section 1, signed on 23 September: the chat app's front door (sign-in with password + CAPTCHA + authenticator code,
guards, patient panel, clinical guardrails) and the causal engine core (synthetic cohort, safety rules first,
propensity + overlap, IPW/matching/AIPW, DR-learner). One patient in → unsafe drugs out → each remaining drug's
6-month HbA1c change with a 95% range, or "insufficient evidence" (slide 23).

**14. Can you show the 25% running?**
Yes: website preset 2 (SGLT2i excluded by R01; DPP-4i −0.68 (−1.09 to −0.27); SU −0.82 (−1.21 to −0.42)), or the
Streamlit demo, or the API at `/docs`, or the engine tests (150).

**15. Why is the chat app counted in the 25%?**
The sheet's Section 1 includes the application base. We built the secure front door first because joining pieces
is where projects break; it was ready before the engine joined it.

**16. What is in the 40%?**
Section 2, met 28 September: the benchmark (20 cohorts) with 9 refutation checks and E-values, weight and
low-sugar outcomes, the "too uncertain" rule, the evidence search (RAG) with its 60-question test, and the website
with accounts.

**17. What is in the 60%?**
Section 3, met 29 September: the causal engine, the evidence search and the explanation run inside the chat app,
so all six pipeline stages run; the output guard also withholds any dose-like text.

**18. What remains for 80% and 100%?**
Section 4a (target 3 October): a medical embedding model and a reranker with held-out questions. Section 4b
(target 6 October): a real-data adapter and evaluation tools. After that: clinician review, SUS study, the paper.

**19. The sheet says 60% by 14 October, but you say 75%. Which is it?**
Both, measuring different things. We claim only the sheet checkpoints we can prove: 25% signed, 40% met 28 Sep,
60% met 29 Sep. The 75% is our weighted estimate of the whole project including evaluation and paper; we do not
claim the 80% checkpoint yet.

**20. How did you calculate 75%?**
Six parts weighted by their share of the year: chat app 20% × 95, engine 25% × 90, RAG 20% × 75, joining 15% × 85,
clinician evaluation 10% × 20, report/paper 10% × 40 = 75.25. Each "done" points to tests or files (slide 32).

**21. Isn't 75% optimistic?**
It is an estimate and we say so. The parts that are not done are scored low on purpose (clinician evaluation 20%,
paper 40%), and nothing without a test or a file counts.

**22. How did you build so much so quickly?**
We fixed the rules first (build guides, safety invariants), and we used an AI coding assistant (Claude Code, listed
on slide 10) to write code under our direction. Every rule is enforced by a test, so nothing is accepted just
because it runs; we can explain every file (Part 4).

**23. Who did what?**
Answer from the presenter split and the report's status table (Chapter 5), and say honestly what *you* did. Never
claim someone else's part.

**24. What will you show at the next review?**
The 80% check: better search (medical embeddings + reranker, held-out questions), then the real-data adapter and
evaluation tools, and the clinician review materials in use.

### C. Causal inference and statistics
**25. Why causal inference and not a normal prediction model?**
A prediction model answers "what HbA1c will this patient have?"; a doctor needs "what would happen under drug A
versus drug B?". That is a causal question, and old records are confounded, so prediction models trained on them
carry the doctors' choices as bias.

**26. What is confounding? Give your example.**
A factor that affects both the drug choice and the outcome. In our cohort, higher HbA1c makes SGLT2i more likely
and also makes HbA1c fall more anyway, so the naive SGLT2i-vs-DPP-4i comparison is −0.370 instead of the true
−0.211 (bias −0.159).

**27. What is a propensity score?**
The probability that a patient with these details received each drug. We estimate it with a cross-fitted
multinomial logistic regression; the three probabilities add to 1.

**28. Why logistic regression and not a neural network for the propensity?**
It is well calibrated, interpretable and enough for about 12 details; balance after weighting (largest SMD 0.08)
shows it works. Cross-fitting guards against over-fitting.

**29. What is overlap, and why 0.05?**
Overlap (positivity) means similar patients received each drug. Below 0.05, fewer than 1 in 20 similar patients got
that drug, so weights explode and any estimate is a guess; we abstain. 0.05 is TEAM-SET and flagged for review.

**30. What is IPW, and what about extreme weights?**
Each patient is weighted by 1 / (probability of the drug they got), so each drug group resembles the whole
cohort. We clip probabilities at 0.01, so no weight exceeds 100.

**31. What is matching, and why a bootstrap?**
Each patient is paired with the most similar patient (by logit propensity) who got the other drug. Matching has no
simple formula for its standard error, so we resample 100 times to get the 95% interval (Abadie & Imbens 2008
note: approximate).

**32. What does "doubly robust" (AIPW) mean?**
AIPW starts from the outcome model's prediction and adds an IPW-weighted correction of its errors. If either the
propensity model or the outcome model is right, the estimate is unbiased: two chances to be right.

**33. Why gradient boosting for the outcome model?**
It captures non-linear effects and interactions (e.g. SGLT2i weaker at low eGFR) without us specifying them.
Cross-fitting stops its flexibility from biasing the AIPW estimate.

**34. What is cross-fitting?**
We split patients into 5 folds; each fold is predicted by models trained on the other 4. A model never grades
patients it has seen, which keeps flexible models from over-fitting the correction (the double machine learning
idea).

**35. What is the DR-learner?**
Each patient's AIPW score is a noisy but unbiased "pseudo-outcome" of their personal effect. The DR-learner fits a
regression of those scores on patient details, giving a personal effect (CATE) for a new patient (Kennedy 2023).

**36. Why a linear second stage?**
It is interpretable and gives valid confidence intervals with HC3; per-patient coverage is 0.927–0.947. A more
flexible second stage is possible later, but intervals are harder.

**37. What is HC3?**
A robust standard error that stays honest when the noise size differs between patients (heteroskedasticity). It
is the recommended small-sample version of the White/Huber "sandwich" errors.

**38. What does a 95% interval mean here?**
If we repeated the whole study many times, about 95% of such intervals would contain the true effect. On synthetic
data we can check this: that is "coverage".

**39. AIPW coverage is 0.90 for one contrast. Isn't that below 95%?**
It is over 20 cohorts, i.e. 18 of 20. With 20 repeats, 17–20 hits is normal random variation for a true 95%
interval. The naive method's coverage is 0%.

**40. ATE vs CATE?**
ATE = average effect over everyone (SGLT2i vs DPP-4i: −0.211). CATE = the effect for patients with given details;
it is what the doctor sees for *this* patient.

**41. What is PEHE?**
The typical error of personal effect estimates versus the true personal effects (known only in synthetic data).
DR-learner 0.105–0.117 versus T-learner 0.184–0.192 and naive 0.169–0.214: lower is better.

**42. What is policy regret?**
If the doctor always chose the drug with the best predicted HbA1c among the allowed ones, how much lowering is lost
versus the truly best drug: 0.011 points with the DR-learner, 0.062 with the naive approach.

**43. What are the refutation checks?**
Three stress tests for each of three contrasts (9 total), all passed: a placebo treatment (shuffled labels) must
give about zero in at least 17 of 20 shuffles; adding a random common cause and using an 80% subset must keep the
estimate within 2 SE.

**44. What is an E-value? Interpret 1.72.**
For SGLT2i vs DPP-4i, an unmeasured confounder would need to be associated with both the drug and the outcome by a
risk ratio of 1.72 (1.54 for the interval) to explain the effect away. Larger = more robust (VanderWeele & Ding
2017).

**45. What assumptions does your method need?**
No unmeasured confounding (all common causes measured), positivity (overlap), consistency (the drug is well
defined), no interference between patients (SUTVA), and a correct causal diagram. They are listed in every Causal
Output under "assumptions".

**46. Why don't you adjust for weight change?**
Weight change is caused by the drug (a mediator). Adjusting for it would remove part of the drug's real effect.
The DAG in `params.yaml` marks it "mediator: never adjusted for".

**47. What if real data have unmeasured confounding?**
No observational method can fully fix that. We report E-values, compare our real-data estimates with RCT results
(e.g. Tsapas 2020) before trusting them, and keep "insufficient evidence" and wide ranges visible.

### D. Data
**48. Why don't you use a real dataset?**
No public Indian dataset records which add-on drug each patient got together with their HbA1c 6 months later (we
checked NMB-2017, LASI, NFHS-5, CARRS, ICMR-INDIAB; slide 37). And even with real data, you can never see the
other drug's outcome, so you cannot grade a method.

**49. Why not the Pima Indians diabetes dataset?**
It is from the Akimel O'odham (Pima) community in Arizona, USA, not India, and it has no drug or follow-up data.

**50. How is the synthetic data generated?**
Five steps (Part 2, step 2): patient details → a "doctor" model assigns drugs with built-in confounding → true
effects per drug → 6-month outcome with drift, regression to the mean and noise → the truth is hidden with
`observed_view()`.

**51. How do you know the synthetic patients are realistic?**
We compared them with 1,010 real NMB-2017 adults with diabetes and HbA1c ≥ 7%: age 55.0 vs 53.5, BMI 26.4 vs 26.6,
female 45% vs 41%. HbA1c is lower and narrower in ours (8.6 vs 9.2), which we will fix by widening it.

**52. Isn't it circular to generate data and then recover it?**
The estimators are not told how the data were made; they only see what a hospital would see. The naive method
fails badly on the same data (bias −0.159, coverage 0%), so recovering the truth is a real test. This is the
standard way causal methods are validated (ACIC, IHDP). It proves the method, not real drug effects.

**53. Where do the drug effect sizes come from?**
Directions and rough sizes from meta-analyses (Tsapas 2020, Palmer 2016), treatment-selection studies (Dennis
2022, TriMaster 2023) and trials (CANTATA-D); marked ASSUMED-DIRECTIONAL because the exact numbers are ours.

**54. 93 of 117 parameters are TEAM-SET. Isn't that weak?**
It is honest labelling. Most TEAM-SET numbers shape the synthetic population (spreads, how doctors choose), not
claims about drugs. Each has a worksheet row to replace it with a cited value, and the loader refuses any number
without a label.

**55. What is NMB-2017?**
A real nationwide Indian survey (2017) of 7,496 adults at high risk of type 2 diabetes, public domain (CC0). It has
age, sex, BMI, waist and HbA1c, but no drug or follow-up, so we use it only as a realism check; the engine never
reads it (a test checks).

**56. How would you use real hospital data?**
An ethics-approved (IEC), de-identified EHR extract under the DPDP Act → mapped to the same columns as
`observed_view` by the real-data adapter → the same code runs → compare with RCT results → a silent pilot where
doctors see it but do not act on it → then the CDSCO device question (backup slide 38).

**57. What about missing values in real records?**
The chat app already names any missing required field instead of guessing. For real data, the adapter will report
missingness; imputation would be added only with a stated assumption.

**58. Why 5,000 patients?**
It is the size in our build guide, large enough for stable estimates and similar to a mid-sized hospital's
records. The benchmark repeats it 20 times with fresh cohorts plus 2,000 test patients each.

**59. Do you store any patient data?**
No real patients at all. The chat app never logs patient values or message text (tests check); the website keeps
patient values on the device.

**60. What about fairness, e.g. across sex?**
The cohort assumes no sex difference, so we cannot claim fairness yet. Subgroup checks need real data;
Gudemann 2026 (ethnicity validation of a similar algorithm) shows why this matters.

**61. Why Asian-Indian BMI cut-offs?**
Indians have higher body fat and diabetes risk at a lower BMI; the consensus (Misra 2009) uses overweight ≥ 23
and obese ≥ 25 instead of 25 and 30.

### E. Safety, ethics and regulation
**62. Is this a medical device?**
No. It is a research prototype for clinician evaluation; not a marketed medical device; not for unsupervised
clinical use. That sentence is on every screen and API response, errors too.

**63. Can a patient use it?**
No. Accounts are for clinicians and need admin approval; there is no patient mode.

**64. Why do you never show doses?**
Dosing depends on kidney function, other drugs and local labels, and a wrong dose is directly harmful. We say
"consult the label" (e.g. R04); an output check and tests make sure no dose appears.

**65. Where do the safety rules come from?**
US FDA prescribing information (FARXIGA, JANUVIA, glimepiride), each with its section. Seven are verified against
the label; three are team-set cut-offs flagged for the clinician (R08 age 65, R09 eGFR 60, R10 eGFR 30).

**66. Isn't using unverified rules dangerous?**
They are conservative (two are only cautions), clearly marked UNVERIFIED/TEAM-SET, and the whole tool is research
only. A doctor's review is part of the plan.

**67. Why are there two rule tables?**
`data/rules.csv` is the engine's table from the build guide; `guardrails.v1.yaml` is the chat app's table from our
guardrail research, with more patient fields. They differ (docs/CAUSAL_PLAN.md §4); in the joined chat app the
stricter action wins until the doctor decides.

**68. Indian labels may differ from US labels.**
Yes. CDSCO labelling can differ, and drugs common in India without a US label (vildagliptin, teneligliptin,
gliclazide, remogliflozin) are not covered. The YAML says this, and the doctor must confirm each rule.

**69. What if the system is wrong?**
It shows ranges, abstains when unsure, lists assumptions and sources, logs every decision (IDs and versions only),
and the doctor decides. It is not for unsupervised use.

**70. How do you protect privacy?**
Identifiers (Aadhaar, ABHA, PAN, Indian mobile, e-mail) are blocked before sending; patient details are structured
fields that are never logged; logs hold only trace IDs, sizes and stage results; the website keeps patient values
on the device.

**71. What happens with an emergency, e.g. "sugar 40, unconscious"?**
The emergency guard (e.g. glucose below 54 mg/dL, "unconscious", "seizure") stops the request and shows an urgent
notice instead of advice.

**72. Did you need ethics approval?**
Not for synthetic data. The clinician study and any real-data work need Institutional Ethics Committee approval;
that is in the plan.

**73. Who is liable if a doctor follows it?**
The clinician remains responsible; the tool is a research prototype, not approved for care. A clinical version
would need regulatory review (CDSCO, as SaMD).

**74. How do you handle out-of-scope questions?**
Type 1 diabetes, pregnancy, under 18, DKA/HHS and starting insulin are refused with a notice (09–12) before any
work; the server returns a reason code and topic, never the matched word.

**75. Why is the intended-use sentence everywhere?**
It sets the right expectation for every reader and every screen, including error messages and printouts, and a
test checks it is present.

### F. Evidence search (RAG) and LLMs
**76. What is RAG and why do you need it?**
Retrieval-augmented generation: first find passages in trusted documents, then answer only from them with
citations. Doctors want to see *why* a drug is flagged, in the source's own words.

**77. Why not let an LLM answer directly?**
LLMs can hallucinate, invent citations or doses. Our default answer is a template that only quotes sentences
verbatim; an LLM is optional and its answer is rejected unless every sentence cites a retrieved passage.

**78. Which documents, and why only those?**
WHO 2018 guidelines on second- and third-line diabetes medicines and 7 FDA Drug Safety Communications: 8 documents,
78 passages. Only sources whose licence we checked (the licence gate) are used.

**79. What is the licence gate?**
`RAG/sources.csv` lists each candidate with its licence; only rows marked `cleared_ingest` by a named person are
ingested. RSSDI and other guidelines wait for permission.

**80. How does the search work?**
Two rankings: BM25 (keywords, rarer words count more) and TF-IDF cosine similarity. They are combined by
reciprocal rank fusion (score = Σ 1/(60 + rank)), and the top 5 passages are kept.

**81. Why not embeddings / a vector database?**
We started lexical because it is transparent, offline and reproducible. A medical embedding model and a reranker
are Section 4a (target 3 October), and there is a slot for them in the code.

**82. How do you prevent hallucination?**
Quoted sentences by default; a citation checker (each sentence must share at least 60% of its content words with
the passage it cites); dose text removed from the index; abstention when coverage is low. Citation precision is
1.000.

**83. What if the sources do not cover a question?**
If the best match is weak (BM25 below 1.0) or the passages cover less than 60% of the question's words, it answers
"insufficient evidence" (e.g. "How much does glimepiride cost in India?").

**84. Abstention is 0.80, below your 0.90 target. Why?**
Some out-of-scope questions share many words with our sources, and keyword search cannot tell. We report it
openly; the medical embedding model and reranker in Section 4a are the fix.

**85. You tuned thresholds on the same 60 questions. Isn't that over-fitting?**
Yes, so the numbers are optimistic; we say so in the report. A held-out question set comes with Section 4a.

**86. Who made the gold questions?**
The team, from the source documents: 45 answerable, 10 out of scope, 5 dose requests. A doctor's review of 20
flagged questions is pending.

**87. What is sent to Gemini, and is it safe?**
Only the question and passage IDs, only when an approved user presses the button, through a Supabase Edge Function;
the key is a Supabase secret, never in the repo. Patient values are never sent.

**88. Why Ollama too?**
For fully offline use: a small local model (llama3.2:3b) on a laptop, behind the same citation checker.

**89. What does citation precision 1.000 mean?**
Every quoted sentence in the answers was found in the passage it cited: no made-up quotes.

### G. Software, security and testing
**90. What is your tech stack, and why?**
Python 3.12 (NumPy, pandas, scikit-learn, SciPy) for the engine and RAG; FastAPI + Pydantic for APIs; React +
TypeScript + Tailwind for the chat page; plain JavaScript for the website; Supabase and Netlify for accounts and
hosting; Docker + Caddy for deployment. All free and widely used.

**91. Why FastAPI?**
It is fast, typed, validates requests with Pydantic (we reject unknown fields) and generates API docs automatically
(`/docs`, off in production).

**92. Explain the six pipeline stages.**
backend_guard → clinical_guardrails → causal_engine → rag_retrieval → llm_explanation → output_guard. Guards first,
safety before estimates, output checked last; after a block, later stages are "skipped".

**93. What is a trace ID?**
An 8-character hex label for each message, printed at the start of every log line in the browser and server, so we
can follow one message end to end without logging its text.

**94. How does sign-in work?**
User ID + password + a 6-digit CAPTCHA (with audio), then a 6-digit code from an authenticator app. Then a secure
`__Host-` session cookie with a CSRF token; idle sign-out after 15 minutes.

**95. Why Argon2id for passwords?**
It won the Password Hashing Competition; it is slow and memory-hard, so stolen hashes are expensive to crack.
Passwords must be at least 12 characters and not common.

**96. What is TOTP? What if a doctor loses their phone?**
A time-based one-time password: the phone app and the server share a secret and compute the same 6 digits every
30 seconds. An admin can reset it with `python3 scripts/admin.py --as ADMIN_ID reset-mfa USER_ID` after checking who is
asking; every admin action goes to the audit log.

**97. What is CSRF and how do you stop it?**
Another website tricking your browser into sending a request with your cookie. Every changing request must carry
our secret `X-CSRF-Token` header, which another site cannot read.

**98. How do you stop password guessing?**
Growing delays after 3 failures, a 15-minute lock after 5, per-IP limits, and the CAPTCHA; unknown user IDs behave
the same, so attackers cannot tell which IDs exist (OWASP ASVS, NIST 800-63B).

**99. How many tests, and what do they cover?**
Engine 150, RAG 33, website 19, chat app 401 backend + 246 frontend, and `check_all` with 43 checks including live
servers and a real browser. They cover features and rules: no doses, intended use everywhere, no patient values in
logs, thresholds only in their files.

**100. What is CI?**
Continuous integration: GitHub Actions runs the tests on Linux, macOS and Windows for every change.

**101. How does voice input work, and is it private?**
The doctor records up to 30 s; faster-whisper ("base", int8) turns it into text on our own server; the text goes
into the message box for the doctor to check and send. The audio is not kept and the transcript is never logged.

**102. How is it deployed?**
`docker compose up --build -d` serves the page and the API from one origin behind Caddy with HTTPS; secrets come
from `.env` at run time; security headers in `backend/app/web.py`.

**103. What if the network fails during the demo?**
The website works offline once loaded (PWA); a local copy runs with `python3 -m http.server 8080`; and there is a
112-second demo video.

### H. The website
**104. Why a website as well as the chat app?**
It runs on any phone with nothing to install and works offline, which suits Indian clinics; the chat app is the
full secure application.

**105. How do you know the browser gives the same numbers as Python?**
`export_web.py` writes the fitted model to `model.json`, and a parity test compares the browser's and Python's
answers on many cases (47 examples + 55 tricky cases); `tests/web` fails if the files are stale.

**106. What is a PWA?**
A progressive web app: it can be installed on the home screen and works offline, using a service worker (`sw.js`).

**107. How are website accounts approved?**
A clinician signs up and sets up an authenticator app; an admin approves the account; only approved accounts can
use Try it and Evidence. Supabase row-level security (RLS) enforces who can read what.

**108. What is the CSP for?**
The Content Security Policy tells the browser to run only our own scripts and styles (no inline code), which blocks
cross-site scripting attacks.

### I. Scope, future and the team
**109. What is out of scope?**
Type 1 diabetes, pregnancy, under 18, emergencies (DKA/HHS), starting insulin, doses, GLP-1 RAs and real patient
use.

**110. What is your future scope?**
Medical embeddings + reranker, a real-data adapter, clinician review (25 vignettes, SUS, Cohen's κ), more drug
classes, Indian guideline sources once licensed, prices from Jan Aushadhi, and a real-data study with ethics
approval.

**111. Where will you publish?**
An IEEE-format paper; candidate venues such as IEEE EMBC 2027 and IEEE ICHI 2027 (report Appendix B), decided with
our guide.

**112. How will you evaluate with clinicians?**
Doctors review the 25 synthetic vignettes in `eval/` (the report plans up to 60 cases) and our 20 flagged RAG
questions; we measure agreement (Cohen's κ, target ≥ 0.61) and usability (SUS, target ≥ 68). The forms are in
`eval/`.

**113. What are your main limitations?**
Synthetic data (method proven, not drug effects); keyword search with abstention 0.80; no doctor review yet; some
rule cut-offs team-set; prices unavailable.

**114. What did you learn?**
That a fair comparison needs causal methods, not averages; that saying "I don't know" is a feature; and that
safety rules must be data, with sources and tests, not code.

### J. Hard and trick questions
**115. "Your results on synthetic data prove nothing."**
They prove that the method recovers a known truth under realistic confounding while the naive method fails. That is
the necessary first step; real-world effects need real data with ethics approval, and we do not claim them.

**116. "The ranges overlap, so the tool is useless."**
Overlap is honest information: for this patient the drugs lower HbA1c similarly, so the doctor can decide on weight,
low-sugar risk, cost and preference, which we also show.

**117. "Isn't this a black box?"**
No: every rule has a source, every number has a range and a propensity, the assumptions are listed, the evidence is
quoted with citations, and the code and tests are open.

**118. "Why HbA1c only, and not heart attacks or death?"**
Hard outcomes need years of follow-up. We show SGLT2i heart and kidney benefits as information rules (G15, G16)
with sources; causal estimates for hard outcomes are future work.

---

## Part 7 · Learn it fast with NotebookLM and Claude

### 7.1 The ready-made explainers (start here)
- **Interactive explainer page** (link in the chat, and `docs/midsem/explainer/index.html`): 12 scenes you can
  play like a video, with a narrator voice, animated diagrams, the 25% boundary, a glossary search and a quiz.
- **Narrated video** `docs/midsem/DiaCausal_explainer.mp4`: the same story, to watch on a phone.
- **Deck + notes:** `Intelligent_Diabetes_CDSS_MidSem_updated.pptx`; the slide-by-slide words are in
  `TEAM_BRIEFING.md`.

### 7.2 NotebookLM (notebooklm.google.com): a podcast and a video about *our* project
1. Create a notebook "DiaCausal". **Add sources** (upload the PDFs from `docs/midsem/`):
   `PANEL_PREP.pdf` (this pack), `TEAM_BRIEFING.pdf`, `EXPLAINING_DIACAUSAL.pdf`, `DATASETS.pdf`,
   `Intelligent_Diabetes_CDSS_MidSem_updated.pdf` (the deck) and `DiaCausal_MidSem_Report.pdf`.
2. **Audio Overview** (Studio panel → Audio Overview → Customise). Paste:
   > "Explain the DiaCausal project to four final-year engineering students who will present it to a panel
   > tomorrow and who know little about diabetes or statistics. Start with the problem (choosing the second
   > diabetes drug after metformin) and why a naive comparison is biased (confounding). Then explain, step by step,
   > exactly what the 25% implementation covers and where it ends (the six steps on slide 23). Expand every
   > abbreviation the first time (SGLT2i, DPP-4i, HbA1c, eGFR, IPW, AIPW, DR-learner, HC3, RAG, BM25, TOTP, CSRF).
   > Then cover the 40% and 60% checks, the numbers (bias −0.159 vs +0.002, coverage, recall@5 0.933, abstention
   > 0.80), the honest limitations, and end with the ten hardest panel questions and model answers."
   You can set the **output language** (for example Hindi) in NotebookLM's settings for a second version.
   Use **Interactive mode** ("Join") to interrupt the hosts and ask your own question.
3. **Video Overview** (Studio → Video Overview → Customise): "A 10-minute explainer with diagrams for students
   presenting this project; focus on how the system works end to end, the 25% boundary, and what each
   component does."
4. **Mind Map**: a clickable map of the whole project; open each branch and explain it aloud.
5. **Flashcards / Quiz** (Studio): "Make 40 flashcards on the abbreviations in Part 3 and 20 quiz questions on
   Parts 2 and 6." Do them until you get every answer right.
6. **Chat** with the notebook: ask "What exactly is in the 25%?", "Explain AIPW with the numbers from our
   benchmark", "What would the panel ask about synthetic data?" NotebookLM answers with citations to your PDFs.

### 7.3 Claude (claude.ai): a tutor that can read the code
1. Follow `docs/CLAUDE_CHAT_GUIDE.md`: create a Project, add the GitHub repository (Project knowledge → + →
   GitHub) and the PDFs above, and paste the project instructions from the guide.
2. **Study prompts** (copy and paste):
   - "I know nothing about this project. Teach me Part 2 of PANEL_PREP (the 25%) one step at a time. After each
     step, ask me one question and wait for my answer before moving on."
   - "Explain `diacausal_engine/estimators.py` line by line in plain English, then tell me which panel questions
     it answers."
   - "Give me 15 multiple-choice questions on the abbreviations in PANEL_PREP Part 3. Show the score at the end
     and re-ask the ones I got wrong."
   - "Draw the six chat-app pipeline stages as a diagram and explain what each one blocks."
3. **Mock viva** (the most useful one):
   > "Act as a panel of three examiners (a clinician, a statistician and a software engineer) at a mid-semester
   > project review. Ask me one question at a time about DiaCausal, mixing easy and hard, especially about the
   > 25% implementation, synthetic data, causal methods and safety. After each answer, grade it out of 10, show
   > a better model answer using only facts from the repository and PANEL_PREP, then ask the next question. Stop
   > after 15 questions and list my three weakest areas."
4. **Voice practice:** in the Claude mobile app, use voice mode with the mock-viva prompt, so you practise
   answering out loud, like on the day.
5. **Check yourself:** "Here is my answer to 'why synthetic data?': … Is anything wrong or overstated? Correct it
   using the repository."
6. **Each person, their slides:** "I present slides 14–21 (Graceton). Quiz me on everything on those slides and
   the questions the panel may ask about them."

Rule for all AI tools: if an answer gives a number, check it against Part 5 (numbers card). The repository is
the source of truth.

---

## Part 8 · On the day

### 8.1 Checklist
- [ ] Laptop charged, charger, HDMI/USB-C adapter; the deck opened from the `.pptx` (PDF copy as backup).
- [ ] Browser zoom 125–150%; website signed in **no more than 15 minutes** before the slot (idle sign-out);
      the authenticator phone with the person driving.
- [ ] Backup A: `cd web && python3 -m http.server 8080` (no internet, no sign-in).
- [ ] Backup B: `DiaCausal_demo.mp4` (112 s) and `DiaCausal_explainer.mp4`.
- [ ] Each presenter knows their slides and the hand-over sentence (`EXPLAINING_DIACAUSAL.md` §5).
- [ ] Everyone can say, from memory: the one-sentence project, the 25% sentence, −0.159 vs +0.002, and
      "about 75%, with the sheet's 25/40/60% checks met".

### 8.2 Rescue lines
- **Do not know:** "That is a good question; we have not measured it yet. Here is how we would: …"
- **Challenged on synthetic data:** "It proves the method recovers a known truth; real effects need hospital
  data with ethics approval, which is our next step."
- **Asked for a number you do not remember:** "Let me show you": open `results/` or slide 27/29.
- **A teammate is stuck:** "If I may add…" and answer in one sentence, then hand back.
- **Demo fails:** "We have a recording of the same flow" → play the video, keep talking over it.

### 8.3 Never say
- "It recommends / prescribes / decides." → Say "it estimates; the doctor decides".
- "It is accurate on real patients" or "trained on real data." → It is synthetic; real data is future work.
- "100% accurate" or "AI decides." → Give the measured numbers with ranges.
- Any **dose**. → "We never show doses; the label decides."
- "We have 80% / 100% implementation." → Claim only 25% (signed), 40% and 60% (met); "about 75% of the whole
  project" is an estimate.
- The matched word of a guard block, or any patient's identifying detail.
