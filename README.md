# DiaCausal CDSS

**Causal Inference for Diabetes Clinical Decision Support**

A transparent, from-scratch implementation of causal inference methods applied to diabetes treatment selection — built as a B.Tech Final Year Major Project at FCRIT.

> Every causal quantity is computed **by hand** in NumPy so that each step can be explained, line by line, to a non-specialist. Nothing is hidden behind a library call.

## 🧪 Causal engine v0.3 — the mid-sem demo (start here)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

For one adult with type 2 diabetes **already on metformin**, DiaCausal compares three add-on
options: an **SGLT2 inhibitor**, a **DPP-4 inhibitor** and a **sulfonylurea**. It works in this order:

1. It removes unsafe options first, using cited drug-label rules in [`data/rules.csv`](data/rules.csv).
2. It estimates each remaining option's **6-month HbA1c change with a 95% range**.
3. It says **"insufficient evidence"** when too few similar patients got an option.

The clinician decides. All data is **synthetic**: an India-calibrated cohort whose every number
has a source and a status in [`data/params.yaml`](data/params.yaml).

### On a MacBook (Terminal)

Install Python 3.12 from python.org first. Then, once:

```bash
git clone https://github.com/Rhian-Roy/DiaCausal-CDSS.git
cd DiaCausal-CDSS
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-engine.txt
```

Every time, in a new Terminal window:

```bash
cd DiaCausal-CDSS
source .venv/bin/activate

python -m pytest tests/engine -q                  # the tests: must end "130 passed" (about 40 s)
python -m diacausal_engine.benchmark --quick      # quick benchmark (about 15 s)
python -m diacausal_engine.benchmark              # full benchmark: 20 x 5,000 patients (about 2 min), rewrites results/
streamlit run demo/streamlit_app.py               # the demo; opens http://localhost:8501
uvicorn diacausal_engine.api:app --port 8001      # the API; docs at http://localhost:8001/docs
```

- **Demo:** the demo takes about 5 seconds to warm up the first time. Then use the three preset
  buttons on the left:
  1. a typical patient;
  2. eGFR 40 with past pancreatitis: a red exclusion and amber cautions, each with its source;
  3. an older patient with past hypoglycaemia: grey "insufficient evidence".
- **Stopping:** press `Ctrl+C` in the Terminal to stop the demo or the API.
- **Try the API:**
  ```bash
  curl -s -X POST localhost:8001/api/v1/recommend -H 'content-type: application/json' \
    -d '{"schema_version":"1.0","patient":{"age":60,"sex":"female","duration_years":8,"hba1c":8.2,"egfr":40,"bmi":25.5,"pancreatitis_history":true}}'
  ```

### What is where

| Path | What it is |
|---|---|
| `diacausal_engine/` | The engine. Its parts follow the "Causal Inference Pipeline" of our flow chart: the dataset (`cohort.py`), the DAG (`dag.py`), safety rules (`guardrails.py`), propensity and overlap (`propensity.py`), naive / IPW / matching / AIPW and the DR-learner (`estimators.py`), metrics, the benchmark, the one-patient **Causal Output** (`recommend.py`, `schemas.py`) and the API (`api.py`) |
| `data/rules.csv` | Safety rules R01–R10, each with a source (Part 6 of `docs/02_Causal_Engine_Build_Guide.md`, verbatim) |
| `data/params.yaml` | Every generator and engine number, each with `source` and `status` (CITED / ASSUMED-DIRECTIONAL / TEAM-SET) |
| `data/prices.csv` | Prices: "price unavailable" until confirmed on the Jan Aushadhi list, with a date |
| `results/` | Committed benchmark output: `results_table.tex`, `benchmark_summary.csv`, `run_info.json`, `figures/` (overlap, love plot, ATE vs truth, CATE recovery, calibration) |
| `screens/` | Screenshots of the three demo presets |
| `demo/streamlit_app.py` | The demo screen |
| `tests/engine/` | The tests: 130 of them, one file per build step (a–j) |
| `docs/REPO_INVENTORY.md`, `docs/CAUSAL_PLAN.md` | What the repo contains, and how the engine was planned and connects to the chat app |

## 💬 Chat app (walking skeleton)

A clinician-facing chat page (`frontend/`, React + Vite) talking to a FastAPI backend
(`backend/`) through a six-stage pipeline. Today it returns a dummy reply; the causal
engine below will plug into it. Research prototype for clinician evaluation; not a
marketed medical device; not for unsupervised clinical use.

**Teammates — start here, in this order:**

1. [`docs/SETUP.md`](docs/SETUP.md) — install, one setup command, one check command (macOS, Windows, Linux)
2. [`docs/TESTING.md`](docs/TESTING.md) — how to know everything works, and what to do if not
3. [`docs/explain/01-walking-skeleton.md`](docs/explain/01-walking-skeleton.md) — what happens when you press Enter
4. [`docs/explain/02-presenting-it.md`](docs/explain/02-presenting-it.md) — pitch, demo script, answers to likely questions
5. [`CLAUDE.md`](CLAUDE.md) — the project's working rules

---

## ✨ Highlights

- **10 estimators implemented from scratch** — Naive, Stratification, G-Computation, Propensity Score Matching, IPW, Stabilised IPW, AIPW, S-Learner, T-Learner, X-Learner
- **Cross-checked against DoWhy & EconML** — every hand-written result is verified to ≤4 decimal places against the standard libraries
- **Guideline citations (research code)** — retrieves passages with page-level citations from guideline PDFs we are licensed to use (IDF 2025 is **not** licence-cleared — `RAG/sources.csv` S11 says "all rights reserved"; ADA's Standards of Care are not cleared either). Licences are tracked in `RAG/sources.csv`
- **Clinical guardrails** — hard safety rules (eGFR thresholds, contraindications) that override any statistical estimate
- **Interactive Streamlit demo** — move sliders to watch confounding change the answer, and see personalised CATE recommendations update live

## 📁 Project Structure

```
.
├── causal_engine/                  # Core Python package
│   ├── __init__.py
│   ├── data.py                     # Synthetic EHR data with authored ground truth
│   ├── dag.py                      # Causal graph, backdoor paths, d-separation
│   ├── estimators.py               # 10 causal estimators (hand-rolled NumPy)
│   ├── diagnostics.py              # Balance (SMD), overlap, E-value sensitivity
│   ├── evaluate.py                 # Grade estimators vs ground truth; policy value
│   ├── crosscheck.py               # Verify hand-maths ≡ DoWhy/EconML
│   ├── pdf_text.py                 # Zero-dependency PDF text extraction
│   ├── rag_lite.py                 # TF-IDF retrieval with page citations
│   ├── guardrails.py               # Hard clinical safety rules
│   ├── cdss.py                     # Fusion layer: CATE + guidelines + guardrails
│   └── guideline_fallback.py       # Fallback when PDFs aren't available
├── tests/
│   └── test_causal_engine.py       # Comprehensive test suite
├── Datasets/
│   ├── diabetes.csv                # "Pima Indians Diabetes" dataset: women of the
│   │                               # Akimel O'odham community, Arizona, USA — NOT from India
│   └── synthetic_diabetes_ehr.csv  # Generated synthetic EHR
├── RAG/                            # Clinical guideline PDFs for retrieval
├── Research Papers/                # Reference literature
├── figures/                        # Generated plots and visualisations
│
├── 01_Causal_Inference_Basics.ipynb          # Narrated notebook (10 acts)
├── DiaCausal_Causal_Inference.ipynb          # Full pipeline notebook
├── causal_inference_basics.py                # Console script — narrated run
├── causal_inference_implementation.py        # Production DoWhy/EconML pipeline
├── diacausal_demo.py                         # Streamlit interactive demo
├── smoke_streamlit.py                        # Headless smoke test for the demo
├── build_notebook.py                         # Script to regenerate the notebook
├── verify_notebook.py                        # Notebook output verifier
└── pytest.ini                                # Test configuration
```

## 🚀 Quick Start — older 2-arm research code (notebooks)

### 1. Clone & install dependencies

```bash
git clone https://github.com/Rhian-Roy/DiaCausal-CDSS.git
cd DiaCausal-CDSS
pip install -r requirements.txt
```

### 2. Run the narrated script

```bash
python causal_inference_basics.py
```

This walks through all 10 acts in the terminal — data generation, DAG construction, balance diagnostics, estimation, cross-checking, and clinical recommendations.

### 3. Launch the interactive demo

```bash
streamlit run diacausal_demo.py
```

### 4. Run the test suite

```bash
python -m pytest tests/ -q                    # full suite (~85s)
python -m pytest tests/ -q -m "not slow"      # skip library cross-checks (~37s)
```

## 🔬 The Ten Acts

| Act | What happens |
|-----|-------------|
| 1 | **Synthetic World** — generate 2 000 patients with an authored ground-truth treatment effect |
| 2 | **Confounding** — show that the naive comparison gets the wrong answer |
| 3 | **DAG** — draw the causal graph, find backdoor paths |
| 4 | **Diagnostics** — SMD love plot, propensity overlap, positivity checks |
| 5 | **Estimation** — run all 10 estimators, compare to ground truth |
| 6 | **Refutation** — placebo treatment, random cause, subset tests |
| 7 | **CATE** — heterogeneous treatment effects by patient subgroup |
| 8 | **Cross-check** — verify hand-maths matches DoWhy & EconML |
| 9 | **RAG + Guardrails** — retrieve guideline citations, apply safety rules |
| 10 | **CDSS** — fuse everything into a personalised treatment recommendation |

## 🛡️ Clinical Guardrails

Safety rules run **before** any estimate and override it. Their thresholds are never typed into code:

- **Causal engine v0.3:** [`data/rules.csv`](data/rules.csv), rules R01–R10 with the drug-label
  source and section of each. For example, R01 excludes an SGLT2 inhibitor for glucose lowering
  when eGFR < 45, and R10 excludes a sulfonylurea when eGFR < 30. Rules marked UNVERIFIED await
  review by the collaborating doctor.
- **Chat app:** [`backend/app/clinical/guardrails.v1.yaml`](backend/app/clinical/guardrails.v1.yaml),
  a draft table that differs from `rules.csv`. [`docs/CAUSAL_PLAN.md`](docs/CAUSAL_PLAN.md) §4
  lists every difference for the doctor to resolve.
- The older 2-arm research code in `causal_engine/guardrails.py` still has numbers in code. It is
  kept for the notebooks only; don't use it for the demo.

## 📦 Dependencies

Core: `numpy`, `pandas`, `scikit-learn`, `matplotlib`, `scipy`

Optional (for cross-checking): `dowhy`, `econml`

Interactive demo: `streamlit`

## 📄 License

This project is part of a B.Tech Major Project at FCRIT. See the repository for licensing details.

## 👥 Authors

Built at **Fr. Conceicao Rodrigues Institute of Technology (FCRIT)**.
