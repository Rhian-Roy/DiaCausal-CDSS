# eval — the evaluation pack

What a reviewer or a clinician-evaluation session needs, in one folder.

| File | What it is |
|---|---|
| `vignettes.v1.json` | 25 **synthetic** patients and questions, each with what the app should do: every clinical guardrail rule, each guard (identifier, emergency, out of scope, language), the abstain paths and ordinary questions |
| `run_vignettes.py` | Runs all 25 through the real pipeline and writes `results/<date>.csv`; exits 1 if any behaves differently from the table |
| `system-usability-scale.md` | The standard 10-question usability questionnaire, with how to score it |
| `doctor-feedback.md` | The safety-and-usefulness sheet, one per session |
| `results/` | Saved runs (not committed) |

```bash
cd backend && .venv/bin/python ../eval/run_vignettes.py      # on a development machine
docker compose exec app python ../eval/run_vignettes.py      # in the deployed container
```

**No real patient data is in this folder, and none may be put into it.** The
Aadhaar-format number in vignette V15 is a randomly generated fake with a valid check
digit; it belongs to nobody.
