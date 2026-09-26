# Offline install (viva laptop today, hospital computer later)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

The public website is for **evaluation** with synthetic data. A hospital would instead install
DiaCausal on its own computers, inside its own network, with no internet and no outside accounts.
This page does that on any laptop (Windows, macOS or Linux).

## 1. Once, with internet

```bash
git clone https://github.com/Rhian-Roy/DiaCausal-CDSS.git
cd DiaCausal-CDSS
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-engine.txt        # Windows: .venv\Scripts\pip ...
```

Optional local language model (for plain-English explanations without internet):

1. Install Ollama from https://ollama.com (free).
2. `ollama pull llama3.2:3b` (about 2 GB; the name is `ollama_model` in `diacausal_rag/config.yaml`).

## 2. Run with the internet switched off

```bash
cd web && python3 -m http.server 8080                  # then open http://localhost:8080
```

`web/config.json` in the repository says `"accounts": "off"`, so this copy needs no sign-in and never
contacts Supabase (the page shows "Local copy: sign-in is switched off"). Everything — the causal
engine, the evidence search and the quoted explanations — runs inside the browser.

Explanations in plain words from the local model (nothing leaves the computer):

```bash
.venv/bin/python -m diacausal_rag.explain "Can SGLT2 inhibitors cause ketoacidosis?" --backend ollama
```

Every sentence the model writes must cite a passage and match its words; otherwise the quotes are
shown. Other tools, all offline: `streamlit run demo/streamlit_app.py` (demo),
`uvicorn diacausal_engine.api:app --port 8001` (API), `python -m diacausal_rag.evaluate --backend ollama`.

## 3. For a hospital (later, with the hospital's IT team)

- Serve `web/` from an internal web server (HTTPS on the intranet), accounts off or behind the
  hospital's own sign-in; never expose it to the internet.
- Replace the synthetic cohort with a de-identified local dataset only after ethics approval
  (`diacausal_engine/cohort.py: load_dataset`), rerun the benchmark and refit.
- Keep the licence rules: only sources the hospital may copy go into `diacausal_rag/corpus/`.
- The doctor stays in charge: decision support only, no doses, every number with its 95% range.
