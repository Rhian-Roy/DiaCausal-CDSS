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
- The prompt is a plain version of plan 8.9 (`prompt.v2.txt`); P22 refines it.

## The benchmark (`python scripts/bench_llm.py --all`, `results/llm/`)
20 golden questions (`eval/llm_golden.csv`): 20 answerable gold questions from all seven sources, each with one of the three demo patients; the causal output and the evidence are produced by the real pipeline layers. **A draft written by Claude: Members B and D must review the questions and their pairing.** One warm-up call is excluded. Ollama 0.40.0, MacBook M5 (16 GB), 10 Oct 2026.

| | `candidate_a` Qwen3 4B | `candidate_b` MedGemma 1.5 4B |
|---|---:|---:|
| Schema-valid (of 20) | **100%** | 90% (1 invalid JSON, 1 timeout) |
| Number-match (of the valid drafts) | 35% | 44% |
| Fallback to the template (of 20) | 70% | 65% |
| of which: number not in the causal output | 9 | 8 |
| of which: citation check failed | 5 | 3 |
| of which: timeout / invalid JSON | 0 | 1 / 1 |
| Latency p50 / p95 (seconds) | 37.8 / 43.7 | 28.4 / 58.5 |
| Longest prompt (tokens) | 3,149 | 3,124 |
| Warm-up (cold load) | 27 s | 37 s |

**How to read it**
1. **Both models follow the schema** (100% and 90%), so the structured-output route works. The two models differ by two questions, which is not a difference at n = 20.
2. **Most answers are still rejected, mainly for numbers.** The plan's rule is that every number must come from the causal output (or be a page or version of a cited passage). The models keep writing numbers from the evidence text ("60 years", "30") and the rule sends those to the template. That is the rule working, not a model fault; but it means **a model-written answer reaches the card in only about one question in three (6 of 20 and 7 of 20)**. P23 may prefer to drop such a claim instead of the whole draft; that would raise the usable share.
3. **The prompt is too long.** Plan 8.9 budgets about 1,900 tokens; real prompts reach 3,100, with five passages up to 650 tokens each, only about 1,000 under the 4,096 limit. P22 (budget, cutting at sentence ends) matters before any model goes live.
4. **Latency is not a clean number.** The laptop was busy (a browser using a full core, the display sharing the GPU): the same 3 questions took about 10 s in a lighter try and 22 to 41 s in this run. Treat 28 to 38 s as an upper bound on an M5 under load, not as a hardware figure. **The RTX 2050 laptop (4 GB) has not been measured.** One MedGemma call hit the 60 s timeout; the first call after loading takes 27 to 37 s, so a cold server will usually fall back once.
5. **Not a recommendation of a winner.** I would keep `provider: template` for the 30 October demo; the local model is an optional extra whose answers are all checked and which cannot show a number the engine did not produce.

## Run it yourself
```bash
ollama pull "$(python -c "from diacausal.llm.providers import ollama; print(ollama.model_tag(ollama.load_llm_config(), 'candidate_a'))")"
.venv/bin/python scripts/bench_llm.py --model candidate_a      # or candidate_b, or --all; --limit 3 for a quick try
```
To use a model in the app: set `provider: ollama` in `diacausal/llm/llm.yaml` (and `model:` to the key you want), start Ollama, and ask with `mode: "ollama"`.
