# Licence register: where the P19 audit stands

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

The register itself is `knowledge_sources/sources.csv` (one row per source; `docs/SOURCES.md` is generated from it with
`python -m diacausal.rag.sources_table`). The licence gate (`diacausal/rag/ingest/licence_gate.py`) ingests a document only when its
bucket is `cleared_ingest` **and** a team member has confirmed it (`checked_by` without "draft" or "to confirm").

## Buckets in use for the Indian sources (P19, audit of 9 Oct 2026, Member B with D)

| Row | Source | Bucket | Ingested or shown? |
|---|---|---|---|
| S02 | RSSDI-ESI 2020, IJEM copy (CC BY-NC-SA 4.0) | `cleared_ingest`, conditional (non-commercial, share-alike; erratum to apply) | No: nothing in the corpus yet, and `checked_by` still says "to confirm" |
| S04 | ICMR Standard Treatment Workflow (T2D) | `verbatim_only` | Quoted word for word at most; not ingested |
| S05 | ICMR Guidelines for T2D 2018 | `verbatim_only` | Same |
| S06 | NLEM 2022 | `unknown` (no licence found) | No: nothing from it is used |
| S18 | Jan Aushadhi product and MRP list | `not_allowed` until PMBI gives permission | No: no price from it is in the repository; the UI says "price unavailable" |

`checked_by` on these rows reads "Claude chat (P19 licence session, 9 Oct 2026) — Member B to confirm" on purpose: Member B replaces it
with their own name when they agree with the bucket; until then the gate stays closed.

## Open items

1. **NPPA ceiling prices**: not retrieved (class unknown).
2. **PMBI permission** to reproduce Jan Aushadhi prices: the email is drafted in `Docs/licence_audit_2026-10-09/` (outside the repo) and has not been sent.
3. NLEM 2022: save the PDF and text-search it for the seven drugs; the "which drugs are listed" statement is UNVERIFIED.
4. Jan Aushadhi: re-check the vildagliptin rows; ask PMBI for the date of the list.
5. MoHFW website policy page was not reachable.
6. Monthly cost in rupees needs doses from a cited structured table (safety invariant 3); these files hold none.

## Not yet in `sources.csv` (needs a decision; the P19 task covered only S02, S04, S05, S06 and S18)

- **S03** (RSSDI 2022, Int J Diabetes Dev Ctries 42(Suppl 1)) is in the register, but the audit found "no RSSDI version after 2020" and marked that UNVERIFIED: S03 needs its own licence check.
- **RSSDI 2017** (PMC5838201, CC BY 4.0, `cleared_ingest`) has no row.
- **MoHFW NP-NCD 2023-2030** (no licence found, `unknown`; it names no drugs) has no row.
- **RSSDI-ESI 2020, Springer copy** (PMC7371966): `not_allowed` (the permission is temporary and tied to the COVID-19 declaration); a row would stop anyone using that copy by mistake.
