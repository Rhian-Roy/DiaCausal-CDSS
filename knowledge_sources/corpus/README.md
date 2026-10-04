# diacausal_rag/corpus — licence-cleared documents only

Put a document here only if its source row in `RAG/sources.csv` has bucket **exactly**
`cleared_ingest` **and** a team member has confirmed the licence in `checked_by` (not a draft).
Everything else is refused by `diacausal_rag/ingest.py`, and a test fails if a `.txt` file here is
missing from `manifest.csv`.

| File | Source | Licence | How it was made |
|---|---|---|---|
| `who_2018_second_line.txt` | S01 WHO 2018 second- and third-line medicines guideline, PDF pages 7–26 | CC BY-NC-SA 3.0 IGO | `python -m diacausal_rag.pdf_text` from the official WHO PDF (iris.who.int) |
| `fda_dsc_2016_metformin_kidney.txt` | S08 FDA DSC 8 Apr 2016, metformin and kidney function | US government work | from the FDA PDF |
| `fda_dsc_2016_saxagliptin_alogliptin_hf.txt` | S08 FDA DSC 5 Apr 2016, saxagliptin/alogliptin and heart failure | US government work | `scripts/fetch_fda_dsc.py` |
| `fda_dsc_2015_dpp4_joint_pain.txt` | S19 FDA DSC 2015, DPP-4 inhibitors and joint pain | US government work | `scripts/fetch_fda_dsc.py` |
| `fda_dsc_2015_sglt2_ketoacidosis_uti.txt` | S20 FDA DSC 2015, SGLT2 inhibitors: ketoacidosis, urinary infections | US government work | `scripts/fetch_fda_dsc.py` |
| `fda_dsc_2016_canagliflozin_dapagliflozin_kidney.txt` | S21 FDA DSC 2016, acute kidney injury warnings | US government work | `scripts/fetch_fda_dsc.py` |
| `fda_dsc_2018_sglt2_genital_infection.txt` | S22 FDA DSC 2018, Fournier's gangrene | US government work | `scripts/fetch_fda_dsc.py` |
| `fda_dsc_2020_canagliflozin_amputation.txt` | S23 FDA DSC 2020, amputation Boxed Warning removed | US government work | `scripts/fetch_fda_dsc.py` |

**WHO attribution (required by the licence):** World Health Organization. *Guidelines on second- and
third-line medicines and type of insulin for the control of blood glucose levels in non-pregnant
adults with diabetes mellitus.* Geneva: WHO; 2018. Licence: CC BY-NC-SA 3.0 IGO. The text here was
extracted from the PDF (layout removed); it is shared under the same licence, for non-commercial use
only, and WHO does not endorse DiaCausal. FDA texts: US federal government works, brand tables and
reference lists left out; they describe US labels, not Indian CDSCO labelling.

Format: plain text, sections start with `## Section name`, page markers like `[page 12]` (web pages
have none). List each file in `manifest.csv` with its source id.

Never put here: the IDF 2025 PDF, ADA Standards, NICE, KDIGO, RSSDI 2022, textbooks, or anything
"cite_only". Passages with dose-like text are withheld at search time (doses come only from labels).
