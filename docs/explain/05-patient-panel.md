# 05 — The patient panel, and why the details are asked for, not read out of a sentence

The panel (design/v1/13–16) collects the facts the clinical rules need: age, how long the
patient has had diabetes, HbA1c, eGFR, BMI, a few yes/no histories, past hypoglycaemia and
a monthly budget. The question stays free text; the *facts* are structured.

## Why not just read the values out of the question?

A doctor writes in shorthand, and a parser has to guess:

| Typed | A parser might read | What it costs |
|---|---|---|
| "eGFR 45–50" | 45? 50? 4550? | the wrong kidney band, and SGLT2 rules turn on eGFR |
| "sugar 8.4" | HbA1c 8.4%? glucose 8.4 mmol/L? | a completely different patient |
| "no DKA hx" | past DKA = yes, because "DKA" appears | a contraindicated drug left in |
| "58F" | age 58? 58 kg? | age is what decides adult scope |

Getting one of those wrong is not a typo, it is a different recommendation. So DiaCausal
asks for each value in its own box, with its unit written beside it, and the doctor sees
exactly what the engine will use. This is the same reason the guards refuse patient
identifiers: what the system acts on should be deliberate, not inferred.

It also makes "missing" honest. An empty box means *not known*, so the clinical
guardrails can say "I need eGFR before I can answer" (rule `G00b_missing_egfr`) instead of
quietly assuming a value.

## The contract

`PatientPart` in `backend/app/schemas.py`, mirrored in `frontend/src/lib/contract.ts`.
`parts` is a **tagged union**: each part says its `type`, and the API reads it accordingly.

```json
{
  "schema_version": "1.0",
  "client_trace_id": "a1b2c3d4",
  "parts": [
    { "type": "patient",
      "age_years": 58, "diabetes_duration_years": 6, "hba1c_percent": 8.4,
      "egfr_ml_min_1_73m2": 62, "bmi_kg_m2": 31.2,
      "established_ascvd": true, "ckd": false, "heart_failure": false,
      "past_dka": false, "recurrent_genital_or_urinary_infection": false,
      "past_pancreatitis": false, "past_hypoglycaemia": "none",
      "budget_inr_per_month": 1500 },
    { "type": "text", "text": "Established coronary disease, HbA1c still 8.4%. What should I add?" }
  ]
}
```

Rules that fall out of that:

- **At most one patient part** per message, plus the text part (`at_most_one_patient_part`).
- Every field is **optional**; the panel starts empty and the guardrails decide what they need.
- Unknown fields are still refused (`extra="forbid"`), so a typo like `weight_kg` is caught
  rather than silently ignored.
- Adding a future part type ("image", "lab_report") means adding a model to the union and a
  name to `SUPPORTED_PART_TYPES` — the whiteboard's *"no restriction… we do not know the data
  types that can come in the future"* — **without** loosening what today's API accepts.

## Ranges are plausibility limits, not clinical thresholds

`backend/app/patient_ranges.py` (and its browser copy `ranges.ts`) hold one range per
number: age 18–110, HbA1c 4–20 %, eGFR 0–150, BMI 12–70, budget 0–100 000 ₹. They exist to
catch a slipped decimal point — HbA1c 45 % instead of 4.5 % — and nothing else. **No number
there says a value is healthy, safe or treatable.** Those decisions live in
`backend/app/clinical/guardrails.v1.yaml`, with a cited source per rule and a doctor's
review. A test compares the two copies, so the page and the server can never drift apart.

Out of range, the browser says so beside the field at once (design 15), and the server
answers 422 with the same wording:

> HbA1c 45% is outside the expected range 4.0–20.0 %. Check the value.

A value the browser flagged is simply not sent; the rest of the panel still is.

## BMI: Asian-Indian cut-offs

Normal below 23, overweight 23–24.9, obese 25 or more — not the WHO 25 / 30. Source:
Misra A, *et al.* Consensus statement for diagnosis of obesity, abdominal obesity and the
metabolic syndrome for Asian Indians. *J Assoc Physicians India* 2009;57:163-170. At the
same BMI, Indian adults carry more visceral fat and have a higher diabetes risk, so using
the WHO numbers would label a great many of our patients "normal".

## Privacy

Patient values are **never logged**. The backend logs only which fields arrived —
`patient details: age_years, hba1c_percent, egfr_ml_min_1_73m2` — and the audit log keeps
the same rule. The panel lives only in the browser's memory: "New patient" clears the panel
**and** the conversation, so the next patient cannot inherit the last one's answers, and a
sign-out or timeout clears the screen entirely.

## Viva questions

**1. Why structured fields instead of reading the values from the sentence?**
Because a misread value is a different recommendation, not a typo. Shorthand like
"eGFR 45–50", "sugar 8.4" or "no DKA hx" is genuinely ambiguous, and the system should act
only on what the doctor deliberately entered and can see.

**2. What does an empty box mean?**
Not known — and the clinical guardrails then refuse to answer rather than assume. That is
why every field is optional in the contract but the rules can still demand eGFR.

**3. Why are the ranges not clinical limits?**
They only catch typing slips. eGFR 8 is a real (very ill) patient, so 0–150 is allowed;
whether the drug is safe at eGFR 8 is a *clinical* rule, cited and doctor-reviewed, in
`guardrails.v1.yaml`. Mixing the two would hide clinical decisions inside input validation.

**4. Why a tagged union for `parts`?**
It lets new kinds of input arrive later without changing the shape of a request or
weakening today's checks: the `type` field picks the model, and anything unknown is refused
with a clear message naming the types we do accept.

**5. Why Asian-Indian BMI cut-offs?**
At the same BMI, Indian adults have more visceral fat and a higher risk of type 2 diabetes,
so the WHO cut-offs miss people who need action. We use the 2009 JAPI consensus (23 / 25)
and cite it on screen, under the category.
