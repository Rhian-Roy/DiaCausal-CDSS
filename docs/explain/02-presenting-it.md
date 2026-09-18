# 02 — Presenting it: pitch, demo and answers to likely questions

Read [01-walking-skeleton.md](01-walking-skeleton.md) first: it explains what happens
when you press Enter. This page helps you **say** it: short pitches, an everyday
analogy, a demo script, answers to the questions guides and mentors usually ask, a
glossary and a code tour.

> DiaCausal is a research prototype for clinician evaluation; not a marketed medical
> device; not for unsupervised clinical use.

**Golden rule when answering:** say what it does *today*, what it will do *later*, and
where the code is. If you don't know, say "good question — here is where that lives"
and open the file (see the [code tour](#code-tour)). Never guess.

## The 30-second version

> "This is the first working slice of DiaCausal. A doctor types a question on the chat
> page. The page checks it, labels it with a short tracking ID and sends it to our
> Python server. The server checks it again and runs it through a six-stage pipeline —
> today only the safety checks at the start and the end are real, the four clinical
> stages in the middle are marked *not built yet* — and a test reply comes back. The
> same tracking ID appears in the browser console and on every server log line, so we
> can follow any message end to end. Next, our causal engine and guideline search plug
> into those four marked slots."

## The 2-minute version (for guides)

1. **The goal.** DiaCausal will help doctors choose second-line diabetes treatment for
   adults already on metformin, using causal inference (what is *likely to cause* a
   better outcome for *this* patient), clinical guardrails and cited guidelines.
2. **Why this slice first.** Before any clever model, we built a *walking skeleton*:
   the whole route from the chat page to the server and back, with a dummy answer.
   Joining the pieces is where projects usually break, so we did it first, while it
   is simple.
3. **What works today.** The chat page matches our design. Browser checks block empty
   or over-long messages. The API accepts only a precise message format and rejects
   anything else with a clear explanation. A six-stage pipeline runs, with the
   safety checks at both ends. Every step carries one trace ID.
4. **How we know.** One command, `python3 scripts/check_all.py`, runs all 102
   automated tests, the type-check, build and lint, then starts the real servers and
   checks them live — 21 checks in all, all passing. The tests were themselves tested by
   deliberately breaking the code.
5. **What's next.** Login with MFA and CAPTCHA; the real blocklist; then connecting our
   existing guardrails, causal engine and guideline retrieval into the marked stages.

## An everyday analogy (for non-technical listeners)

Think of a **hospital courier with tracking numbers**.

- You write a note (the question) at the **front desk** (the chat page). The desk
  checks it isn't blank or too long (**UI guards**) and stamps a **tracking number** on
  it (the **trace ID**).
- The note goes to the **back office** (the Python backend). Security at the back door
  checks it *again* (**backend guard**) — because people can walk in through the back
  door without passing the front desk.
- Inside, the note moves along a **conveyor with six stations**. Four stations have a
  sign *"under construction"* (**skipped**). The last station inspects the reply before
  it leaves (**output guard**).
- The reply comes back with the same tracking number, and the front desk **checks the
  number matches** before handing it over (**output check**).
- Every station writes the tracking number in its logbook — but **never copies the
  note's contents** (privacy).

## The live demo (about 5 minutes)

**Before you start:** start both servers ([SETUP.md, step 5](../SETUP.md#5-try-it-yourself)),
open http://localhost:5173 and the browser console, and put the browser and the
backend terminal side by side. Zoom the browser to 125–150% so people at the back can
read. The demo needs **no internet** — everything runs on your laptop. As a backup,
keep a screenshot of the page and of a passing `check_all` run.

| # | Do | Say |
|---|---|---|
| 1 | Show the page | "This follows our design: large readable fonts, the patient summary marked *Example data*, and the disclaimer under the message box." |
| 2 | Type `Established coronary disease, HbA1c 8.4% on maximum metformin. What should I add?` → **Enter** | "Watch the console: four lines — input passed, UI guard, medical UI guard, output passed — all starting with the same 8-character ID." |
| 3 | Point at the backend terminal | "The server printed the same ID on eight lines: request received, each of the six stages, reply sent. Notice my question's words are not in the log — only its length." |
| 4 | Point at the answer card | "The reply is a dummy for now. The grey box shows which stages ran: two of six. The ID under it matches the console." |
| 5 | Press **Enter** on an empty box | "Empty messages are blocked in the browser — nothing reaches the server. The server also blocks them, in case someone skips the page." |
| 6 | Open http://localhost:8000 → **POST /api/v1/chat → Try it out**; in the example body change `"type": "text"` to `"type": "image"`; **Execute** | "The API refuses anything outside the contract with a message a person can read: *Part 1 has type "image", which this API does not accept.*" |
| 7 | Run `python3 scripts/check_all.py` | "One command runs all 102 tests, the build and lint, then starts the real app and tests it live: 21 checks, all passing." |
| 8 | Close | "Next: login with MFA and CAPTCHA, then the causal engine plugs into its stage." |

## Questions you may be asked — with answers

### A. The big picture

**1. What is DiaCausal?**
A clinical decision support prototype for type 2 diabetes. For an adult already on
metformin whose sugar is still high, it will suggest which medicine class to add, with
the reasoning, safety checks and guideline citations. It is for research evaluation by
clinicians, not for use on patients without supervision.

**2. What does this version actually do?**
It carries a question from the chat page to the backend and back, through all the
checks and all six pipeline stages, and shows a *fixed test reply*. It gives **no**
clinical advice yet. Everything around the future advice — the page, the API, the
safety checks, the tracing, the tests — is real.

**3. Why build a "walking skeleton" with a dummy reply instead of the model first?**
Connecting the parts is where projects usually fail late. With the skeleton working,
every later feature only fills one clearly marked slot, and we can test each one end to
end the day it is added. It also let us fix the message format early, so the frontend
and backend can be developed in parallel.

**4. Is this a medical device? Is it safe to use on patients?**
No. It is a research prototype for clinician evaluation; not a marketed medical
device; not for unsupervised clinical use. That sentence is on the page and inside
every chat reply from the API. Today's reply is a fixed test text, and the page says so.

**5. Who is it for?**
Clinicians (doctors) evaluating the prototype. That is why the design uses large,
highly legible fonts and puts safety information in clear green/amber/red boxes.

### B. How it works

**6. What happens when I press Enter?**
Three checks in the browser (input, UI guard, medical UI guard), then the message is
sent to the Python backend as JSON. The backend checks the format, runs six stages
(two real checks, four not built yet), adds a dummy reply, and sends everything back.
The browser checks the reply belongs to this message and shows it. Details: [01](01-walking-skeleton.md).

**7. What is an API here, exactly?**
A fixed address on the server, `POST /api/v1/chat`, that accepts one precise JSON
format and returns another. The format is written down in `backend/app/schemas.py`,
and FastAPI publishes live documentation of it at http://localhost:8000/docs.

**8. What does the request look like?**
`{"schema_version":"1.0","client_trace_id":"a1b2c3d4","parts":[{"type":"text","text":"…"}]}`
— a version number, the trace ID, and a list of typed parts (today only text).

**9. What are the six stages, and why are four "skipped"?**
`backend_guard` (runs), `clinical_guardrails`, `causal_engine`, `rag_retrieval`,
`llm_explanation` (all four *not built yet*), `output_guard` (runs). Listing all six
from day one means the reply's format is already final, and it is honest: the doctor
can see no clinical reasoning happened.

**10. What is the trace ID and why is it made in the browser?**
A random 8-character label for one message (like `efc1a658`). Made at the very start,
it can label every step: the four console lines, every backend log line, the response
header and the note under the answer. If a clinician says "this answer looks wrong",
the ID finds the whole story in the logs — without the logs storing what they typed.

**11. Can two messages get the same trace ID?**
It has 8 hexadecimal characters, about 4.3 billion possible values, and log lines also
carry the time, so for a prototype a mix-up is very unlikely. The backend accepts IDs up
to 64 characters, so it can be made longer later without changing the API.

**12. Why does the page call `/api/...` and not the backend's port directly?**
Browsers block a page on one address from reading replies from another address unless
the server specially allows it (this rule is called CORS). In development Vite
*forwards* `/api` to the backend, so the browser only ever talks to one address and
there is no CORS setup to get wrong. In production a web server will do the same job.

### C. Safety, security and privacy

**13. Why check the message twice — in the browser and on the server?**
They do different jobs. The browser check gives instant feedback and saves a wasted
request. But anyone can send requests straight to the API (for example with curl), so
the browser can't be trusted to enforce anything — the server check is the one that
counts.

**14. What about foul language?**
The blocking works on both sides and is tested with a made-up word. The real word list
is still empty — the team will add it in `frontend/src/lib/guards.ts` and
`backend/app/pipeline/blocklist.py`. It matches whole words only, so "assess" is not
blocked by a word inside it.

**15. What does the "medical UI guard" check?**
Today it is a stub that lets everything through — that is stated in the code. Planned
checks: patient identifiers typed into the box (names, phone or Aadhaar numbers),
emergencies (tell the user to get help instead), and questions outside the tool's
scope.

**16. Why is the message text never logged?**
In real use a question could contain patient details, and logs are copied, shared and
kept for a long time. So the backend logs only the trace ID, sizes and stage results.
A test checks that the text never appears in the log.

**17. How is the backend protected against bad or hostile input?**
Pydantic checks every request against the contract before our code runs; unknown
fields, unknown part types, text over 8000 characters, more than 20 parts, or a badly
formed trace ID are refused with HTTP 422 and a plain-English reason. Anything the
client sent is echoed back only short and escaped, so it can't flood the reply or
forge extra lines in the log (both are tested).

**18. Where is the login with ID, password, MFA and CAPTCHA?**
Not built yet, on purpose: the first slice proves the route works. The place is
prepared — `backend/app/auth/README.md` and `frontend/src/features/auth/README.md`
describe the plan: CAPTCHA, then password (stored only as a hash), then the 6-digit
code, then a secure session cookie; the chat API will then answer only signed-in
clinicians.

**19. Later, what stops a wrong or harmful answer from reaching a doctor?**
Several layers: clinical guardrails (hard rules such as kidney-function thresholds)
that override any statistical estimate; the output guard that checks the reply before
it leaves; the browser's output check; the disclaimer; and the clinician, who makes
the decision.

### D. Technology choices

**20. Why React + Vite + TypeScript?**
React is the most widely used way to build interactive pages, so help and examples are
easy to find. Vite starts instantly and reloads on every save. TypeScript catches
mistakes like a wrong field name before the page runs — the build fails instead of the
doctor's screen.

**21. Why Tailwind and shadcn/ui?**
Tailwind lets us put the design's exact colours, fonts and spacing in one place
(`frontend/src/index.css`) and use them by name (`bg-pine`). shadcn/ui gives ready-made,
accessible components (button, text box) whose code is copied into our project, so we
can change them freely.

**22. Why FastAPI + Pydantic, and why Python?**
Our causal engine and research code are already Python, so the backend can call them
directly. FastAPI turns a Python function into a web API, and writes the interactive
documentation for us. Pydantic checks every request against our models; that is how
the strict contract is enforced.

**23. The repo already has a Streamlit demo. Why a separate React app and API?**
Streamlit is great for our own analysis demos. For clinicians we need our own design,
login, and a stable API that other clients (a mobile app, an evaluation harness) can
use. Separating the page from the API also lets us test each on its own.

**24. Why `schema_version` and a list of `parts`?**
`parts` lets new kinds of input (an image, an audio clip) be added as new part types
without changing the shape of a message. `schema_version` lets us change the contract
deliberately later, with old and new clients telling each other which version they
speak.

**25. The notes say "we don't know what data types may come in the future" — so why reject unknown types?**
Because the list of typed parts is what makes future types easy to *add*. What we
refuse is *silently accepting* something we can't handle: for a clinical tool, a clear
"type image is not supported yet" is far safer than quietly ignoring an attached lab
report.

### E. Testing and quality

**26. How do you know it works?**
`python3 scripts/check_all.py` runs 53 backend tests, 49 frontend tests, the
type-check, build and lint, then starts the real backend and page and sends real
messages through them — 21 checks. We also checked it by hand in a browser
([TESTING.md, part 2](../TESTING.md#part-2--check-by-eye-in-a-real-browser-about-10-minutes)).

**27. What kinds of tests are these?**
*Unit tests* check one piece alone (e.g. the UI guard with an empty text). *API tests*
send requests to the backend in memory and check the replies. The *page test* runs the
real React page in a simulated browser (jsdom): it types a question, presses Enter, and
requires exactly the four console lines with one ID. The *live checks* start the real
servers and talk to them over the network.

**28. How do you know the tests are good enough?**
We tested the tests: reviewers deliberately broke the code in dozens of small ways
(drop a console line, reorder stages, let an empty message through, stop hiding the
text from the log) and checked that a test fails each time. Where none did, we added
one. This is called *mutation testing*.

**29. What is not tested?**
Things that don't exist yet (login, database, voice, Docker, the four clinical
stages), real browsers other than Chrome (Safari's keyboard quirk is tested in
simulation), and Windows/Linux setup, which is written but so far only run on macOS.

### F. Design and usability

**30. Why these fonts and colours?**
The body font, Atkinson Hyperlegible, was designed by the Braille Institute to keep
letters like I/l/1 and O/0 easy to tell apart — important when reading doses and lab
values quickly. Headings use a serif (Source Serif 4). Safety states use green, amber
and red boxes, each with an icon and a word, so colour is never the only signal.

**31. Why is "Example data" shown even on phones, when the phone design leaves it out?**
So example values can never be mistaken for a real patient. It was a deliberate,
safety-first change from the mock-up.

**32. Is it accessible?**
Enter sends and Shift+Enter makes a new line; every button has a label for screen
readers; the conversation is announced as it updates; a thick focus outline shows
keyboard users where they are; and Enter is ignored while someone is still composing a
word on a Hindi or Marathi keyboard.

### G. How it was built

**33. Did you use AI to write this?**
Answer honestly, and check your institute's rules first. A truthful answer is:
*"Yes — we used Claude Code, an AI coding assistant, under our direction. We wrote the
requirements (our notes and the design), reviewed the plan, and ran and checked every
step. The code is documented and tested so that we can explain and change any part of
it."* The commits also say so (`Co-Authored-By: Claude`). Then show that you understand
it — which is what this page and [01](01-walking-skeleton.md) are for.

**34. How can teammates contribute without breaking things?**
Each task on its own branch, a pull request on GitHub, a teammate reviews it, and
`scripts/check_all.py` must pass before merging. The rules everyone follows are in
`CLAUDE.md`.

### H. What's next

**35. What is the plan from here?**
In order: (1) the agreed foul-language list and real medical UI checks; (2) the login
page and backend authentication with MFA and CAPTCHA; (3) connect
`clinical_guardrails` to our existing `causal_engine/guardrails.py`; (4) connect the
`causal_engine` stage to `causal_engine/cdss.py` to rank treatment options; (5)
guideline retrieval from the PDFs in `RAG/`; (6) the written explanation; then the
database with an audit log, Docker, and voice input.

**36. How exactly will the causal engine plug in?**
Its stage is one file, `backend/app/pipeline/causal_engine.py`, with a `run` function
that today returns *skipped*. It will call our existing code and return *passed* with
its ranking. The API format already has room for it, and the page already shows each
stage's status — so the frontend does not need to change for it to appear.

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
| **CORS** | Browser rule that stops a page reading replies from a different address unless allowed |
| **Trace ID** | 8-character label that follows one message through every step and log |
| **Guard** | A check that can stop a message or a reply |
| **Pipeline / stage** | The ordered steps the backend runs for each message / one of those steps |
| **Walking skeleton** | The thinnest version that goes through every layer end to end |
| **Unit / API / end-to-end test** | Tests one piece / tests the backend through its API / tests the whole route |
| **Vitest / jsdom / pytest** | Frontend test runner / simulated browser for tests / backend test runner |
| **Mutation testing** | Breaking the code on purpose to check the tests notice |
| **Lint** | Automatic check for common coding mistakes (oxlint) |
| **Commit / branch / pull request** | A saved step / a separate line of work / a request to merge work after review |
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

## Numbers worth remembering

| | |
|---|---|
| Max text per part | 8,000 characters (counted like Python: an emoji is 1) |
| Max parts per message | 20 |
| Pipeline stages | 6 — 2 run today (first and last), 4 skipped |
| Trace ID | 8 hex characters from the browser (backend accepts 1–64 of `A–Z a–z 0–9 - _`) |
| Tests | 53 backend + 49 frontend = 102; `check_all` = 21 checks |
| Versions | Python 3.12, Node 24 LTS, React 19, Vite 8, FastAPI 0.141, Pydantic 2.13 |
| Ports | backend 8000, page 5173 |
