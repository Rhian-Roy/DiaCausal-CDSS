# DiaCausal on a clinic laptop, offline

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

This puts DiaCausal on one laptop, so it works **with Wi-Fi switched off**. It is written for Windows first (the team's RTX 2050
laptop), then macOS. You need the internet **once**, for the setup; after that, never.

**What runs:**
- the DiaCausal server (`diacausal.api.main`) on **127.0.0.1:8000**;
- the same website as https://diacausal.netlify.app, served by that server.

A question about a filled-in patient is answered by the server's full pipeline:
1. the seven input guards;
2. the safety rules;
3. the causal engine;
4. the evidence search;
5. the writer;
6. the seven output guards.

The **writer** is a local Ollama model when Ollama is running, or the template when it is not. The page says which one, in a bar
under the header. If the model's draft fails an output check, the template answers instead, and the answer card says so.

**No accounts on the laptop.** The page shows "Local copy: sign-in is switched off". This is acceptable here only for two reasons:
- **The server listens on 127.0.0.1 only.** That address means "this computer", so no other device on the clinic network can open
  it. The start scripts never use `0.0.0.0`, and a test checks that.
- **The laptop keeps no patient data.** The page keeps nothing it is typed, the server writes no patient value, question or answer
  to any file or log, and the browser forgets the patient when the tab closes or **New patient** is pressed.

If either of these stops being true (for example, the server is opened to the network, or answers are saved), accounts are needed
again.

---

## Windows (the RTX 2050 laptop)

### Step 1: install Python 3.12 and Git (internet on)

1. Download **Python 3.12** from https://www.python.org/downloads/windows/ (the "Windows installer (64-bit)").
   - In the first window, tick **"Add python.exe to PATH"**.
   - Then click **Install Now**.
2. Download **Git** from https://git-scm.com/download/win and install it with the default choices.
3. Open **Command Prompt** (Start menu → type `cmd`) and check both:
   ```bat
   py -3.12 --version
   git --version
   ```

### Step 2: install Ollama and download the model (internet on)

1. Download Ollama for Windows from https://ollama.com/download and install it. It starts by itself and shows a llama icon near
   the clock.
2. Download the model **once**. The tag is the `candidate_a` tag in `diacausal/llm/llm.yaml` (never type a different one):
   ```bat
   ollama pull qwen3:4b-instruct-2507-q4_K_M
   ollama list
   ```
   The download is about 2.5 GB.
3. **Record the model** in the table below, from `ollama list` (its ID) and the model's page on ollama.com (its licence). Fill in
   the Windows row.

| Field | Value seen on the Mac on 11 Oct 2026 | Windows laptop | Checked by (member, date) |
|---|---|---|---|
| Tag | `qwen3:4b-instruct-2507-q4_K_M` | | UNVERIFIED |
| ID (digest, first 12 characters) | `0edcdef34593` | | UNVERIFIED |
| Size | 2.5 GB | | UNVERIFIED |
| Licence | Apache-2.0 (as `llm.yaml` records from the Ollama model page) | | UNVERIFIED |
| Ollama version | 0.40.0 | | UNVERIFIED |

Everything in this table stays **UNVERIFIED** until a team member checks it against the model card and signs the last column.

### Step 3: get DiaCausal and its libraries (internet on)

```bat
cd %USERPROFILE%\Documents
git clone https://github.com/Rhian-Roy/DiaCausal-CDSS.git
cd DiaCausal-CDSS
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-engine.txt
```

This takes a few minutes. Nothing else needs the internet.

### Step 4: start it (Wi-Fi off from now on)

1. **Switch Wi-Fi off.**
2. Double-click **`scripts\start_clinic.bat`** in File Explorer.
3. A black window opens and says whether Ollama is running. After about a minute the browser opens at **http://127.0.0.1:8000/**.
4. **To stop DiaCausal, close the black window.**

If Windows asks whether Python may use the network, choose **Cancel / do not allow**. The server only needs this computer.

### Step 5: check it works offline

With Wi-Fi off:
1. The page opens. Under the header it shows the intended-use sentence and the bar "On this computer: answers are written by the
   local model qwen3:… " (or "by the template" if Ollama is not running).
2. **Patient Details** → **1 · Typical patient** → **Compare**: three options are compared.
3. Type **"Can SGLT2 inhibitors cause ketoacidosis?"** and press Enter. You get an answer card that ends with "The clinician
   decides." Above that line, it says who wrote it: the local model, or the template "because the local model's draft did not
   pass the checks".
4. Type **"Patient unconscious in OPD, which add-on?"**: the red **Emergency** notice appears, and nothing else.
5. **Investigate** → **Metformin and kidney function**: passages appear.

The first question after start-up can take longer, because the model is loading into memory.

---

## macOS

Steps 1 to 5 are the same, with these differences:

| Step | macOS |
|---|---|
| 1 | Python 3.12 from https://www.python.org/downloads/macos/ (or `brew install python@3.12`); Git comes with the Xcode command-line tools (`xcode-select --install`) |
| 2 | Ollama from https://ollama.com/download (drag it into Applications and open it once); then the same `ollama pull` and `ollama list` in Terminal |
| 3 | `python3.12 -m venv .venv` and `.venv/bin/python -m pip install -r requirements-engine.txt` |
| 4 | Double-click **`scripts/start_clinic.command`** in Finder. The first time, macOS may say it is from an unidentified developer: right-click it → **Open** → **Open**. Close the Terminal window to stop DiaCausal |

---

## Measure it on this laptop

With DiaCausal **stopped** (the script starts its own copy), and Ollama running:

```bat
.venv\Scripts\python.exe scripts\measure_local.py --machine rtx2050
```

On macOS, use `.venv/bin/python scripts/measure_local.py --machine <name>`.

This runs the 20 questions of `eval/llm_golden.csv` through `/api/v1/ask` and writes `results/local_llm_<machine>.csv`. For each
question it records:
- the total time, and the time of each layer;
- who wrote the answer;
- whether the template took over, and which output check failed.

At the end it adds the median and 95th-percentile times, the fallback rate and the start-up time. It never writes a question, an
answer or a patient value: only question IDs. Commit the file in a pull request.

---

## If something is wrong

| You see | What to do |
|---|---|
| ".venv is missing" | do step 3 |
| The bar says "by the template" though Ollama is installed | start Ollama (Windows: from the Start menu; macOS: open the app), check `ollama list` shows the tag, then reload the page |
| Every answer says the template took over (`GUARD_...`) | that is the output guards working: the model's draft failed a check. It is recorded, not an error |
| The first answer takes a long time, or falls back with `TIMEOUT` | the model was loading. Ask again; it stays loaded for 10 minutes |
| "address already in use" in the black window | another program uses port 8000 (for example the old chat app's backend). Close it, then start again |
| The page shows "Sign in" | you opened https://diacausal.netlify.app, not http://127.0.0.1:8000/ |

---

## For a hospital (later, with the hospital's IT team)

- Serve DiaCausal from an internal server (HTTPS on the intranet), behind the hospital's own sign-in. Never expose it to the internet.
- Replace the synthetic cohort with a de-identified local dataset only after ethics approval
  (`diacausal/causal_inference/cohort.py: load_dataset`), then rerun the benchmark and refit.
- Keep the licence rules: only sources the hospital may copy go into `knowledge_sources/corpus/`.
- The doctor stays in charge: decision support only, no doses, every number with its 95% range.
