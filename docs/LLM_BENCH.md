# Local model via Ollama: how it is called, and the benchmark (P21)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

**Status: built, OFF.** `diacausal/llm/llm.yaml` has `provider: template`. The template writes every answer until the team has read this page.

## What was verified (Ollama 0.40.0 installed here; latest release 0.40.2, 8 Oct)
| Question | Answer | Where from |
|---|---|---|
| Does `/api/generate` take a JSON schema in `format`? | Yes: "Supports either the string `json` or a JSON schema object" | docs.ollama.com/api/generate |
| Where do `temperature` and `num_ctx` go? | Inside `options` | same page |
| Did it work on the installed server? | **Yes, tested live** with the real `AnswerDraftV1` schema on both pulled models: valid, schema-shaped JSON came back. `ollama ps` showed the model loaded with context 4096 | this machine |
| `think` | `true`, `false` or `null`; both models accept `false` without error and give the same answer. Left at `null` | docs page and live test |
| Was Ollama installed? | Already (0.40.0, `/usr/local/bin/ollama` and the app), so nothing was installed or upgraded; the 0.40.2 notes mention nothing about `format` | `ollama --version`, GitHub releases |

## The two candidates (exact tags, pulled)
| Key in `llm.yaml` | Tag | Download | Licence |
|---|---|---|---|
| `candidate_a` | `qwen3:4b-instruct-2507-q4_K_M` | 2.5 GB | Apache-2.0 (stated on its Ollama page) |
| `candidate_b` | `medgemma1.5:4b-it-q4_K_M` | 3.3 GB | **Google's Health AI Developer Foundations (HAI-DEF) Terms of Use**, not an open-source licence (not stated on the Ollama page; read at developers.google.com/health-ai-developer-foundations/terms on 10 Oct 2026). Summary below. |

**What the HAI-DEF terms say** (read from Google's page by a tool that summarises it, not the full legal text, so a human must still read the page and the separate Prohibited Use Policy it points to before the report quotes it):
- "Clinical Use" is defined as "any use in diagnosis or treatment of patients (including as part of a research study)". There is no blanket ban on it; the terms say to seek Health Regulatory Authorization when applicable (section 3.1). DiaCausal uses the model on synthetic data only, never for a real patient, and says "not for unsupervised clinical use" on every screen.
- Copies of the model or its derivatives may be redistributed only if the conditions of section 3.1 are met (pass the use restrictions on, share the agreement, include a Notice file). **Do not copy the model into this repository or the Docker image**: it is pulled by each machine from Ollama.
- A use "that could cause a Health Regulatory Authority to deem Google to be" a medical device manufacturer is not allowed (section 3.2): another reason the prototype stays a research tool.
- Google does not own the outputs; the user is responsible for them (section 3.3) and for judging whether the model is appropriate (section 4.3).
- Third-party pages disagree on the label (HAI-DEF, "Gemma terms"); the model card and Google's page both say HAI-DEF. Qwen3 (Apache-2.0) carries none of these conditions, which is one more reason to prefer it if the two models are close.

The plan says "MedGemma 1.5 4B": Ollama has it as its own library entry `medgemma1.5` (`medgemma:4b` is not labelled 1.5). Tags live in `llm.yaml` only; a test fails if one is typed anywhere in the code.

## How the provider behaves (`diacausal/llm/providers/ollama.py`)
- **Request:** `POST {ollama_url}/api/generate` with the model tag, `stream: false`, the `AnswerDraftV1` schema in `format`, `options {temperature 0, num_ctx 4096}`, `keep_alive 10m`; timeout 60 s (all from `llm.yaml`).
- **On when:** the model is called only if **both** `llm.yaml provider: ollama` **and** the request says `mode: ollama`. A dose question, or one with no evidence, never reaches it.
- **The model's text is not trusted (P23).** The provider only talks to Ollama; a failure of the call itself gives a CODE: server not running (`UNREACHABLE`), too slow (`TIMEOUT`), bad HTTP status (`HTTP_ERROR`), a reply that is not Ollama's (`BAD_REPLY`), any unexpected error. What does come back goes through the **seven output checks of plan 8.10** (`diacausal/guards/output_guards.py`): parse (`INVALID_JSON`, `SCHEMA_INVALID`), citations (a bad claim is dropped; none left = `GUARD_CITATIONS`), numbers (`GUARD_NUMBERS`), dose and threshold text (`GUARD_DOSE_THRESHOLD`), an excluded option described positively (`GUARD_EXCLUDED_OPTION`), effect wording for an option marked insufficient (`GUARD_INSUFFICIENT_WORDING`), an identifier (a BLOCK) or causal wording about a driver (`GUARD_IDENTIFIER_CAUSAL`). Anything but a pass means the template answers, and the card says `fallback_used` with the failed check IDs; **the model's text is never kept, logged or returned**.
- **Numbers on the card never come from the model:** the effects table is built from the causal output; the model supplies only the cited claims, a one-sentence context and the limitations, and a number in them must be one the causal output or the drivers contain.
- The prompt is plan 8.9 (`prompt.v2.txt`), built within a 1,900-token budget by `prompt_builder.build_llm_prompt` (P22; docs/PROMPT_TEMPLATE.md). A prompt that cannot be built (`PromptError`: `PROMPT_TOO_LONG`, `PROMPT_NO_EVIDENCE`, `PROMPT_IDENTIFIER`) sends the request to the template without calling the model.

## The benchmark (`python scripts/bench_llm.py --all`, `results/llm/`)
20 golden questions (`eval/llm_golden.csv`): 20 answerable gold questions from all seven sources, each with one of the three demo patients; the causal output and the evidence are produced by the real pipeline layers. **A draft written by Claude: Members B and D must review the questions and their pairing.** One warm-up call is excluded. Ollama 0.40.0, MacBook M5 (16 GB), 10 Oct 2026. **The numbers belong to the code that produced them: the committed files were re-run after P23 put the seven output checks in front of every draft** (and after the causal-wording check was narrowed, see point 3).

| | `candidate_a` Qwen3 4B | `candidate_b` MedGemma 1.5 4B |
|---|---:|---:|
| Schema-valid (of 20) | 100% | 85% |
| Number-match (of the valid drafts) | 35% | 24% |
| Fallback to the template (of 20) | **70%** (6 drafts used) | **80%** (4 drafts used) |
| failed check 3, numbers (whole draft falls back) | 13 | 13 |
| failed check 4, dose or threshold text | 4 | 3 |
| failed check 2, citations (claims dropped) | 8 | 2 |
| failed check 5, excluded option praised | 1 | 0 |
| timeouts | 0 | 3 |
| drafts used after dropping a bad claim | 2 | 0 |
| Latency p50 / p95 (seconds) | 17.9 / 22.2 | 22.8 / 60.0 |
| Longest prompt: estimate / Ollama's count | 1,881 / 2,759 | 1,881 / 2,728 |
| *Earlier: P21 plain prompt / P22 budgeted prompt, drafts used* | *6 / 4* | *7 / 4* |

(A draft can fail several checks, so the rows do not add up to the fallbacks.)

**How to read it**
1. **Check 3 (numbers) decides almost everything: 13 of 20 drafts for both models fall back on it.** In a diagnostic run of Qwen3 (only the offending numbers were printed, never the drafts) the 64 numbers that broke it were: **33 numbers that are in the retrieved passages** (the model quotes the evidence), **23 of the patient's own values** (age, HbA1c, eGFR, BMI echoed from PATIENT_SUMMARY into the claims or the context), and 8 others. Every one of the 13 drafts had such a number inside a claim, and none failed on patient values alone. The plan's rule allows only numbers from the causal output, the drivers, or a cited page or version, so this is the rule working as written. **Ways to raise the usable share, all your call, none done here:** drop the claim that holds the number instead of the whole draft (as check 2 does); also allow a number that appears verbatim in a passage the claim cites; also allow the patient-summary values (the card shows them anyway). Each is a change to plan 8.10.
2. **Check 4 is right when it fires.** I looked at what it caught: "contraindicated in patients with an eGFR below 30 mL/minute", copied from a label. Plan rule 4 says thresholds are never stated by the model, so these drafts must fall back.
3. **One check was too eager and was fixed before the committed run.** The first P23 run flagged 4 Qwen3 drafts for causal wording about a driver; all 4 were false alarms ("the question is whether SGLT2 inhibitors can cause ketoacidosis in a patient with an HbA1c of 8.4%": the drug causes, the HbA1c is only context). A causal cue now counts only within 4 words of a driver (`causal_window_words` in `output_guards.yaml`, TEAM-SET); the tests keep the true cases ("a higher BMI causes...", "because of eGFR") failing. **Word-list checks will have other misses and false alarms; Member D should read a sample.**
4. **Dropping a bad claim helps a little:** 2 Qwen3 drafts were used after losing one claim each (they would have fallen back before P23).
5. **No winner, and the template stays the default.** Qwen3 is more reliably valid (100% against 85%) and gives 6 usable drafts against 4; with n = 20 that is a couple of questions. MedGemma had 3 timeouts, and its terms are Google's HAI-DEF terms (summary above). The laptop was quieter this time (Qwen3 p50 18 s), but latency is still not a hardware figure, and **the RTX 2050 laptop has not been measured.** I would keep `provider: template` for 30 October.

## Run it yourself
```bash
ollama pull "$(python -c "from diacausal.llm.providers import ollama; print(ollama.model_tag(ollama.load_llm_config(), 'candidate_a'))")"
.venv/bin/python scripts/bench_llm.py --model candidate_a      # or candidate_b, or --all; --limit 3 for a quick try
```
To use a model in the app: set `provider: ollama` in `diacausal/llm/llm.yaml` (and `model:` to the key you want), start Ollama, and ask with `mode: "ollama"`.
