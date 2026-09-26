# diacausal_rag/corpus — licence-cleared documents only

Put a document here only if its source row in `RAG/sources.csv` has bucket **exactly**
`cleared_ingest` **and** a team member has confirmed the licence in `checked_by` (not a draft).
Everything else is refused by `diacausal_rag/ingest.py`.

Today: `fda_dsc_2016_metformin_kidney.txt` — the FDA Drug Safety Communication of 8 April 2016 on
metformin and reduced kidney function (S08, US government work, confirmed by the team on 2026-09-26;
reference markers, the reference list and the brand-name table left out). Waiting: S01 WHO 2018
(Member B to confirm), and the 5 April 2016 FDA saxagliptin/alogliptin communication (text not yet
fetched).

Format: plain text, sections start with `## Section name`, page markers like `[page 12]`.
List each file in `manifest.csv` with its source id:

```
file,source_id
who_2018_second_line.txt,S01
```

Never put here: the IDF 2025 PDF, ADA Standards, NICE, textbooks, or anything "cite_only".
