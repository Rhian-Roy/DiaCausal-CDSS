# DiaCausal CDSS

**Causal Inference for Diabetes Clinical Decision Support**

A transparent, from-scratch implementation of causal inference methods applied to diabetes treatment selection — built as a B.Tech Final Year Major Project at FCRIT.

> Every causal quantity is computed **by hand** in NumPy so that each step can be explained, line by line, to a non-specialist. Nothing is hidden behind a library call.

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
- **Guideline citations (research code)** — retrieves passages with page-level citations from guideline PDFs we are licensed to use (IDF 2025 is cleared; ADA's Standards of Care are **not** licence-cleared, so they are not included). Licences are tracked in `RAG/sources.csv`
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

## 🚀 Quick Start

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

The system includes hard safety constraints that **override** any statistical estimate:

- eGFR < 30 → contraindicate SGLT2i
- eGFR < 45 → flag metformin dose adjustment
- Known allergies / contraindications
- Confidence-interval-too-wide warnings

## 📦 Dependencies

Core: `numpy`, `pandas`, `scikit-learn`, `matplotlib`, `scipy`

Optional (for cross-checking): `dowhy`, `econml`

Interactive demo: `streamlit`

## 📄 License

This project is part of a B.Tech Major Project at FCRIT. See the repository for licensing details.

## 👥 Authors

Built at **Fr. Conceicao Rodrigues Institute of Technology (FCRIT)**.
