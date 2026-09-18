# 01 — The walking skeleton: what happens when you press Enter

> DiaCausal is a research prototype for clinician evaluation; not a marketed medical
> device; not for unsupervised clinical use.

A **walking skeleton** is the thinnest version of the app that still goes through every
layer: page → guards → API → backend pipeline → reply → page. Nothing clever happens
yet (the reply is a fixed dummy text), but every connection is real and tested. From
here, each new feature is "fill in one box" instead of "invent the whole route".

## The route of one message

```
 BROWSER (frontend/)                                   SERVER (backend/)
 ─────────────────────────────────────                 ─────────────────────────────────
 You press Enter
   │  new trace ID, e.g. efc1a658
   ▼
 1 input passed            (text taken from the box)
 2 ui guard passed         (not empty, ≤ 8000 chars, no blocked words)
 3 medical ui guard passed (stub: lets everything through today)
   │
   │  POST /api/v1/chat  ──── Vite forwards /api ────►  Pydantic checks the shape
   │  {"schema_version":"1.0",                          (bad shape → HTTP 422 + clear message)
   │   "client_trace_id":"efc1a658",                         │
   │   "parts":[{"type":"text","text":"..."}]}                ▼
   │                                                    Pipeline, in order:
   │                                                     backend_guard        runs
   │                                                     clinical_guardrails  skipped
   │                                                     causal_engine        skipped
   │                                                     rag_retrieval        skipped
   │                                                     llm_explanation      skipped
   │                                                     (dummy reply put in)
   │                                                     output_guard         runs
   │                                                          │
   │  ◄──────────────── reply + all six stage results ───────┘
   ▼                                                    every log line: [efc1a658] ...
 4 output passed           (right shape, same trace ID, output guard passed)
 5 reply shown in the chat
```

## Step by step, in plain English

1. **You press Enter.** `Composer.tsx` catches the key. Shift+Enter makes a new line
   instead. While you're still composing a character on a Hindi or Marathi keyboard,
   Enter is left alone.
2. **A trace ID is made.** `trace.ts` picks 8 random hex characters (like `efc1a658`).
   It's a name tag for this one message: every console line about it starts with the ID,
   and the backend prints the same ID in its log.
3. **"input passed".** `chatFlow.ts` takes the text from the box and trims spaces off the ends.
4. **"ui guard passed".** `guards.ts` checks the message isn't empty, isn't longer than
   8,000 characters (counted the way Python counts them, so an emoji is 1), and has no
   word from the blocklist. The blocklist is empty until the team supplies it. If a check
   fails, the message is **not sent**. You see a notice, and the console shows a
   `ui guard blocked` warning instead.
5. **"medical ui guard passed".** For now this is a stub that always passes. Its comment
   lists what it will check later (patient identifiers, emergencies, out-of-scope questions).
6. **The message goes to the backend.** `api.ts` sends JSON to `/api/v1/chat`. In
   development, Vite forwards anything under `/api` to FastAPI on port 8000, so the
   browser only ever talks to one address.
7. **Pydantic checks the shape.** `schemas.py` says exactly what's allowed. Unknown fields,
   unknown part types (like `"image"`) and text over 8,000 characters are rejected with
   HTTP 422. `errors.py` rewrites the error as a sentence a person can act on.
8. **The pipeline runs.** `pipeline/runner.py` calls six stages in order, one file each.
   Today only the first and last do real work:
   - `backend_guard` repeats the essential browser checks (non-empty, blocklist). It has
     to, because a request can reach the API without going through our page.
   - The middle four return `"skipped"` with "Not built yet."
   - Because `llm_explanation` doesn't exist yet, the runner puts in a fixed dummy reply.
   - `output_guard` checks the reply before it leaves: not empty, no blocked words.
   If any stage blocks, the later stages are reported as `"skipped"` and the reply says why.
9. **The backend logs, never the text.** `tracing.py` puts `[efc1a658]` on every log line
   written while this request is handled. The message text itself is never logged, because
   in real use it could contain patient details.
10. **"output passed".** Back in the browser, `checkOutput` accepts the reply only if it
    has the right shape, carries **the same trace ID we sent**, lists all six stages in
    order, and the output guard passed. Only then does the console print `output passed`.
11. **The reply appears** in a "DiaCausal answered" card. Under it are the stage results
    and the trace ID.

## One worked example

You type:

> Established coronary disease, HbA1c 8.4% on maximum metformin. What should I add, and what must I check first?

The browser makes trace ID `efc1a658` and sends:

```json
{
  "schema_version": "1.0",
  "client_trace_id": "efc1a658",
  "parts": [{ "type": "text", "text": "Established coronary disease, HbA1c 8.4% on maximum metformin. What should I add, and what must I check first?" }]
}
```

**Browser console** (open with ⌥⌘I → Console):

```
[efc1a658] input passed
[efc1a658] ui guard passed
[efc1a658] medical ui guard passed
[efc1a658] output passed
```

**Backend terminal:**

```
19:33:11 INFO    [efc1a658] chat request received: 1 part(s), 110 characters
19:33:11 INFO    [efc1a658] backend_guard: passed
19:33:11 INFO    [efc1a658] clinical_guardrails: skipped
19:33:11 INFO    [efc1a658] causal_engine: skipped
19:33:11 INFO    [efc1a658] rag_retrieval: skipped
19:33:11 INFO    [efc1a658] llm_explanation: skipped
19:33:11 INFO    [efc1a658] output_guard: passed
19:33:11 INFO    [efc1a658] reply sent: outcome=answered
INFO:     127.0.0.1:56711 - "POST /api/v1/chat HTTP/1.1" 200 OK
```

The same ID appears in both places, and the question's text doesn't appear in the log
at all.

**Reply** (shortened):

```json
{
  "schema_version": "1.0",
  "trace_id": "efc1a658",
  "outcome": "answered",
  "parts": [{ "type": "text", "text": "Dummy reply from the DiaCausal backend. Your message (110 characters) arrived safely with trace ID efc1a658. No clinical analysis ran: ..." }],
  "blocked_reason": null,
  "stages": [
    { "name": "backend_guard",       "status": "passed",  "detail": "Message has text and no blocked words." },
    { "name": "clinical_guardrails", "status": "skipped", "detail": "Not built yet." },
    { "name": "causal_engine",       "status": "skipped", "detail": "Not built yet." },
    { "name": "rag_retrieval",       "status": "skipped", "detail": "Not built yet." },
    { "name": "llm_explanation",     "status": "skipped", "detail": "Not built yet." },
    { "name": "output_guard",        "status": "passed",  "detail": "Reply has text and no blocked words." }
  ],
  "intended_use": "Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use."
}
```

**On screen:** "YOU ASKED" and your question, then a white "DIACAUSAL ANSWERED" card
with the dummy text. Under it is a grey box: "2 of 6 stages ran; the others are not
built yet", followed by each stage and its status. Last comes "Trace ID efc1a658".

### When it does not go to plan

| You do | Console | Backend | On screen |
|---|---|---|---|
| Press Enter on an empty box | `input passed`, then warning `ui guard blocked: Type a question first.` | nothing (never sent) | "Type a question first." under the box |
| Send a part with `"type": "image"` (e.g. with curl) | — | `WARNING [id] request rejected (422): Part 1 has type "image", which this API does not accept. Supported part types: text.` | (the API's JSON error) |
| Send 8,001 characters with curl | — | 422: `Part 1 text is 8,001 characters long; the limit is 8,000.` | — |
| Backend not running | error `request failed: …` | — | red box "Couldn't get a reply … Check that the backend is running." |
| A reply with another message's trace ID | error `output check failed: …` | — | "The reply did not pass the output check, so it is not shown." |

To try the API yourself while the backend is running (change `image` to `text` and add a
`"text"` field to get the dummy reply instead of the 422):

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/chat -H 'Content-Type: application/json' -d '{"schema_version":"1.0","client_trace_id":"test0001","parts":[{"type":"image","url":"x.png"}]}'
```

Leave out the `-H 'Content-Type: application/json'` part and the API tells you to add it:
without that header FastAPI does not treat the body as JSON.

## Five questions your mentor might ask

**1. Why check the message twice, in the browser and again in the backend?**
They do different jobs. The browser check gives the doctor instant feedback and saves a
wasted request. But anyone can send a request to the API directly (curl, a script), so
the browser can't be trusted to enforce anything. The backend check is the one that
counts. The same idea runs through the rest of the design: the backend's output guard
checks the reply, and the browser checks it again before showing it.

**2. What is the trace ID, and why is it made in the browser?**
It's a short random name tag for one message. Making it at the very start (in the
browser) means every step can be labelled with it: the four console lines, every
backend log line, the `X-Trace-Id` response header, and the note under the answer.
When a clinician reports "this answer looks wrong", you ask for the ID and find the
whole story in the logs, without the logs ever storing what they typed. The backend
only accepts safe characters in the ID, so it can't be used to fake log lines.

**3. Why does the reply list four stages that did not run?**
So the shape of the reply is final from day one. The frontend already displays six
stages, and the tests already require all six in order. When `causal_engine` is built,
its status changes from `"skipped"` to `"passed"` or `"blocked"`, and nothing else in the
contract changes. It is also honest: the doctor can see that no clinical reasoning
happened.

**4. The notes say "we don't know what data types will come in the future", so why reject unknown part types?**
The message is a list of *typed parts*, which is exactly what makes future types easy
to add. When images or audio arrive, we add an `ImagePart` model and a line in
`SUPPORTED_PART_TYPES`, and the request shape stays the same. What we refuse is
*silently accepting* something we can't handle. For a clinical tool, a clear "type image
is not supported yet" is far safer than quietly ignoring an attached lab report.
`schema_version` lets us change the contract later on purpose, rather than by accident.

**5. How do you know it works, and what isn't tested yet?**
There are automated tests on both sides:

- **pytest** (backend) checks the exact request and reply format, every rejection
  message, the stage order and statuses, the blocking rules, and that log lines carry
  the trace ID and never the message text.
- **Vitest** (frontend) checks the guards, the output check, and the whole page. It
  types a message, presses Enter against a fake backend, and requires exactly the four
  console lines, all with one ID. It also checks Shift+Enter, empty messages, a backend
  that is off, and replies for the wrong ID.

On top of that, the whole route was run by hand in a real browser with the real backend
(the worked example above).

Not tested yet, because it doesn't exist yet: login, the database, voice, Docker, and
the four clinical stages. Each has a README saying where it will go.

## Where to look

| To change… | Open |
|---|---|
| What the API accepts or returns | `backend/app/schemas.py` **and** `frontend/src/lib/contract.ts` |
| A pipeline stage | `backend/app/pipeline/<stage name>.py` |
| Wording of API error messages | `backend/app/errors.py` |
| The browser checks | `frontend/src/lib/guards.ts` |
| The order of console lines | `frontend/src/lib/chatFlow.ts` |
| Colours and fonts | `frontend/src/index.css` (copied from `design/chat.html`) |
| Run and test commands | `CLAUDE.md` |
