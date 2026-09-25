# Bringing a teammate's causal-engine code into DiaCausal

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

**For:** Graceton, and anyone with their own causal-inference code. The engine on `main`
(`diacausal_engine/`) is the **one engine** the demo, the API, the tests and the benchmark use. We
compare other code with it first, then keep the best parts through a pull request. Nobody replaces
it directly.

## 1. How to upload your code (5 minutes, no command line needed)

1. On github.com open **Rhian-Roy/DiaCausal-CDSS**.
2. Click the branch menu (it says `main`), type a new name such as `graceton/causal-engine`, and
   choose **Create branch**.
3. On that branch: **Add file → Upload files**. Put everything in a folder named
   `contrib/graceton/` (drag the whole folder), then **Commit changes**.
4. Write in the team chat what it does, and how to run it, in three lines.

Please **never upload to `main`**, and never upload:
- any real patient data;
- API keys or passwords (for example a `.env` file);
- datasets or PDFs whose licence we have not checked (see `RAG/sources.csv`).

## 2. What I compare (the checklist)

| # | Question | Our engine on `main` |
|---|---|---|
| 1 | Does it answer **our** question: three options added to metformin, 6-month HbA1c change? | Yes: SGLT2i, DPP-4i, SU |
| 2 | Do safety rules run **before** any estimate, read from `data/rules.csv`, with nothing hard-coded? | Yes (a test scans the code) |
| 3 | Does every estimate have a **95% interval**? | Yes |
| 4 | Does it say "insufficient evidence" when propensity < 0.05? | Yes |
| 5 | Is it tested against a **known truth**: bias, coverage, PEHE? | Yes (`results/`) |
| 6 | Does every data number have a **source and status**? | Yes (`data/params.yaml`) |
| 7 | Are there no drug doses and no secrets? | Yes (tests) |
| 8 | Is it synthetic or licence-cleared data only (not Pima presented as Indian data)? | Yes |
| 9 | Are there automated tests? | 139 |
| 10 | Does it return the flow chart's **Causal Output** (applicable, intervention, outcome, effect, confidence, assumptions)? | Yes (`schemas.CausalOutput`) |

## 3. What happens next

- **A good extra piece** (a new estimator such as a causal forest, a better plot, a real-data
  loader) gets added to `diacausal_engine/` with tests. It then appears in the benchmark next to
  AIPW and the DR-learner, so the team can see honestly which is better.
- **A duplicate of something we already have** stays in `contrib/` as reference, credited to you.
- **Anything that breaks a rule above** (hard-coded thresholds, no intervals, doses) is not merged
  until it is fixed.

The merge happens through a pull request, which the tests check automatically before anyone clicks
Merge.
