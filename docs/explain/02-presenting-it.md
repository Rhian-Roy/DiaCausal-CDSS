# 02 — Presenting it: pitch, demo and answers to likely questions

Read [01-walking-skeleton.md](01-walking-skeleton.md) first: it explains what happens
when you press Enter. This page helps you **say** it: short pitches, an everyday
analogy, a demo script, answers to the questions guides, examiners and mentors usually
ask, a glossary and a code tour.

> DiaCausal is a research prototype for clinician evaluation; not a marketed medical
> device; not for unsupervised clinical use.

**Golden rules when answering**

1. Say what it does **today**, what it will do **later**, and **where the code is**.
2. Never make it sound bigger than it is. "Not built yet" is a good answer — it shows
   you know exactly where the edges are.
3. If you don't know: "Good question — here is where that lives", open the file (see the
   [code tour](#code-tour)), and read it together. Never guess.

## The 30-second version

> "This is the first working slice of DiaCausal. A doctor types a question on the chat
> page. The page checks it, labels it with a short tracking ID and sends it to our
> Python server. The server checks the format, then runs a six-stage pipeline. Today
> only the simple checks at the start and the end run — is the message or reply empty,
> does it contain a blocked word — and the four clinical stages in the middle are
> marked *not built yet*, so a fixed test reply comes back. The same tracking ID appears
> in the browser console and on every server log line, so we can follow any message end
> to end. Next, our causal engine and guideline search plug into those marked stages."

## The 2-minute version (for guides)

1. **The goal.** DiaCausal aims to help doctors choose second-line diabetes treatment
   for adults already on metformin, using causal inference (what is *likely to cause* a
   better result for *this* patient), hard clinical safety rules and cited guidelines.
2. **Why this slice first.** Before any clever model, we built a *walking skeleton*: the
   whole route from the chat page to the server and back, with a dummy answer. Joining
   the pieces is where projects usually break, so we did it first, while it is simple.
3. **What works today.** The chat page matches our design. Browser checks block empty or
   over-long messages. The API accepts only a precise message format and rejects
   anything else with a clear explanation. A six-stage pipeline runs, with basic guard
   checks at both ends (not empty, no blocked word); there is **no clinical safety check
   yet**. Every step carries one trace ID.
4. **How we know.** One command, `python3 scripts/check_all.py`, runs all 103 automated
   tests (308 backend, 203 frontend), the type-check, build and lint, then starts the real
   servers and tests them live. It prints 34 pass/fail lines, all passing. GitHub runs the
   same check on Linux, Windows and macOS for every push.
5. **What's next.** Login with MFA and CAPTCHA; the real blocked-word list; then
   connecting our existing research code — guardrails, causal engine, guideline
   retrieval — into the marked stages.

## An everyday analogy (for non-technical listeners)

Think of a **hospital courier with tracking numbers**.

- You write a note (the question) at the **front desk** (the chat page). The desk
  checks it isn't blank or too long (**UI guards**) and stamps a **tracking number** on
  it (the **trace ID**).
- The note goes to the **back office** (the Python backend). The back door checks it
  *again* (**backend guard**) — because people can walk in through the back door without
  passing the front desk.
- Inside, the note moves along a **conveyor with six stations**. Four stations have a
  sign *"under construction"* (**skipped**). The last station looks at the reply before
  it leaves (**output guard**).
- The reply comes back with the same tracking number, and the front desk **checks the
  number matches** before handing it over (**output check**).
- Every station writes the tracking number in its logbook — but **never copies the
  note's contents** (privacy).

## The live demo (about 5 minutes)

**Before you start:** start both servers ([SETUP.md, step 5](../SETUP.md#5-try-it-yourself)),
open http://localhost:5173 and the browser console, and put the browser and the backend
terminal side by side. Zoom the browser to 125–150% so people at the back can read.
The chat page needs **no internet** — everything runs on your laptop. Only step 6 (the
`/docs` page) loads its look from the internet; if the room has no Wi-Fi, do step 6 with
the `curl` command from [01](01-walking-skeleton.md#when-it-does-not-go-to-plan) instead.
As a backup, keep a screenshot of the page and of a passing `check_all` run.

| # | Do | Say |
|---|---|---|
| 1 | Show the page | "This follows our design: large readable fonts, the patient summary marked *Example data*, and the disclaimer under the message box." |
| 2 | Type `Established coronary disease, HbA1c 8.4% on maximum metformin. What should I add?` → **Enter** | "Watch the console: four lines — input passed, UI guard, medical UI guard, output passed — all starting with the same 8-character ID." |
| 3 | Point at the backend terminal | "The server printed the same ID on eight lines: request received, each of the six stages, reply sent. My question's words are not in the log — only its length." |
| 4 | Point at the answer card | "The reply is a fixed test text for now. The grey box shows which stages ran: two of six. The ID under it matches the console." |
| 5 | Press **Enter** on an empty box | "Empty messages are blocked in the browser — nothing reaches the server. The server also blocks them, in case someone skips the page." |
| 6 | Open http://localhost:8000 → **POST /api/v1/chat → Try it out**; in the example body change `"type": "text"` to `"type": "image"`; **Execute** | "The API refuses anything outside the contract with a message a person can read: *Part 1 has type "image", which this API does not accept.*" |
| 7 | Run `python3 scripts/check_all.py` | "One command runs all 511 tests, the build and lint, then starts the real app and tests it live: 34 lines, all passing." |
| 8 | Close | "Next: login with MFA and CAPTCHA, then our causal engine plugs into its stage." |

## Questions you may be asked — with answers

### A. The big picture

**1. What is DiaCausal?**
A clinical decision support prototype for type 2 diabetes. For an adult already on
metformin whose sugar is still high, it aims to suggest which medicine class to add,
with the reasoning, safety checks and guideline citations. It is for research evaluation
by clinicians, not for use on patients without supervision.

**2. What does this version actually do?**
It carries a question from the chat page to the backend and back, through the basic
input checks (empty, too long, wrong format) and all six pipeline stages, and shows a
*fixed test reply*. It gives **no** clinical advice yet. The page, the API, the tracing
and the tests around the future advice are real.

**3. Why build a "walking skeleton" with a dummy reply instead of the model first?**
Connecting the parts is where projects usually fail late. With the skeleton working,
every later feature fills one clearly marked slot and can be tested end to end the day it
is added. It also fixed the message format early, so frontend and backend work can go
on in parallel.

**4. Is this a medical device? Is it safe to use on patients?**
No. It is a research prototype for clinician evaluation; not a marketed medical
device; not for unsupervised clinical use. That sentence is on the page and inside
every chat reply from the API. Today's reply is a fixed test text, and the page says so.

**5. Who is it for?**
Clinicians evaluating the prototype. That is why the design uses large, highly legible
fonts and plans clear green/amber/red boxes for safety information.

### B. How it works

**6. What happens when I press Enter?**
Three checks in the browser (input, UI guard, medical UI guard), then the message is sent
to the Python backend as JSON. The backend checks the format, runs six stages (two
simple checks, four not built yet), adds a test reply, and sends everything back. The
browser checks the reply belongs to this message and shows it. Details: [01](01-walking-skeleton.md).

**7. What is an API here, exactly?**
A fixed address on the server, `POST /api/v1/chat`, that accepts one precise JSON format
and returns another. The format is written down in `backend/app/schemas.py`, and
FastAPI publishes live documentation of it at http://localhost:8000/docs.

**8. What does the request look like?**
`{"schema_version":"1.0","client_trace_id":"a1b2c3d4","parts":[{"type":"text","text":"…"}]}`
— a version number, the trace ID, and a list of typed parts (today only text).

**9. What are the six stages, and why are four "skipped"?**
`backend_guard` (runs), `clinical_guardrails`, `causal_engine`, `rag_retrieval`,
`llm_explanation` (all four *not built yet*), `output_guard` (runs). Listing all six
from day one fixes the list of stages that every reply carries, and it is honest: the
doctor can see no clinical reasoning happened.

**10. Why does a blocked message come back with HTTP 200, but a bad request with 422?**
422 means the *request* broke the contract (wrong field, unknown part type, bad trace
ID) — a mistake by whoever sent it; the reply explains it (`backend/app/errors.py`). A
blocked message is a *valid* request that the pipeline decided not to answer — a normal
result — so it gets 200 with `"outcome": "blocked"`, the reason, and all six stages
(`backend/app/pipeline/runner.py`). A test checks this (`backend/tests/test_pipeline.py`).

**11. What is the trace ID and why is it made in the browser?**
A random 8-character label for one message (like `efc1a658`). Made at the very start, it
can label every step: the four console lines, every backend log line, the response
header and the note under the answer. If a clinician says "this answer looks wrong",
the ID finds the whole story in the logs — without the logs storing what they typed.

**12. Can two messages get the same trace ID?**
It has 8 hexadecimal characters, about 4.3 billion possible values, and log lines also
carry the time, so for a prototype a mix-up is very unlikely. The backend accepts IDs up
to 64 characters, so it can be made longer later without changing the API. It is a
debugging label, not a security token: the backend checks its format, not that it is
unique.

**13. If two doctors send at the same moment, can the log mix up their IDs? Does it scale?**
Each request keeps its ID in its own "context variable" (`backend/app/tracing.py`), and
every request gets a fresh pipeline context, so requests don't share state. During the
review, hundreds of requests were sent in parallel and every log line carried the right
ID — but that is not part of the automated tests. Today it is one server process on one
laptop with no load testing; running several processes behind a web server is part of
the Docker plan.

**14. Does it remember my earlier messages, so I can ask a follow-up?**
No. Each Enter sends only that message (`frontend/src/lib/api.ts`), and the backend keeps
nothing. The conversation on screen lives only in the page's memory
(`frontend/src/hooks/useChat.ts`) and disappears on refresh. Follow-ups need conversation
context, which isn't designed yet; the list-of-parts format and `schema_version` leave
room for it.

**15. Why does the page call `/api/...` and not the backend's port directly?**
Browsers follow the *same-origin policy*: a page may only read replies from its own
origin (scheme + host + port — so `localhost:5173` and `localhost:8000` are different
origins). A server can allow exceptions with *CORS* headers. In development Vite forwards
`/api` to the backend, so the page only ever talks to its own origin and we need no CORS
setup. In production a web server will do the same forwarding (see `docker/README.md`).

### C. Safety, security and privacy

**16. Where does what I type go? Is it stored, or sent to the internet or a cloud AI?**
Today nothing leaves your laptop and nothing is saved. The page sends the text only to
its own address; Vite passes it to the backend on the same computer; the backend makes no
outside calls (its only libraries are FastAPI, uvicorn and Pydantic) and has no database.
The log keeps only the ID, sizes and stage results. Still, **don't type real patient
names or numbers**: the check meant to catch them is a stub. Before any real patient data
is used, we must decide whether the future language model runs locally or in the cloud,
and get the institute's ethics approval.

**17. Why check the message twice — in the browser and on the server?**
They do different jobs. The browser check gives instant feedback and saves a wasted
request. But anyone can send requests straight to the API (for example with curl), so
the browser can't be trusted to enforce anything — the server check is the one that
counts.

**18. Then why is the medical check (patient identifiers, emergencies) only in the browser?**
Fair point: today it is only a stub in the browser (`medicalUiGuard` in
`frontend/src/lib/guards.ts`), and the server has no matching check yet. When those
checks are written, they must also run on the server (in `backend_guard` or
`clinical_guardrails`), exactly as the empty-message check and blocked-word list already
run on both sides. The browser copy is only for instant feedback.

**19. What about foul language?**
The blocking works on both sides and is tested with a made-up word. The real word list
is still empty — the team will add it in `frontend/src/lib/guards.ts` and
`backend/app/pipeline/blocklist.py`. It matches whole words only, so "assess" is not
blocked by a word inside it.

**20. What does the "medical UI guard" check?**
Today nothing — it is a stub that lets everything through, and the code says so.
Planned: patient identifiers typed into the box (names, phone or Aadhaar numbers),
emergencies (tell the user to get help instead), and questions outside the tool's scope.

**21. Why is the message text never logged?**
In real use a question could contain patient details, and logs are copied, shared and
kept for a long time. So the backend logs only the trace ID, sizes and stage results.
Tests check that the text never appears in the log.

**22. How is the backend protected against bad or hostile input?**
Pydantic checks every request against the contract before our code runs. Unknown
fields, unknown part types, text over 8,000 characters, more than 20 parts, or a badly
formed trace ID are refused with HTTP 422 and a plain-English reason. Anything the
client sent is echoed back only short and escaped, so it can't flood the reply, crash
it, or forge extra lines in the log (all three are tested).

**23. Who can reach the API? What stops someone from flooding it?**
Today both servers listen only on your own laptop (uvicorn's and Vite's defaults), so
other computers can't reach them. Each message is capped at 8,000 characters per part
and 20 parts. There is no login, rate limit or overall request-size limit yet — fine for
a local prototype, not for a network. The plan: login in front of the chat endpoint,
rate limiting and lockout (`backend/app/auth/README.md`), and a web server that exposes
only `/api` (`docker/README.md`).

**24. Where is the login with ID, password, MFA and CAPTCHA?**
Not built yet, on purpose: the first slice proves the route works. The plan is written
in `backend/app/auth/README.md` and `frontend/src/features/auth/README.md`: CAPTCHA, then
password (stored only as a hash), then the 6-digit code, then a secure session cookie;
the chat API will then answer only signed-in clinicians.

**25. Later, what stops a wrong or harmful answer from reaching a doctor?**
Several layers, most not built yet: clinical guardrails (hard rules such as
kidney-function thresholds) that override any statistical estimate; the output guard,
which will also check the reply's content; the browser's output check; the disclaimer;
and the clinician, who makes the decision.

### D. The clinical and causal side

**26. Does it use the patient details at the top (HbA1c 8.4%, eGFR 62)?**
No. That line is fixed example data from the design and is never sent
(`frontend/src/components/chat/PatientStrip.tsx` says so); only the typed text is sent.
The research engine does need structured values — `recommend(patient)` in
`causal_engine/cdss.py` reads age, BMI, starting HbA1c, eGFR, heart disease and kidney
disease (`COVARIATES` in `causal_engine/data.py`). How those reach the API isn't decided
yet; most likely a new structured part type holding the patient record, confirmed by the
clinician rather than guessed from free text.

**27. What data is the causal model trained on, and which drugs does it compare?**
The research engine in `causal_engine/` is not connected to the chat yet. It learns from
a *synthetic* cohort we generate (`causal_engine/data.py`), where we plant the true
effect for every patient so we can check which method recovers it — impossible on real
data, where the true individual effect is never observed. Today it compares one choice: an
SGLT2 inhibitor vs metformin, using the X-learner by default (`causal_engine/cdss.py`).
**v1.0 scope, due 30 October, is the three-drug add-on decision** — SGLT2 inhibitor vs
DPP-4 inhibitor vs sulfonylurea, on top of metformin (`docs/prompts/06-causal-engine.md`).
What stays future work is validation on real patients: the engine has not been fitted or
checked on any real cohort, which is exactly what the clinician evaluation is for.

**28. Which language model (LLM) do you use, and how will you stop it inventing a drug or a dose?**
None yet: `backend/app/pipeline/llm_explanation.py` returns *skipped*, and no model is
installed. The design rule in that file is "a language model explains; it does not
decide": the ranking comes from the causal engine, hard vetoes from the guardrails, and
facts from retrieved guideline passages; the model only puts those into words, and the
output guard is planned to withhold any dose without a guideline citation. The research
code today writes its explanation from a fixed template, not a model
(`causal_engine/cdss.py`, `format_card`). Local or cloud model is still open — it matters
for privacy.

**29. How exactly will the causal engine plug in?**
Its stage is one file, `backend/app/pipeline/causal_engine.py`, whose `run` function
returns *skipped* today. It will call our research code and return *passed* or
*blocked*, and the page shows that status with no change. The ranking itself, and later
the citations, will need a new reply part type in `schemas.py` and `contract.ts`, with
the page's output check and answer card updated to show it. Because replies are lists
of typed parts, that is an addition, not a rewrite.

### E. Technology choices

**30. Why React + Vite + TypeScript?**
React is the most widely used way to build interactive pages, so help and examples are
easy to find. Vite starts instantly and reloads on every save. TypeScript catches
mistakes like a wrong field name before the page runs — the build fails instead of the
doctor's screen.

**31. Why Tailwind and shadcn/ui?**
Tailwind lets us put the design's exact colours, fonts and spacing in one place
(`frontend/src/index.css`) and use them by name (`bg-pine`). shadcn/ui gives ready-made,
accessible components (button, text box) whose code is copied into our project, so we
can change them freely.

**32. Why FastAPI + Pydantic, and why Python?**
Our causal engine and research code are already Python, so the backend can call them
directly. FastAPI turns a Python function into a web API and writes the interactive
documentation for us. Pydantic checks every request against our models; that is how the
strict contract is enforced.

**33. The repo already has a Streamlit demo. Why a separate React app and API?**
Streamlit is great for our own analysis demos. For clinicians we need our own design,
login, and a stable API that other clients (a mobile app, an evaluation harness) can
use. Separating the page from the API also lets us test each on its own.

**34. Why `schema_version` and a list of `parts`?**
`parts` lets new kinds of input (an image, an audio clip, a patient record) be added as
new part types without changing the shape of a message. `schema_version` lets us change
the contract deliberately later, with client and server saying which version they speak.

**35. The notes say "we don't know what data types may come in the future" — so why reject unknown types?**
Because the list of typed parts is what makes future types easy to *add*. What we refuse
is *silently accepting* something we can't handle: for a clinical tool, a clear "type
image is not supported yet" is far safer than quietly ignoring an attached lab report.

### F. Testing and quality

**36. How do you know it works?**
`python3 scripts/check_all.py` runs the 308 backend and 203 frontend tests, the
type-check, build and lint, then starts the real backend and page and sends real
messages through them — 34 pass/fail lines. We also checked it by hand in a browser
([TESTING.md, part 2](../TESTING.md#part-2--check-by-eye-in-a-real-browser-about-10-minutes)).

**37. What kinds of tests are these?**
*Unit tests* check one piece alone (e.g. the UI guard with an empty text). *API tests*
send requests to the backend in memory and check the replies. The *page test* runs the
real React page in a simulated browser (jsdom) against a fake backend: it types a
question, presses Enter, and requires exactly the four console lines with one ID. The
*live checks* start the real servers and talk to them over the network.

**38. How do you know the tests are good enough?**
During development, AI review agents working under our direction deliberately broke the
code in small ways (drop a console line, reorder stages, let an empty message through)
and checked that a test failed each time. Where none did, we added one: backend went
from 46 to 53 tests, frontend from 41 to 49. That is mutation testing done by hand; we
have not run a mutation-testing tool (mutmut, Stryker), so there is no mutation score
yet — a possible next step.

**39. Is there a real end-to-end test? How do the frontend and backend stay in agreement?**
The contract is written twice, `backend/app/schemas.py` and `frontend/src/lib/contract.ts`,
and kept in sync by hand (a rule in `CLAUDE.md`). The page tests use a fake backend, so
they would not notice if only one side changed; `check_all` section 6 checks the real
backend's replies, which catches some drift. The real page with the real backend in a
real browser was checked by hand only. Next steps: a browser-automation test
(Playwright), or generating the TypeScript types from FastAPI's `/openapi.json`.

**40. Who makes sure the checks pass — do you have CI?**
Yes: `.github/workflows/check.yml` runs the same setup and `check_all` on Linux, Windows
and macOS for every push and pull request, and shows a green tick or red cross on
GitHub. The team rule is to merge only green pull requests after a review; GitHub can
also be set to block merging until the check passes.

**41. What is not tested?**
Things that don't exist yet (login, database, voice, Docker, the four clinical stages),
the real page with the real backend automatically (by hand only), and browsers other
than Chrome (Safari's keyboard quirk is tested in simulation). Windows and Linux are
tested by the GitHub check, not by hand.

### G. Design and usability

**42. Why these fonts and colours?**
The body font, Atkinson Hyperlegible, was designed by the Braille Institute to keep
letters like I/l/1 and O/0 easy to tell apart — important when reading doses and lab
values quickly. Headings use a serif (Source Serif 4). Safety states will use green,
amber and red boxes, each with an icon and a word, so colour is never the only signal.

**43. Why is "Example data" shown even on phones, when the phone design leaves it out?**
So example values can never be mistaken for a real patient. It was a deliberate,
safety-first change from the mock-up.

**44. Is it accessible?**
Enter sends and Shift+Enter makes a new line; every button has a label for screen
readers; the conversation is announced as it updates; a thick focus outline shows
keyboard users where they are; and Enter is ignored while someone is still composing a
word on a Hindi or Marathi keyboard.

### H. Working as a team

**45. Did you use AI to write this?**
Answer honestly, and check your institute's rules first. A truthful answer is:
*"Yes — we used Claude Code, an AI coding assistant, under our direction. We wrote the
requirements (our notes and the design), approved the plan, and ran and checked every
step; AI review agents also reviewed and tested the work. The code is documented and
tested so that we can explain and change any part of it."* The commits say so too
(`Co-Authored-By: Claude`). Then show that you understand it — which is what this page
and [01](01-walking-skeleton.md) are for.

**46. How can teammates contribute without breaking things?**
Each task on its own branch, a pull request on GitHub, a teammate reviews it, and the
automatic check must be green before merging. The rules everyone follows are in
`CLAUDE.md`; setup is in `docs/SETUP.md`.

**47. Can I try it without installing anything?**
Not yet: it isn't hosted anywhere, and the repo's `.devcontainer` (GitHub Codespaces) is
set up for the older Streamlit demo, not this app. For now: install it with
`docs/SETUP.md` (about 15 minutes), or watch the demo on a teammate's laptop. Options
later: update the dev container for Python 3.12 + Node 24, or the planned Docker setup.

### I. What's next

**48. What is the plan from here?**
In order: (1) the agreed blocked-word list and real medical checks, on both browser and
server; (2) the login page and backend authentication with MFA and CAPTCHA; (3) connect
`clinical_guardrails` to our existing `causal_engine/guardrails.py`; (4) connect the
`causal_engine` stage to `causal_engine/cdss.py` — which today compares an SGLT2 inhibitor
with metformin on synthetic data, so recommending an add-on class needs more treatment
groups and real data; (5) guideline retrieval from the PDFs in `RAG/`; (6) the written
explanation; then the database with an audit log, Docker, and voice input.

## Glossary

| Word | Meaning here |
|---|---|
| **Frontend / backend** | The page in the browser (React) / the program on the server (Python) |
| **API** | The agreed way the frontend asks the backend for something: an address plus a JSON format |
| **JSON** | Plain-text data format: `{"name": "value"}` |
| **HTTP status 200 / 422 / 500** | OK / "your request breaks the contract" / "the server itself failed" |
| **Schema / contract** | The exact allowed shape of the request and reply (`schemas.py`, `contract.ts`) |
| **Pydantic** | Python library that checks data against the schema |
| **FastAPI / uvicorn** | The Python web framework / the program that runs it and listens on port 8000 |
| **React / Vite / TypeScript** | Page library / development server and bundler / JavaScript with types |
| **Tailwind / shadcn/ui** | Styling by named classes / ready-made components copied into our code |
| **Virtual environment (`.venv`)** | The backend's private Python and libraries, separate from the rest of the computer |
| **`node_modules`** | The frontend's installed libraries |
| **Proxy** | Vite forwarding `/api` requests from the page to the backend |
| **Same-origin policy / CORS** | Browser rule that a page may only read replies from its own origin / the headers a server uses to allow other origins |
| **Trace ID** | 8-character label that follows one message through every step and log |
| **Guard** | A check that can stop a message or a reply |
| **Pipeline / stage** | The ordered steps the backend runs for each message / one of those steps |
| **Walking skeleton** | The thinnest version that goes through every layer end to end |
| **Unit / API / end-to-end test** | Tests one piece / tests the backend through its API / tests the whole route |
| **Vitest / jsdom / pytest** | Frontend test runner / simulated browser for tests / backend test runner |
| **Mutation testing** | Breaking the code on purpose to check the tests notice |
| **CI (GitHub Actions)** | GitHub running the checks automatically on every push |
| **Lint** | Automatic check for common coding mistakes (oxlint) |
| **Commit / branch / pull request** | A saved step / a separate line of work / a request to merge work after review |
| **Causal inference / CATE** | Estimating what a treatment *causes* / its effect for one kind of patient |
| **IME** | Input method: how you type Hindi, Marathi, Japanese… by composing characters |

## Code tour

When someone says "show me the code", open these in order:

| To show | Open | Point at |
|---|---|---|
| The design we matched | `design/chat.html`, `frontend/src/index.css` | Colour tokens copied across (`--color-pine`) |
| Enter and the message box | `frontend/src/components/chat/Composer.tsx` | `onKeyDown` |
| The four console lines | `frontend/src/lib/chatFlow.ts` | `checkInput` and `askDiaCausal` |
| The browser checks | `frontend/src/lib/guards.ts` | `uiGuard`, `medicalUiGuard` |
| The trace ID | `frontend/src/lib/trace.ts` | `newTraceId`, `traceLogger` |
| Sending and the output check | `frontend/src/lib/api.ts` | `postChat`, `checkOutput` |
| The contract | `backend/app/schemas.py` | `ChatRequest`, `ChatResponse` |
| Clear error messages | `backend/app/errors.py` | `_describe` |
| The six stages | `backend/app/pipeline/runner.py` + one file per stage | `STAGES_BEFORE_REPLY`, `run_pipeline` |
| Trace ID in the backend log | `backend/app/tracing.py` | `TraceIdFilter`, `trace_context` |
| The whole flow tested | `frontend/src/pages/ChatPage.test.tsx` | the first test |
| The one command | `scripts/check_all.py` | sections 1–7 |
| The automatic check on GitHub | `.github/workflows/check.yml` | the three operating systems |
| The research engine (not connected yet) | `causal_engine/cdss.py`, `causal_engine/data.py` | `recommend`, `COVARIATES` |

## Numbers worth remembering

| | |
|---|---|
| Max text per part | 8,000 characters (counted like Python, so browser and server always agree) |
| Max parts per message | 20 |
| Pipeline stages | 6 — 2 run today (first and last), 4 skipped |
| Trace ID | 8 hex characters from the browser (backend accepts 1–64 of `A–Z a–z 0–9 - _`) |
| Tests | 54 backend + 49 frontend = 103 |
| `check_all` | 21 pass/fail lines: 4 tools, 1 per test suite, build, lint, 13 live |
| Versions | Python 3.12, Node 24 LTS, React 19, Vite 8, FastAPI 0.141, Pydantic 2.13 |
| Ports | backend 8000, page 5173 |
