# Guideline sources and licences (generated — do not edit by hand)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

Generated from `RAG/sources.csv` by `python -m diacausal_rag.sources_table`. Edit the CSV, then regenerate.
`diacausal_rag/ingest.py` ingests **only** rows whose bucket is exactly `cleared_ingest`; every other row is refused.
A row stays a draft until a team member confirms the licence and fills "Checked by"; drafts are never ingested.

| ID | Source | Version / year | Licence bucket | Use in DiaCausal | Checked on | Checked by |
|---|---|---|---|---|---|---|
| S01 | Guidelines on second- and third-line medicines and type of insulin for the control of blood glucose levels in non-pregnant adults with diabetes mellitus | 2018 (ISBN 978-92-4-155028-4) | cleared_ingest | Core comparative evidence: SU / DPP-4i / SGLT2i as add-on | 2026-09-19 | Claude (draft) — Member B to confirm |
| S02 | RSSDI-ESI Clinical Practice Recommendations for the Management of Type 2 Diabetes Mellitus 2020 | 2020; Indian J Endocrinol Metab 24(1):1-122; doi 10.4103/ijem.IJEM_225_20; PMID 32699774 | cleared_ingest_PENDING | Best India-specific T2D guideline in an open version | 2026-09-19 | Claude (draft) — Member B to confirm |
| S03 | RSSDI Clinical Practice Recommendations for the Management of Type 2 Diabetes Mellitus 2022 | 2022; Int J Diabetes Dev Ctries 42(Suppl 1):1-143; doi 10.1007/s13410-022-01129-5; PMC9534592 | cite_only | Newest RSSDI version — cite, do not ingest | 2026-09-19 | Claude (draft) — Member B to confirm |
| S04 | Standard Treatment Workflow: Diabetes Mellitus Type 2 (ICD-10 E11) | Undated STW PDF (2024 upload) | cite_only_permission_requested | India-specific second-line workflow; metabolic targets | 2026-09-19 | Claude (draft) — Member B to confirm |
| S05 | Guidelines for Management of Type 2 Diabetes | 2018 | cite_only_permission_requested | Indian targets and drug classes | 2026-09-19 | Claude (draft) — Member B to confirm |
| S06 | National List of Essential Medicines 2022 | 2022 | cite_only_structured | Which of the three classes are on NLEM (structured table) | 2026-09-19 | Claude (draft) — Member B to confirm |
| S07 | US FDA prescribing information: FARXIGA (label 2026, 202293s035), JARDIANCE, JANUVIA, AMARYL, metformin | current labels | cite_only_structured | eGFR limits and contraindications in guardrails.v1.yaml | 2026-09-19 | Claude (draft) — Member B to confirm |
| S08 | FDA Drug Safety Communications: metformin and reduced kidney function (8 Apr 2016); saxagliptin/alogliptin and heart failure (5 Apr 2016) | 2016 | cleared_ingest | Guardrails G00, G07 | 2026-09-26 | Rhian Roy Kuttikadan (team) |
| S09 | KDIGO 2022 Clinical Practice Guideline for Diabetes Management in CKD | 2022 | cite_only | SGLT2i organ-protection note (G15) | 2026-09-19 | Claude (draft) — Member B to confirm |
| S10 | NICE NG28 Type 2 diabetes in adults | current | exclude | — | 2026-09-19 | Claude (draft) — Member B to confirm |
| S11 | IDF Global Clinical Practice Recommendations for Managing Type 2 Diabetes | 2025 (ISBN 978-2-930229-97-3) | cite_only_permission_requested | — | 2026-09-19 | Claude (draft) — Member B to confirm |
| S12 | ADA Standards of Care in Diabetes | 2026 | cite_only | Team study only | 2026-09-19 | Claude (draft) — Member B to confirm |
| S13 | LASI Wave 1 India Report | 2020 | cite_only | Numbers in params.yaml | 2026-09-19 | Claude (draft) — Member B to confirm |
| S14 | Anjana RM et al. ICMR-INDIAB national study | 2023 | cite_only | Numbers in params.yaml | 2026-09-19 | Claude (draft) — Member B to confirm |
| S15 | StatPearls; Endotext (NCBI Bookshelf) | living | verbatim_only | Background definitions | 2026-09-19 | Claude (draft) — Member B to confirm |
| S16 | ICD-11 | current | verbatim_only | Codes and titles | 2026-09-19 | Claude (draft) — Member B to confirm |
| S17 | LDNOOBW List of Dirty, Naughty, Obscene and Otherwise Bad Words (en, hi) | master, fetched 2026-09-19 | cleared_ingest | shared/guard_rules/rules.v1.json | 2026-09-19 | Claude (draft) — Member B to confirm |
| S18 | PMBJP / Jan Aushadhi product and MRP list | download current list | cite_only_structured | monthly_cost_inr in params.yaml | 2026-09-19 | Claude (draft) — Member B to confirm |
| X01 | Managing Diabetes Mellitus: Guide for Health Workers | August 2007 | exclude | — | 2026-09-19 | Claude (draft) — Member B to confirm |
| X02 | Diabetes Care 2026;49(8):1323-1329 (ambient temperature and hypoglycaemia in type 1 diabetes) | 2026 | exclude | — | 2026-09-19 | Claude (draft) — Member B to confirm |
| X03 | 'Diabetes handbooks, ency...' link list (AI-generated) | — | exclude | — | 2026-09-19 | Claude (draft) — Member B to confirm |

**Licence confirmed, may be ingested:** S08.
**Cleared bucket, waiting for a team member to confirm:** S01, S17.
