# Setup for teammates (macOS, Windows, Linux)

About 15 minutes the first time. You need three tools, the code, one setup command and
one check command. Nothing here needs an internet connection once it is installed.

> DiaCausal is a research prototype for clinician evaluation; not a marketed medical
> device; not for unsupervised clinical use.

## 1. Install the tools (once per computer)

| Tool | Why | macOS ([Homebrew](https://brew.sh)) | Windows (PowerShell or Command Prompt) | Linux (Ubuntu 24.04) |
|---|---|---|---|---|
| Git | download the code, share changes | `brew install git` | `winget install Git.Git` | `sudo apt install git` |
| Python **3.12** | runs the backend | `brew install python@3.12` | `winget install Python.Python.3.12` | `sudo apt install python3.12 python3.12-venv` |
| Node.js **24 LTS** | runs the frontend | `brew install node@24` (then the PATH line below) | `winget install OpenJS.NodeJS.LTS` | from [nodejs.org](https://nodejs.org) (LTS) |

**macOS only:** Homebrew keeps `node@24` off your PATH, so add it once, then open a new
terminal window:

```bash
echo 'export PATH="/opt/homebrew/opt/node@24/bin:$PATH"' >> ~/.zshrc
```

(On an older Intel Mac the path is `/usr/local/opt/node@24/bin` instead.)

**Windows only:** after installing, close and reopen the terminal so it finds the new tools.

Check the three tools. Each should print a version:

| | macOS / Linux | Windows |
|---|---|---|
| Git | `git --version` | `git --version` |
| Python | `python3.12 --version` → `3.12.x` | `py -3.12 --version` → `3.12.x` |
| Node | `node --version` → `v24.x` (20.19 or newer works) | `node --version` |

## 2. Get the code

```bash
git clone https://github.com/Rhian-Roy/DiaCausal-CDSS.git
```

```bash
cd DiaCausal-CDSS
```

All commands below are run from this `DiaCausal-CDSS` folder.

## 3. One-time setup

It checks your Python and Node, makes the backend's private Python (`backend/.venv`)
and installs the libraries for both parts. Safe to run again (do so after a `git pull`
that changed `requirements` or `package-lock.json`).

| macOS / Linux | Windows |
|---|---|
| `python3.12 scripts/setup.py` | `py -3.12 scripts\setup.py` |

It ends with `Setup finished.`

## 4. Check that everything works (one command)

| macOS / Linux | Windows |
|---|---|
| `python3 scripts/check_all.py` | `py scripts\check_all.py` |

It runs every automated test, then starts the real app on spare ports and sends real
messages through it. It should end with:

```
ALL 21 CHECKS PASSED
```

What each check proves, and what to do if one fails: [TESTING.md](TESTING.md).

## 5. Try it yourself

Two terminal windows, both in the `DiaCausal-CDSS` folder.

**Terminal 1 — the backend (Python):**

| macOS / Linux | Windows |
|---|---|
| `cd backend` then `.venv/bin/uvicorn app.main:app --reload --port 8000` | `cd backend` then `.venv\Scripts\uvicorn app.main:app --reload --port 8000` |

**Terminal 2 — the frontend (the page):**

`cd frontend` then `npm run dev` (same on every system).

Open **http://localhost:5173**, then the browser's console:
**⌥⌘J** (Chrome, Mac), **Ctrl+Shift+J** (Chrome, Windows/Linux), or F12 → Console.
Type a question and press **Enter**. You should see four lines that start with the same
8-character ID, the dummy reply in the chat, and the same ID on 8 lines in terminal 1.
Stop either server with **Ctrl+C**.

## 6. Working together

- Ask Rhian to add you on GitHub (repo **Settings → Collaborators**) so you can push.
- Get the latest code: `git pull`
- One branch per task: `git switch -c login-page` (any short name)
- Before you push, run the check from step 4 — everything should pass.
- Share your work: `git push -u origin login-page`, then on GitHub click
  **Compare & pull request** and ask a teammate to review.
- Found a problem? Report it with the **trace ID** (shown under each answer and in the
  console) — see [TESTING.md, part 5](TESTING.md#part-5--reporting-a-problem).

The project's working rules (what the API accepts, what must be logged, where new
pieces go) are in [`CLAUDE.md`](../CLAUDE.md). How it all works:
[docs/explain/01-walking-skeleton.md](explain/01-walking-skeleton.md).
