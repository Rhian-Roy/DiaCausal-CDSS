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
| `candidate_b` | `medgemma1.5:4b-it-q4_K_M` | 3.3 GB | **Not stated on the Ollama page.** Google says its Health AI Developer Foundations terms govern MedGemma and that it is not clinical-grade. **UNVERIFIED: read the terms before MedGemma appears in the report.** |

The plan says "MedGemma 1.5 4B": Ollama has it as its own library entry `medgemma1.5` (`medgemma:4b` is not labelled 1.5). Tags live in `llm.yaml` only; a test fails if one is typed anywhere in the code.

## How the provider behaves (`diacausal/llm/providers/ollama.py`)
- **Request:** `POST {ollama_url}/api/generate` with the model tag, `stream: false`, the `AnswerDraftV1` schema in `format`, `options {temperature 0, num_ctx 4096}`, `keep_alive 10m`; timeout 60 s (all from `llm.yaml`).
- **On when:** the model is called only if **both** `llm.yaml provider: ollama` **and** the request says `mode: ollama`. A dose question, or one with no evidence, never reaches it.
- **Falls back to the template on anything:** server not running (`UNREACHABLE`), too slow (`TIMEOUT`), bad HTTP status (`HTTP_ERROR`), a reply that is not Ollama's (`BAD_REPLY`), invalid JSON (`INVALID_JSON`), JSON that is not an `AnswerDraftV1` (`SCHEMA_INVALID`), a claim that cites no passage, a passage that was not shown or one that does not support it, or a dose (`CITATION_CHECK`), a number that is not in the causal output (`NUMBER_MISMATCH`), or any unexpected error. The reply carries `fallback: CODE`; **the model's text is never kept, logged or returned**.
- **Numbers on the card never come from the model:** the effects table is built from the causal output; the model supplies only the cited claims. Plan 8.10 check 3 is enforced here already (P23 will own the full set of guards).
- The prompt is plan 8.9 (`prompt.v2.txt`), built within a 1,900-token budget by `prompt_builder.build_llm_prompt` (P22; docs/PROMPT_TEMPLATE.md). A prompt that cannot be built (`PromptError`: `PROMPT_TOO_LONG`, `PROMPT_NO_EVIDENCE`, `PROMPT_IDENTIFIER`) sends the request to the template without calling the model.

## The benchmark (`python scripts/bench_llm.py --all`, `results/llm/`)
20 golden questions (`eval/llm_golden.csv`): 20 answerable gold questions from all seven sources, each with one of the three demo patients; the causal output and the evidence are produced by the real pipeline layers. **A draft written by Claude: Members B and D must review the questions and their pairing.** One warm-up call is excluded. Ollama 0.40.0, MacBook M5 (16 GB), 10 Oct 2026. **The numbers belong to the prompt that produced them: this table was re-run after P22 replaced the plain P21 prompt with the budgeted one (docs/PROMPT_TEMPLATE.md).** The committed files are the second of two runs on the new prompt (the first ran while I was also running tests, so the second is the quieter one; both are shown).

| | `candidate_a` Qwen3 4B | `candidate_b` MedGemma 1.5 4B |
|---|---:|---:|
| Schema-valid (of 20), P22 run 1 / run 2 | 100% / **90%** | 75% / **85%** |
| Number-match (of the valid drafts), run 1 / run 2 | 35% / **39%** | 27% / **24%** |
| Fallback to the template (of 20), run 1 / run 2 | 80% / **80%** | 80% / **80%** |
| of which in run 2: number not in the causal output | 7 | 9 |
| of which in run 2: citation check failed | 7 | 4 |
| of which in run 2: timeout | 2 | 3 |
| Latency p50 / p95 (seconds), run 2 | 40.3 / 60.0 | 29.7 / 60.0 |
| Longest prompt: the estimate / Ollama's own count | 1,881 / 2,612 | 1,881 / 2,728 |
| *Before P22 (plain prompt, one run)*: valid / fallback / longest prompt | *100% / 70% / 3,149* | *90% / 65% / 3,124* |

**How to read it**
1. **The prompt is now inside its budget.** The estimate never passes 1,881 (budget 1,900), and Ollama's own count of the longest prompt fell from 3,149 to about 2,700 tokens, which leaves about 1,300 of the 4,096 for the reply (a draft is about 350). The estimate under-counts: Ollama's count is 1.2 to 1.6 times it (mean 1.35; measured with the prompt cache bypassed, docs/PROMPT_TEMPLATE.md).
2. **Answers the pipeline can use did not improve: 4 of 20 for both models (was 6 and 7).** Both models fall back on 80% of the questions in both runs. With n = 20 the difference from before is 2 or 3 questions, and the timeouts (2 and 3 in run 2, each a question lost) come from a busy laptop, so I cannot tell a prompt effect from noise. What is clear is the mechanism: **the number rule (plan 8.10 check 3) and the citation check reject most drafts**: models copy numbers from the evidence ("60 years", "30"), which the rule sends to the template. That is the rule working; it means a model-written answer reaches the card in about one question in five. P23 may drop only the offending claim instead of the whole draft; that, not the prompt, is what would raise the usable share.
3. **No winner.** Qwen3 is more reliably valid (90 to 100% against 75 to 85%) and MedGemma is no better on any measure here; the gap is a few questions. MedGemma's licence is still UNVERIFIED.
4. **Latency is not a clean number.** The laptop was busy in both runs (load average 3 to 4 with the benchmark idle), and the same model's p50 moved from 26.5 s to 40.3 s between two runs of the same prompt. Treat 27 to 40 s as an upper bound on an M5 under load, not a hardware figure. **The RTX 2050 laptop (4 GB) has not been measured.** The first call after loading takes 13 to 38 s, so a cold server will usually fall back once.
5. **I would still keep `provider: template` for the 30 October demo**; the local model is an optional extra whose answers are all checked and which cannot show a number the engine did not produce.

## Run it yourself
```bash
ollama pull "$(python -c "from diacausal.llm.providers import ollama; print(ollama.model_tag(ollama.load_llm_config(), 'candidate_a'))")"
.venv/bin/python scripts/bench_llm.py --model candidate_a      # or candidate_b, or --all; --limit 3 for a quick try
```
To use a model in the app: set `provider: ollama` in `diacausal/llm/llm.yaml` (and `model:` to the key you want), start Ollama, and ask with `mode: "ollama"`.
