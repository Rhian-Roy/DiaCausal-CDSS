# 06 — Clinical guardrails: the rules that come before any ranking

The second stage of the pipeline now runs. It takes the patient panel, applies the cited
rules in `backend/app/clinical/guardrails.v1.yaml`, and decides — **before anything is
ranked** — which of the three add-on options may be used at all.

```
backend_guard ─► clinical_guardrails ─► causal_engine ─► rag_retrieval ─► llm_explanation ─► output_guard
                 ▲ removes unusable options here, so nothing downstream can rank them
```

## Three invariants

1. **Guardrails run before the causal engine.** A contraindicated option is removed in this
   stage, so the ranking never sees it and it can never be shown first.
2. **Every threshold comes from the table, with a source.** No number in the code, none read
   out of the doctor's sentence, none from a language model.
3. **A rule that is not ready does not run.** A rule with a `TODO` or without a source is
   refused, and the refusal is logged and reported.

## The table

15 rules, 14 in use. Each has an `id`, a `scope` (the whole patient, or one option), a
`when:` condition, an `action`, a plain-English `reason`, and a `source` with title,
version, section and URL.

| Action | Means |
|---|---|
| `abstain` | the whole question is refused — e.g. eGFR below 30, where "add to metformin" no longer applies |
| `do_not_use` | that option is removed before the causal stage |
| `check_first` | the option stays, with a caution and its source |
| `info` | relevant background (e.g. the KDIGO kidney recommendation), never a restriction |

`G13_su_older_adult` is **refused**: its threshold is still `TODO_AGE` and it has no source.
The loader excludes it, `scripts` and the log say so, and
`.venv/bin/python -m app.clinical.check` exits 1 until Member D fills it in. The other
fourteen still protect the patient in the meantime — refusing to start would have thrown
away fourteen good rules for the sake of one incomplete one.

## Conditions are data, not code

A `when:` line is parsed, checked against a whitelist of comparisons, `and`/`or`/`not` and
"is missing", and only then evaluated with the patient's values. Anything else —
a function call, an attribute, a comprehension, a leftover `TODO_AGE` — is refused by the
loader, so a mistake (or a malicious edit) in the table cannot run code on the server.

A value that was never entered is **unknown**, not zero: a rule about eGFR simply does not
fire when eGFR is blank. That is why `G00b_missing_egfr` exists — without kidney function,
the stage abstains instead of quietly assuming.

## A worked example

Patient panel: 58 years, type 2 diabetes 6 years, HbA1c 8.4 %, **eGFR 40**, BMI 31.2,
**past DKA: yes**, no heart failure, no past hypoglycaemia.

| Rule | Fires? | Effect |
|---|---|---|
| `G00_metformin_egfr_lt30` | no (40 ≥ 30) | — |
| `G00b_missing_egfr` | no (it was entered) | — |
| `G01_sglt2i_egfr_lt30` | no | — |
| `G02_sglt2i_egfr_30_to_45` | **yes** | SGLT2 inhibitor → check first |
| `G03_sglt2i_past_dka` | **yes** | SGLT2 inhibitor → **do not use** (the stricter one wins) |
| `G09_dpp4i_egfr_lt45` | **yes** | DPP-4 inhibitor → check first (dose adjustment) |
| sulfonylurea rules | no | Sulfonylurea → safe to consider |

Result: the SGLT2 inhibitor is **removed** — the causal engine will never rank it — and the
reply carries all three statuses with their reasons and sources, plus
"draft — not clinically reviewed", because no doctor has signed the table off yet.
The stage's own line reads `2 of 3 options may be used; removed: sglt2i`.

## What the reply carries

A new reply part, `options` (`OptionsPart` in `schemas.py`, mirrored in `contract.ts`):
each option's `status`, the `reasons` and `sources` behind it, `notes` from `info` rules,
and the `rule_ids` that fired — an audit trail from an answer back to a line in the table.
Later stages (the causal engine, the explanation) add their own fields to the same part.

## Viva questions

**1. Why can't the model override a contraindication?**
Because no model is involved at this point, and nothing downstream can put the option
back. The guardrails run before the causal engine and physically remove the option from
the list the engine receives; the explanation stage can only describe what survived. A
statistical estimate is an average over people, while a contraindication is a fact about
*this* patient — and a language model is not a safety mechanism at all.

**2. Why is a threshold in a YAML file instead of in the code?**
So a doctor can read and review it without reading Python, so every number carries its
source, version and section, and so changing a threshold is a reviewable one-line change
rather than a code change. The tests read the thresholds from the same file, so the rules
and their tests can never drift apart.

**3. What happens when a rule is incomplete?**
It never fires. The loader refuses it, the server logs "clinical rule NOT in use — …",
and `python -m app.clinical.check` exits 1. A refused rule cannot silently behave as if
it passed.

**4. What if the panel is half empty?**
Rules about a missing value do not fire, and the rules that require a value say so: with
no eGFR, `G00b` abstains and the pipeline stops with "Kidney function is needed before any
of the three options can be judged." DiaCausal would rather say nothing than guess.

**5. What if every option is ruled out?**
The stage abstains and says why for each one, instead of ranking things that must not be
used. That is the honest answer, and it is what design 19 ("insufficient evidence") shows.
