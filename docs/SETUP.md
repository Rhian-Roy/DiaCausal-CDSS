# Setup for teammates (macOS, Windows, Linux)

About 15 minutes the first time. You need three tools, the code, one setup command and
one check command. Setup downloads libraries, so it needs internet; after that the app
runs offline (only the API documentation page, `/docs`, loads its look from the internet).

> No installing possible right now? Watch the demo on a teammate's laptop. (GitHub
> Codespaces is not set up for the chat app yet: the repo's `.devcontainer` is for the
> older Streamlit demo.)

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
The Windows commands below are for PowerShell or Command Prompt. In Git Bash, write every
path with forward slashes (`.venv/Scripts/python`).

**Linux only:** Ubuntu's own `nodejs` package is too old; install Node 24 from nodejs.org.

Check the three tools. Each should print a version:

| | macOS / Linux | Windows |
|---|---|---|
| Git | `git --version` | `git --version` |
| Python | `python3.12 --version` → `3.12.x` | `py -3.12 --version` → `3.12.x` |
| Node | `node --version` → `v24.x` (24.15 or newer) | `node --version` |

## 2. Get the code

```bash
git clone https://github.com/Rhian-Roy/DiaCausal-CDSS.git
```

```bash
cd DiaCausal-CDSS
```

All commands below are run from this `DiaCausal-CDSS` folder.

If there is no `scripts` folder, the chat app has not been merged into `main` yet. Switch to
its branch (ask Rhian for the name if it has changed):

```bash
git switch claude/diacausal-chatbot-setup-225ec7
```

## 3. One-time setup

It checks your Python and Node, makes the backend's private Python (`backend/.venv`)
and installs the libraries for both parts. Safe to run again — do so after a `git pull`
that changed `requirements` or `package-lock.json`, **after stopping both servers**
(on Windows running servers lock files that setup replaces).

| macOS / Linux | Windows |
|---|---|
| `python3.12 scripts/setup.py` | `py -3.12 scripts/setup.py` |

It also downloads the **speech-to-text model** (about 145 MB, once per computer) and
makes **`backend/.env`**, which holds the secret key that encrypts everyone's
authenticator secrets. It is never committed and never overwritten; keep it (losing it
means everyone must set up their authenticator app again).

It ends with `Setup finished.` Lines starting with `npm warn` (on a Mac, one about
`fsevents`) are harmless; only a line starting with `[FAIL]` needs action.

## 4. Check that everything works (one command)

| macOS / Linux | Windows |
|---|---|
| `python3 scripts/check_all.py` | `py scripts/check_all.py` |

It runs every automated test, then starts the real app on spare ports and sends real
messages through it. It should end with:

```
ALL 34 CHECKS PASSED
```

What each check proves, and what to do if one fails: [TESTING.md](TESTING.md).

## 5. Try it yourself

### 5a. Create the first admin account (once per computer)

Every person has their own account; there is no shared login and no "sign up" button.
The whiteboard's **master login** is an **admin** account: a person who can create,
disable, unlock and reset other accounts. Make the first one:

| macOS / Linux | Windows |
|---|---|
| `python3 scripts/create_admin.py your.id "Dr Your Name"` | `py scripts/create_admin.py your.id "Dr Your Name"` |

Run it in a **real terminal window** (Terminal or iTerm). It asks for a password twice;
typing shows nothing, which is normal. At least 12 characters — a short sentence works
well. There is no default password anywhere, and it works only while there is no admin yet.

An editor's built-in console has no real terminal, so the hidden prompt cannot work there;
the script says so and suggests
`echo 'the password' | python3 scripts/create_admin.py USER_ID "Name" --password-stdin`
(that leaves the password in your shell history, so change it afterwards).

### 5b. Start the two servers

Two terminal windows, both in the `DiaCausal-CDSS` folder.

**Terminal 1 — the backend (Python):**

| macOS / Linux | Windows |
|---|---|
| `cd backend` then `.venv/bin/python -m uvicorn app.main:app --reload --port 8000` | `cd backend` then `.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000` |

**Terminal 2 — the frontend (the page):**

`cd frontend` then `npm run dev`. **Windows PowerShell:** if it says `npm.ps1 cannot be
loaded because running scripts is disabled`, type `npm.cmd run dev` instead (or use
Command Prompt).

### 5c. Sign in (use Chrome)

Open **http://localhost:5173** in **Chrome** (the sign-in cookie is marked *Secure*;
Chrome accepts that on `localhost`, Safari may not), then the browser's console:
**⌥⌘J** (Chrome, Mac), **Ctrl+Shift+J** (Chrome, Windows/Linux), or F12 → Console.

1. **Step 1:** your user ID, your password, and the 6 digits in the picture
   (**Play audio** reads them out; **New image** gives another). Click **Sign in**.
   Console: `login input passed`, `captcha passed`, `password passed`.
2. **First time only — set up your authenticator app** (design 06): on your phone install
   **Google Authenticator** (or Microsoft Authenticator). Tap **+** → **Scan a QR code**,
   point the camera at the QR code on the screen. The app now shows **DiaCausal** with a
   6-digit number that changes every 30 seconds. Type the number shown now and click
   **Confirm and finish setup**. (No camera? Tap **+** → **Enter a setup key** and type the
   key shown in groups of 4; type: time based.)
3. **Every later time:** step 2 asks for the 6-digit code from the app.
4. **First time only:** read "How to use DiaCausal", tick **I understand**, **Continue**.

Console: `mfa passed`. Your name and **Sign out** appear top right. After 13 minutes
without activity a box warns you; at 15 minutes you are signed out and the conversation is
cleared from the screen.

Type a question and press **Enter**. You should see four lines that start with the same
8-character ID, the dummy reply in the chat, and the same ID on 8 lines in terminal 1.
Stop either server with **Ctrl+C**.

### 5d. Accounts for the rest of the team (admins only)

Each admin action asks for **your** admin password and your current 6-digit code, and is
written to the audit log.

```bash
python3 scripts/admin.py --as your.id create-user dr.mehta "Dr Mehta"            # a clinician
python3 scripts/admin.py --as your.id create-user dr.shah "Dr Shah" --role admin  # another admin
python3 scripts/admin.py --as your.id unlock dr.mehta       # after 5 wrong tries (or wait 15 minutes)
python3 scripts/admin.py --as your.id reset-mfa dr.mehta    # lost phone: sets up the app again
python3 scripts/admin.py --as your.id disable dr.mehta      # and: enable
python3 scripts/admin.py --as your.id list
```

(Windows: `py` instead of `python3`.) The new person signs in with the password you set
and sets up their own authenticator app on first sign-in.

## 6. Working together

- Ask Rhian to add you on GitHub (repo **Settings → Collaborators**) so you can push.
- Get the latest code: `git pull`
- One branch per task: `git switch -c login-page` (any short name)
- Before you push, run the check from step 4 — everything should pass.
- Share your work: `git push -u origin login-page`, then on GitHub click
  **Compare & pull request** and ask a teammate to review.
- GitHub runs the same check automatically on Linux, Windows and macOS for every push
  and pull request (the **Actions** tab). A green tick means all three passed; a red cross
  means click it and read the `[FAIL]` line.
- Found a problem? Report it with the **trace ID** (shown under each answer and in the
  console) — see [TESTING.md, part 5](TESTING.md#part-5--reporting-a-problem).

The project's working rules (what the API accepts, what must be logged, where new
pieces go) are in [`CLAUDE.md`](../CLAUDE.md). How it all works:
[docs/explain/01-walking-skeleton.md](explain/01-walking-skeleton.md).
