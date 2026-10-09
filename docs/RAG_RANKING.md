# Source-aware ranking for the RAG (P19)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

**Status: built, OFF.** `diacausal/rag/ranking.yaml` has `enabled: false`. With it off, search is exactly as before (72 saved questions give identical answers) and the website is unchanged.

## What it does when switched on (`diacausal/rag/retrieve/ranking.py`, used by `hybrid.py`)
1. **Fusion (reciprocal rank fusion, k = 60):** each BM25 ranking (one per sub-query) contributes its **top 20**, the dense ranking its **top 20** if dense search is on (`dense.yaml`), and the TF-IDF ranking as it always did (in full).
2. **Re-sort** the fused list by the tuple **(fusion score, authority tier, India relevance, section match, patient-condition match)**, best first, compared left to right: a later key only decides between passages tied on every earlier key. The fusion score is compared after rounding to `fusion_round_decimals` places; two passages whose fused scores round to the same number are tied. After the five keys come the exact score and the chunk's position, so the order is fully determined.
3. **Latest version only:** if two rows of `sources.csv` have the same issuer and title and different versions, only the newest version's passages can be returned. A family whose versions cannot all be read as a date or year is left alone (nothing is dropped on a guess).
4. **Only order changes.** The candidates are the passages the keyword searches found, and **abstention is decided from the plain keyword ranking**, so ranking can never turn an answer into a refusal or the reverse (tested on 72 questions).

| Key | Where it comes from | Better = |
|---|---|---|
| authority tier | `knowledge_sources/sources.csv` column `authority_tier` | lower in `authority_tier_order` (1, 2, 3, 4, UNKNOWN) |
| India relevance | column `india_relevance` | earlier in `india_order` (india, global, other_country, unknown) |
| section match | question words (plus their query-processing expansions) found in the passage's section title | more |
| patient-condition match | the patient's yes/no conditions (kidney disease, heart failure, heart disease, past pancreatitis, past hypoglycaemia, past ketoacidosis) that the passage mentions, by the search words in `ranking.yaml` | more |

## The two new `sources.csv` columns (filled from each row's issuer and kind of document)
**authority_tier:** 1 guideline or recommendation of a health or professional body; 2 regulator safety communication or label; 3 government list, survey, peer-reviewed study or reference text; 4 not clinical evidence (word list, price list); `UNKNOWN`.
**india_relevance:** `india` written by an Indian body or about the Indian population; `global` an international body; `other_country` another country's body (FDA, ADA, NICE, Bhutan); `unknown`.

| Sources | Tier | India relevance |
|---|---|---|
| S01 WHO 2018 guideline (ingested) | 1 | global |
| S08, S19 to S23 FDA Drug Safety Communications (ingested) | 2 | other_country |
| S02, S03 RSSDI, S04, S05 ICMR | 1 | india |
| S09 KDIGO, S11 IDF | 1 | global |
| S10 NICE, S12 ADA, X01 Bhutan | 1 | other_country |
| S06 NLEM, S13 LASI, S14 INDIAB | 3 | india |
| S07 FDA labels | 2 | other_country |
| S15 StatPearls/Endotext | 3 | **unknown** |
| S16 ICD-11 | 3 | global |
| S17 word list | 4 | **unknown** |
| S18 Jan Aushadhi price list | 4 | india |
| X02 ADA journal article | 3 | other_country |
| X03, RP01 to RP05 | **UNKNOWN** | **unknown** |

These are **proposals for Member B and the doctor to confirm**: nobody has reviewed them. Unknowns are marked, never guessed. Note that only seven sources are in the corpus today, so **only two tiers matter now**: WHO (1) against FDA (2), and every passage is global or other_country (nothing is India-specific). The India key will start to matter if an Indian source such as S02 is ingested.

## Evaluation (`python -m diacausal.rag.evaluate --ranking-tune`, then `--ranking-ablation`)
All 60 gold questions are split by a fixed seed (`ranking.yaml`: 20261010) into **train (40: 30 answerable, 7 out-of-scope, 3 dose) and held-out (20: 15, 3, 2)**, stratified (answerable by source). **The one thing tuned is `fusion_round_decimals`, chosen on train only** (a test proves tuning reads no held-out question): exact and 4 decimals give train nDCG@5 0.665, **3 gives 0.672 (chosen)**, 2 collapses to 0.439 because too many passages tie. Held-out was read once, after that choice. The gold questions carry no patient, so the condition key cannot be evaluated here (it is unit-tested).

| split | variant | recall@5 | MRR | nDCG@5 | abstention accuracy | dose leaks |
|---|---|---:|---:|---:|---:|---:|
| train (30 answerable) | before | 0.933 | 0.647 | 0.663 | 0.857 | 0 |
| | after | 0.933 | 0.659 | 0.672 | 0.857 | 0 |
| **held-out (15 answerable)** | before | 1.000 | 0.739 | 0.685 | 0.667 | 0 |
| | **after** | 1.000 | **0.772** | **0.700** | 0.667 | 0 |
| | after + dense bge-small | 1.000 | 0.794 | 0.707 | 0.667 | 0 |
| | after + dense PubMedBERT | 0.933 | 0.772 | 0.683 | 0.667 | 0 |
| all 45 | before / after | 0.956 / 0.956 | 0.677 / 0.697 | 0.670 / 0.681 | 0.800 / 0.800 | 0 / 0 |

**Honest reading: no demonstrated gain.** The held-out improvement (MRR +0.033, nDCG@5 +0.015) is one question that improved and none that got worse, and its paired 95% interval starts at exactly 0. On train the same change has 2 wins and 3 losses on MRR, and over all 45 questions 3 wins and 3 losses (MRR +0.019, interval -0.009 to +0.056). Recall@5 and abstention do not move; no dose text leaks. The ordering changes 21 of the 60 top-5 lists (16 of them only reorder the same passages), mostly through the section-match and rounding rules, because within one source the tier and India keys are identical. Adding dense search helps a little on held-out with bge-small and loses one question (recall 0.933) with PubMedBERT. Files: `results/rag_ranking_eval.csv`, `rag_ranking_paired.csv`, `rag_ranking_tuning.csv`.

**Recommendation:** keep it off for the 30 October demo. The tiers become useful when the corpus holds sources of different tiers on the same question, which today it mostly does not.

## To switch it on
Set `enabled: true` in `diacausal/rag/ranking.yaml`. **That makes the Python search differ from the website's** (`web/evidence.js` mirrors the plain fusion), so `tests/web` will fail until the browser is changed too (P27) or the two are allowed to differ on purpose. The patient's conditions are already passed by `/api/v1/ask`.
