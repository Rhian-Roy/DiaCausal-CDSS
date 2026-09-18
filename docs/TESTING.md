# How to know everything works

Three layers: **one command** checks almost everything automatically (part 1), a
**10-minute by-eye check** covers what only a person can judge (part 2), and part 3 says
honestly what is **not** tested yet. Part 4 fixes common problems; part 5 is how to
report one.

## Part 1 — the one command

| macOS / Linux | Windows |
|---|---|
| `python3 scripts/check_all.py` | `py scripts\check_all.py` |

(First time on a computer? Do the setup in [SETUP.md](SETUP.md) first.)

It takes a few seconds and prints `[PASS]` or `[FAIL]` per line, ending with
`ALL 21 CHECKS PASSED`. It starts its own copy of the app on spare ports, so it does
not disturb servers you already have running.

### Which check proves which requirement

| Requirement | Proved by |
|---|---|
| Press Enter → console prints `input passed`, `ui guard passed`, `medical ui guard passed`, `output passed`, all with the same trace ID | Section 3: frontend test *"prints the four console lines with one trace ID and shows the reply"* (`frontend/src/pages/ChatPage.test.tsx`). By eye: part 2, step 2. |
| An empty message is blocked | Section 3 (browser side, never sent) and section 6 *"an empty message is blocked by backend_guard"* (server side) |
| The message goes to the Python backend through the API and a dummy reply comes back | Section 6 *"a question gets the dummy reply"*; section 7 *"a message sent via the page's /api reaches the backend"* |
| The reply appears in the chat | Section 3 (the page test finds the reply on screen). By eye: part 2, step 4. |
| The backend log prints the same trace ID | Section 6 *"backend log shows [id] on the request, every stage and the reply"*; backend tests in `backend/tests/test_logging.py` |
| Accept only `{"schema_version":"1.0","client_trace_id":…,"parts":[…]}` | Section 2: `backend/tests/test_validation.py` (20+ cases) |
| Unknown part types and text over 8000 characters are refused with a clear message | Section 2 and section 6 (*"image" part refused*, *over 8000 refused*) |
| Six stages in order; only the first and last run, the rest `skipped` | Section 2 (`test_chat.py`, `test_pipeline.py`) and section 6 |
| Message text never written to the log | Section 2 (`test_message_text_is_never_logged`) and section 6 |
| The code type-checks, builds and has no lint problems | Sections 4 and 5 |
| Colours, fonts, layout match `design/` | By eye only: part 2, steps 1 and 7 |

**Are the tests themselves any good?** They were checked by *mutation testing*:
reviewers deliberately broke the code in dozens of small ways (skip a console line,
reorder the stages, stop trimming, let an empty message through, …) and confirmed the
tests fail each time. Every test that failed to notice a break was fixed.

You can also run the parts separately:

| What | Command (from the repo root; Windows: `.venv\Scripts\python`) |
|---|---|
| Backend tests | `cd backend` then `.venv/bin/python -m pytest -v` (`-v` lists every test by name) |
| Frontend tests | `cd frontend` then `npm test` |
| Type-check + build | `cd frontend` then `npm run build` |
| Lint | `cd frontend` then `npm run lint` |

## Part 2 — check by eye in a real browser (about 10 minutes)

Start both servers as in [SETUP.md, step 5](SETUP.md#5-try-it-yourself), open
http://localhost:5173 and the browser console. Put the browser and the backend
terminal side by side.

| # | Do | You should see |
|---|---|---|
| 1 | Look at the page next to `design/chat-desktop.png` | Dark pine-green top bar, serif "DiaCausal", "RESEARCH PROTOTYPE" badge, bold patient line with an "Example data" chip, a white message box with a mic and a green arrow button, the disclaimer under it |
| 2 | Type `HbA1c 8.4% on metformin. What should I add?` and press **Enter** | Console: four lines `[xxxxxxxx] input passed`, `… ui guard passed`, `… medical ui guard passed`, `… output passed` — the same 8 characters on each |
| 3 | Look at terminal 1 | Eight lines with that same `[xxxxxxxx]`: request received, six stages, reply sent. Your question's words do **not** appear |
| 4 | Look at the chat | "YOU ASKED" + your question; a white card "DIACAUSAL ANSWERED" with the dummy reply, "2 of 6 stages ran; the others are not built yet", and "Trace ID xxxxxxxx" matching the console |
| 5 | Press **Enter** on an empty box | "Type a question first." under the box; console shows `input passed` then a yellow warning `ui guard blocked`; nothing new in terminal 1 |
| 6 | Type a line, press **Shift+Enter**, type another | A new line in the box; nothing is sent |
| 7 | Open the device toolbar (**⌘⇧M** Mac / **Ctrl+Shift+M** Windows, with the console open), pick an iPhone | Compare with `design/chat-phone.png`: "PROTOTYPE" badge, short patient line, "Ask a question" placeholder |
| 8 | Press **Tab** until the green send button is selected | A thick pine-green outline around it (keyboard users can see where they are) |
| 9 | Stop terminal 1 (**Ctrl+C**), then send a question | Red box "Couldn't get a reply … Check that the backend is running." Start terminal 1 again afterwards |
| 10 | Open http://localhost:8000 | The API's own documentation page (`/docs`); **POST /api/v1/chat → Try it out → Execute** sends a request by hand |

## Part 3 — what is not tested yet (and why)

| Not tested | Why |
|---|---|
| Login, MFA, CAPTCHA, database, Docker, voice | Not built yet; each has a README where it will go (see `CLAUDE.md`) |
| The four clinical stages (guardrails, causal engine, RAG, LLM) | Not connected yet; they return `skipped` |
| Foul-language blocking with real words | The mechanism works and is tested with a made-up word; the agreed list is still empty |
| Every browser | Automated page tests run in a simulated browser (jsdom). Tried by hand in Chrome/Chromium. Safari's special keyboard behaviour for Hindi/Japanese input is covered by a simulated test only |
| Windows and Linux setup | `scripts/setup.py` and `scripts/check_all.py` are written for all three, but have been run on macOS only so far — tell the team if something differs on your computer |

## Part 4 — when something fails

| You see | Why | Fix |
|---|---|---|
| `command not found: python3.12` / `No suitable Python runtime found` | Python 3.12 not installed | [SETUP.md step 1](SETUP.md#1-install-the-tools-once-per-computer) |
| `[FAIL] backend Python is 3.12 (found: none…)` or `vitest: command not found` | Setup not done in this folder | `python3.12 scripts/setup.py` (Windows `py -3.12 scripts\setup.py`) |
| `Node.js … too old` / `node: command not found` | Old or missing Node | Install Node 24 LTS, open a new terminal |
| Windows: `npm.ps1 cannot be loaded because running scripts is disabled` | PowerShell's script policy | Use **Command Prompt** instead of PowerShell, or type `npm.cmd` instead of `npm` |
| `Port 5173 is already in use` / `address already in use` (8000) | Another copy is already running — another terminal, or an app's preview | Stop the other one (**Ctrl+C** in its terminal), or just use it |
| Page shows *Couldn't reach the DiaCausal server* or *HTTP 500* | Backend (terminal 1) not running or crashed | Start or restart terminal 1; read its last lines |
| Console shows none of the four lines | Console filter hides them, or wrong tab | Console level **Default** / **All levels**, clear the filter box |
| Tests fail right after `git pull` | Someone added a library | Run the setup script again |
| Anything else | | Report it (part 5) |

## Part 5 — reporting a problem

Tell the team (or open a GitHub issue):

1. What you did (the steps) and what you expected.
2. What happened instead — a screenshot of the page **and** the console.
3. The **trace ID** (8 characters, under the answer and on every console line), and the
   lines from the backend terminal that contain it.
4. Your system (macOS/Windows/Linux) and the output of `python3 scripts/check_all.py`.

With the trace ID anyone can find exactly what the backend did with that message.
