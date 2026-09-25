# System Requirements: DiaCausal

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

**For:** mentor item 2 ("Hardware & Software Requirements"), slides 7–8 and report Chapter 4.
Each requirement names the **file or test that proves it**, so every claim can be checked. "Planned"
marks work for October; "Not measured" means we have no evidence yet, so do not claim it.

## 1. Scope and users

| Item | Description |
|---|---|
| Problem | An adult with type 2 diabetes on metformin needs a second drug. Which of SGLT2 inhibitor, DPP-4 inhibitor or sulfonylurea, for *this* patient? |
| Output | Each option's expected 6-month HbA1c change with a 95% range, or "insufficient evidence", after unsafe options are removed with cited rules. Later: cited guideline explanations (RAG). |
| Primary user | Clinician (during a consultation). **The clinician decides.** |
| Other users | Evaluator (runs the benchmark, reviews logs); administrator (manages accounts, rules and sources) |
| Out of scope | Type 1 diabetes, pregnancy, under-18s, emergencies, starting insulin, drug doses |
| Data | **Synthetic only**, an India-calibrated cohort (`data/params.yaml`). No real patient data. |

## 2. Functional requirements

| ID | Requirement | Status | Proved by |
|---|---|---|---|
| FR-1 | Accept the patient's details, with units, and reject impossible values with a plain-English message | Built | `diacausal_engine/schemas.py`; `tests/engine/test_i_api.py`; chat app `backend/tests/test_patient.py` |
| FR-2 | Apply cited safety rules **before** any estimate; exclude or caution each option, and show the source and section | Built | `data/rules.csv`, `guardrails.py`; `test_b_guardrails.py`; `test_h_demo.py` (rules run before the estimate) |
| FR-3 | Estimate each remaining option's 6-month HbA1c change with a **95% interval** | Built | `estimators.DRLearner`; `test_e_dr_learner.py`; `test_j_invariants.py` (300 random patients) |
| FR-4 | Say "insufficient evidence" when propensity < 0.05 or the patient is outside the cohort; NOT_APPLICABLE when nothing can be answered | Built | `propensity.py`; `test_c_propensity.py`; `test_h_demo.py` |
| FR-5 | Compare options fairly (pairwise differences with 95% intervals) | Built | `recommend.py` comparisons; `test_h_demo.py` |
| FR-6 | Show the monthly cost in INR, or "price unavailable" until a price is confirmed | Built | `data/prices.csv`; `test_h_demo.py` (prices stay unavailable) |
| FR-7 | Return a structured Causal Output (applicable, intervention, outcome, effect, confidence, assumptions) | Built | `schemas.CausalOutput`; `test_h_demo.py` (every flow-chart field) |
| FR-8 | REST API `POST /api/v1/recommend` | Built | `diacausal_engine/api.py`; `test_i_api.py` |
| FR-9 | Log every request with its ID, versions and decisions | Built | `recommend.write_audit`; chat app `audit_log` table; `test_h_demo.py` |
| FR-10 | Benchmark against the known truth: bias, RMSE, coverage, PEHE, regret, balance, refutation | Built | `benchmark.py`, `refute.py`; `results/`; `test_g_benchmark.py`, `test_k_refute.py` |
| FR-11 | Demo with preset patients and a "Why causal?" explanation | Built | `demo/streamlit_app.py`; `screens/`; `test_h_demo.py` |
| FR-12 | Chat app: sign-in with password, CAPTCHA and an authenticator code; message guards; patient panel | Built | `backend/app/auth/`, `pipeline/`; `scripts/check_all.py` (43 checks) |
| FR-13 | Voice input put into the message box (never sent automatically) | Built | `backend/app/voice/`; `backend/tests/test_voice.py` |
| FR-14 | Evidence retrieval with a citation for every sentence (RAG), refusing when unsupported | **Planned (1–16 Oct)** | `docs/03_RAG_Build_Guide.md`; `diacausal_rag/` skeleton |
| FR-15 | Causal engine inside the chat app (designs 17–19) | **Planned (Oct)** | `docs/CAUSAL_PLAN.md` §6 |
| FR-16 | Hypoglycaemia risk and weight change per option (from cited tables) | **Planned** | worksheet rows 23–24 still "needs decision" |

## 3. Non-functional requirements

| ID | Requirement | Target | Evidence today |
|---|---|---|---|
| NFR-1 Safety | Never show a drug dose; excluded options never get a number | 0 dose strings | Output check in `recommend.check_output`; `test_j_invariants.py`; `test_h_demo.py` |
| NFR-2 Honesty | Every estimate carries a 95% interval; abstain rather than guess | 100% | `test_j_invariants.py` |
| NFR-3 Transparency | Every number in the generator has a source and a status; every rule has a source | 100% | `config.py` refuses otherwise; `test_a_cohort.py`, `test_b_guardrails.py` |
| NFR-4 Intended use | The intended-use sentence on every screen and every API response (errors too) | 100% | `test_h_demo.py`, `test_i_api.py`, `test_j_invariants.py`; chat app `check_all.py` |
| NFR-5 Privacy | No patient values or message text in logs; no real data | 0 values logged | `test_h_demo.py` (audit), `test_i_api.py` (logs); chat app `test_logging.py` |
| NFR-6 Security | No secrets in the repo; exact version pins; dependency audit; sign-in for the chat app | Clean | `test_j_invariants.py` (secrets, pins); `pip-audit` in CI; `backend/tests/test_auth.py` |
| NFR-7 Performance | One recommendation in under 3 s after start-up | < 3 s | About 12 ms per request measured; `test_h_demo.py` asserts < 2 s; start-up fit about 4 s |
| NFR-8 Reproducibility | Same seed gives the same cohort and results | Identical | `test_a_cohort.py` (same seed, same cohort); `results/run_info.json` stores seeds and file hashes |
| NFR-9 Accuracy (synthetic) | Corrected estimators are nearly unbiased with about 95% coverage | Bias < 0.05; coverage ≈ 0.95 | `results/benchmark_summary.csv`: AIPW bias ≤ 0.005, coverage 0.90–0.95 |
| NFR-10 Portability | Runs on macOS, Windows and Linux | 3 OS | GitHub Actions `check` (3 OS) and `engine` (Linux, macOS) jobs |
| NFR-11 Maintainability | Automated tests for every requirement | All pass | 139 engine tests; 392 backend + 238 frontend tests; 43 live checks |
| NFR-12 Accessibility | WCAG 2.1 AA; colour never the only signal | AA | Every status also has a text label (EXCLUDED, CAUTION, INSUFFICIENT EVIDENCE). **Not measured** against WCAG yet. |
| NFR-13 Test coverage | At least 80% line coverage | ≥ 80% | **Not measured yet** (coverage tool not run) |

## 4. Hardware requirements

| Tier | Minimum | Used by us |
|---|---|---|
| Development | Laptop, 8 GB RAM, 5 GB free disk, internet for installing packages | MacBook Air (Apple silicon), plus Claude Code cloud sessions (Linux) |
| Demo | The same laptop, **offline**; or a free Streamlit Community Cloud link as backup | MacBook, with the recorded video as a second backup |
| Client | Any modern web browser (Chrome, Safari, Edge, Firefox) on a laptop or phone | — |
| Chat app deployment | Any machine with Docker; about 2 GB RAM (the speech model is about 145 MB) | `docker compose up` (docs/DEPLOY.md) |

## 5. Software requirements (exact versions from the repo)

| Layer | Software | Version | Where pinned |
|---|---|---|---|
| Language | Python | 3.12 | CI, `scripts/setup.py` |
| Causal engine | NumPy, pandas, SciPy, scikit-learn, Matplotlib, PyYAML | 2.5.3, 3.0.6, 1.18.1, 1.9.1, 3.11.2, 6.0.3 | `requirements-engine.txt` |
| Demo | Streamlit | 1.64.0 | `requirements-engine.txt`, `demo/requirements.txt` |
| API | FastAPI, Pydantic, Uvicorn | 0.141.1, 2.13.5, 0.53.0 | `requirements-engine.txt`, `backend/requirements.txt` |
| Tests | pytest, httpx2 | 9.1.1, 2.13.0 | `requirements-engine.txt` |
| Chat backend | SQLAlchemy, Alembic, pwdlib/argon2-cffi, pyotp, cryptography, captcha, faster-whisper | 2.0.54, 1.20.0, 0.3.1/25.1.0, 2.10.0, 50.0.1, 0.7.1, 1.2.1 | `backend/requirements.txt` |
| Chat frontend | Node, React, Vite, TypeScript, Tailwind CSS, Vitest | 24 LTS (22.22+ accepted), 19.3, 8.3, 6.0, 4.3, 5.0 | `frontend/package.json`, `package-lock.json` |
| Deployment | Docker, Caddy (HTTPS) | Caddy 2.10 | `Dockerfile`, `compose.yaml` |
| RAG (planned) | BM25, dense embeddings, a vector store; LLM via API or local Ollama | to be chosen 1 Oct | `docs/03_RAG_Build_Guide.md` |
| Tools | Git, GitHub, GitHub Actions, Claude Code | — | `.github/workflows/check.yml` |

## 6. Constraints and assumptions

- **Regulatory:** a research prototype only; it would need ethics approval, validation on real data
  and regulatory review before any clinical use.
- **Clinical rules:** taken from US FDA labels (and KDIGO). The collaborating doctor must confirm them
  for Indian practice. UNVERIFIED cut-offs (R03, R08–R10) are labelled on screen.
- **Causal assumptions:** no unmeasured confounding (the E-value quantifies the risk), overlap
  (checked), and a correct DAG. Stated in every Causal Output.
- **Data licences:** RAG may ingest only sources in the `cleared_ingest` bucket of
  `RAG/sources.csv`.
- **Privacy:** India's Digital Personal Data Protection Act, 2023, applies to any future real data.
