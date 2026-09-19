# 03 — The guards: what stops a message, and why

A message passes two guards in the browser and the same checks again on the server
before anything else happens. The server has the final say, because a request can
reach the API without going through our page (for example with `curl`).

```
Enter ─► input passed ─► ui guard ─► medical ui guard ─► POST /api/v1/chat ─► backend_guard ─► …
                        (empty, length,  (identifier,                      (all of them again,
                         foul language)   emergency, scope)                  the one that counts)
```

## One rules file for both sides

Every list lives in **`shared/guard_rules/rules.v1.json`** (version `1.0.0-draft`):

| Side | Loads it with | Code |
|---|---|---|
| Browser | Vite JSON import (bundled into the page) | `frontend/src/lib/guards.ts` |
| Server | Python `json`, once at start-up | `backend/app/pipeline/blocklist.py` (used by `backend_guard.py` and `output_guard.py`) |

`shared/guard_rules/reference_guard.py` is the reference: a short, plain version of
the rules. Both real guards must give exactly its answer on every case in
`examples.v1.json` (47 cases) and on 55 extra tricky cases in
`frontend/src/test/guardAgreement.json`. pytest and Vitest both run all of them.

**How words are matched.** Text is normalised (Unicode NFKC, then case-folded), split
into whole words, where a word is letters + combining marks + digits
(`[\p{L}\p{M}\p{N}]`), and phrases are matched word by word. So "assess" does not
contain "ass", and the Hindi "मधुमेह" is one word, not four pieces. (Plain `\w` would
split it at every vowel sign, because vowel signs are "marks", not letters.) The backend
uses the `regex` package, since Python's built-in `re` has no `\p{…}`.

**Order, first match wins:** identifier → foul language → emergency → out of scope.

## The four guards, with one worked example each

### 1. Patient identifiers → notice 09 "Identifier removed — not sent"

Patterns for Aadhaar (12 digits **with a valid Verhoeff check digit**, so most random
12-digit lab numbers pass), ABHA number and address, Indian mobile numbers, PAN and email.

> `Patient Aadhaar 726018159082, HbA1c 8.4%`
> The regex finds `726018159082`; the Verhoeff check digit is right, so it is an Aadhaar.
> Browser: `medical ui guard blocked (identifier)`, nothing is sent, and the "You asked"
> line shows `Patient Aadhaar [removed], HbA1c 8.4%`. Server (if someone bypasses the page):
> `outcome: "blocked"`, `reason_code: "identifier"`. The number is never logged.

Known, accepted false positive: any stand-alone 10-digit number starting 6–9 looks like a
mobile number (case `i09`). Blocking is the safe side; the doctor just removes it.

### 2. Foul language → notice 12 "Cannot answer as written"

English and Hindi (romanised) words and phrases from LDNOOBW (CC BY 4.0, credited in
`docs/ATTRIBUTION.md`), with clinical words removed. A **medical allowlist always wins**,
so "anal fissure", "genital mycotic infection", "urine", "sildenafil (Viagra)" all pass.

> `what bullshit answer is this`
> Word `bullshit` is on the list and not on the allowlist → the ui guard blocks with code
> `language`. The page shows "Message not shown." instead of repeating it; the console
> warning and the server log say *that* it was blocked, never *which* word.

### 3. Emergency → notice 11 "Emergency", and nothing else

Phrases (unconscious, seizure, collapsed, severe hypoglycaemia, …) and glucose values
below 54 mg/dL (3.0 mmol/L) or at least 600 mg/dL (33.3 mmol/L), after words like
`sugar`, `CBG`, `RBS`, `GRBS`.

> `RBS 2.4 mmol/L`
> 2.4 × 18 = 43.2 mg/dL, below 54 → emergency. The reply has **no treatment content**:
> only "This may be an emergency. Follow your emergency protocol."

### 4. Out of scope → notice 10 "Out of scope", naming the reason

DiaCausal covers adults with type 2 diabetes already on metformin. Topics outside it:
type 1, pregnancy, under 18, DKA/HHS, starting insulin.

> `She is pregnant, 28 weeks, on metformin`
> `pregnant` matches the pregnancy list → `reason_code: "out_of_scope"`,
> `scope_topic: "pregnancy"` → "This question is about pregnancy."

**Negation and history cues** cancel emergency and scope matches when they appear up to
4 words before: `not pregnant`, `no prior DKA`, `history of seizures as a child`,
`past severe hypoglycaemia … two years ago` all pass. Identifiers and foul language ignore
cues ("no Aadhaar 5016 6131 8603" still blocks).

## Console and log

| Where | Pass | Block |
|---|---|---|
| Browser console | `[id] ui guard passed`, `[id] medical ui guard passed` | `console.warn`: `[id] ui guard blocked: … (language)` or `[id] medical ui guard blocked (identifier)` |
| Backend log | `[id] guard rules version 1.0.0-draft`, `[id] backend_guard: passed` | `[id] backend_guard: blocked (…reason, never the word…)` |

No check is a stub any more, so no line says "(stub)".

## Where it is tested

`backend/tests/test_guard_rules.py`, `frontend/src/lib/guards.test.ts`, the notice tests
in `frontend/src/pages/ChatPage.test.tsx`, and three live checks in `scripts/check_all.py`.

## Viva questions

**1. Why check in the browser *and* on the server?**
The browser check gives instant feedback and keeps identifiers from ever leaving the
computer. But anyone can send a request without our page, so the server repeats every
check; its answer is the one that counts.

**2. How do you know the two sides agree?**
They read the same JSON file, and both test suites run the same 47 examples plus 55
extra cases whose answers come from `reference_guard.py`. pytest also re-checks those
answers against the reference, so a wrong expected value cannot hide.

**3. Why does "assess" not trigger the word "ass", and why does "मधुमेह" stay whole?**
Matching is on whole words. A word is letters + combining marks + digits; Devanagari
vowel signs are combining marks, so they stay inside the word instead of splitting it.

**4. Why does "not pregnant" pass but "no Aadhaar 5016…" block?**
Negation and history cues are meaningful for clinical facts ("not pregnant" is a
reassuring fact). An identifier is sensitive whatever words surround it, so cues are ignored.

**5. Why is the matched word never shown or logged?**
Repeating an insult or an Aadhaar number spreads it: to the screen, to anyone reading the
log, to log backups. We record *that* a guard fired and which kind (`reason_code`),
which is all anyone needs for debugging.
