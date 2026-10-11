# Demo script: six cases, about 8 minutes

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

For a supervised demo (the viva, the dry run on Tue 27 Oct, a doctor's evaluation). One person drives the laptop, one person talks.
The screens named below are the design files in `design/screens-v2/`: open them beforehand, so you know what "right" looks like.

## Before the demo (10 minutes)

1. **Choose the copy.**
   - **The clinic laptop** (recommended: no internet, no sign-in). Double-click `scripts/start_clinic.bat` (Windows) or
     `scripts/start_clinic.command` (macOS); the browser opens http://127.0.0.1:8000/. See `docs/OFFLINE_INSTALL.md`.
   - **The public site**, https://diacausal.netlify.app: sign in with your email, password and 6-digit code before the audience
     arrives.
2. **Run the demo check** (it asks the same six cases and prints PASS or FAIL for each expected state):
   ```bash
   .venv/bin/python scripts/demo_check.py                              # Windows: .venv\Scripts\python.exe scripts\demo_check.py
   .venv/bin/python scripts/demo_check.py --url http://127.0.0.1:8000  # the clinic server you just started
   ```
   It must end with **ALL ... DEMO CHECKS PASSED**. If one fails, do not demo that case: tell the team which line failed.
3. Open **Patient Details**, press **New patient**, and make the browser window full screen.

## Opening (30 seconds)

Read this sentence **word for word**; it is also under the header of every screen:

> "Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use."

Then say:

> "DiaCausal helps a doctor compare three medicines that can be added to metformin for an adult with type 2 diabetes: an SGLT2
> inhibitor, a DPP-4 inhibitor and a sulfonylurea. **Every number you will see comes from a synthetic India-calibrated cohort**,
> not from real patients. Safety rules run first, every estimate has a 95% interval, and the clinician decides."

## The six cases

The exact numbers can change when the benchmark is rerun, so this script says **what to look for**, not the numbers.

### Case 1: a typical patient (screen 17)

- **Do:** Patient Details → **1 · Typical patient** → **Compare**.
- **Expect:** `17-answer-options-compared.html`:
  - the six steps run;
  - "Three options compared for this patient";
  - three safety cards, all "Safe to consider", with no option removed;
  - SGLT2 inhibitor carries the tag **"More HbA1c lowering than DPP-4i"**, and its difference has a 95% interval that excludes 0;
  - the card ends with "The clinician decides.".
- **Say:** "For this patient the SGLT2 inhibitor lowers HbA1c more than the DPP-4 inhibitor, and the whole 95% interval of that
  difference is below zero; it is a difference on HbA1c only, and the trade-offs below are for the doctor to weigh."
- **If it looks different:** no lead tag means the numbers changed. Say "no clear difference" instead and carry on. If any option
  says "Do not use", check the preset filled in (age 52, eGFR 88), then press **New patient** and try again.

### Case 2: eGFR 40 and past pancreatitis (screen 21)

- **Do:** **New patient** → **2 · eGFR 40, past pancreatitis** → **Compare**.
- **Expect:** `21-answer-no-clear-difference.html`:
  - SGLT2 inhibitor's card says **"Do not use"** with rule **R01** and its source;
  - in the table its row says **"Not estimated"**, with "Removed by rule R01 before estimation" under it;
  - DPP-4 inhibitor and sulfonylurea have estimates;
  - "No clear difference in HbA1c for this patient", with the trade-offs first.
- **Say:** "The kidney rule removed the SGLT2 inhibitor **before** anything was estimated, so it has no number at all; between the
  two that remain there is no clear difference in HbA1c, so DiaCausal does not pick one."
- **If it looks different:** if SGLT2 inhibitor shows a number, stop the demo of this case and tell the team (a rule did not run).
  `demo_check.py` checks this.

### Case 3: an older patient with past hypoglycaemia (screen 21, with the abstain card of screen 19)

- **Do:** **New patient** → **3 · Older, past hypoglycaemia** → **Compare**.
- **Expect:**
  - SGLT2 inhibitor removed by rule R01;
  - DPP-4 inhibitor estimated;
  - the sulfonylurea row says **"No estimate"**, with "Insufficient evidence (see below)" under it;
  - below the table, the **abstain card** of `19-insufficient-evidence.html`: "Insufficient evidence for: Sulfonylurea", "Why: too
    few similar patients received this option in the reference data (propensity …; threshold 0.05)".
- **Say:** "When too few similar patients received an option, DiaCausal says 'insufficient evidence' and shows **no number**,
  rather than guessing; it also says why."
- **If it looks different:** if the sulfonylurea shows a number, tell the team (the overlap rule did not apply). If every option
  shows "insufficient evidence", check that the preset filled in (age 80, eGFR 38).

### Case 4: an emergency (screen 11)

- **Do:** in the message box, type **Patient unconscious in OPD, which add-on?** and press Enter.
- **Expect:** `11-notice-emergency.html`:
  - the red **EMERGENCY** notice: "This may be an emergency. Follow your emergency protocol.";
  - "DiaCausal has not answered this question and will not suggest treatment for it.";
  - nothing else: no options, no passages.
- **Say:** "An emergency is never answered: the input checks stop it before anything is searched, and the red notice always comes
  first."
- **If it looks different:** if any answer appears, stop and tell the team. Check the text was typed exactly.

### Case 5: a message with an identifier (screen 09)

- **Do:** type **Patient Aadhaar 726018159082, HbA1c 8.4%, which add-on?** and press Enter. The number is made up; it only has the
  same form as a real Aadhaar number.
- **Expect:** `09-notice-identifier.html`:
  - "Identifier removed — not sent";
  - "Please remove patient identifiers (Aadhaar, phone, PAN, email, names) and ask again";
  - "You asked" shows **"[Not shown: it contained a patient identifier …]"**, never the number;
  - the message box is empty.
- **Say:** "A message holding an Aadhaar, phone, PAN, email or a name is refused and not even shown back; nothing was sent or
  kept."
- **If it looks different:** if the number appears anywhere on screen, stop and tell the team.

### Case 6: an out-of-scope question (screen 10)

- **Do:** type **She is pregnant, which add-on?** and press Enter.
- **Expect:** `10-notice-out-of-scope.html`: "Out of scope". "DiaCausal covers adults with type 2 diabetes already on metformin.
  This question is about pregnancy or breastfeeding." "Use your usual guideline or refer as you normally would."
- **Say:** "DiaCausal knows its limits: pregnancy, type 1 diabetes, children and starting insulin are outside what it was built
  for, so it sends the doctor back to the usual guideline."
- **If it looks different:** if an answer appears instead, tell the team (the scope check did not run).

## Closing (15 seconds)

> "Every estimate came from a synthetic India-calibrated cohort, with its 95% interval, after the safety rules. DiaCausal is
> decision support only: **the clinician decides**."

Press **New patient** at the end, so no patient details stay on screen.

## If something goes wrong during the demo

| You see | Do |
|---|---|
| The page does not open on the clinic laptop | the black (Windows) or Terminal (macOS) window must stay open; start the script again |
| "Sign in" on the public site | sign in, or switch to the clinic laptop |
| A case looks different from this script and `demo_check.py` passed | carry on with the next case and note what you saw; tell the team afterwards |
| The bar says "by the template" on the clinic laptop | fine for the demo: the six cases do not need the local model |
