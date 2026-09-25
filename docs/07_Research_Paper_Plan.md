# Research Paper Plan

**For:** Pratham (lead writer) and everyone

## When — not now

A paper needs final results, so writing it now would mean writing it twice.

| When | What |
|---|---|
| Now – 16 Oct | Build and evaluate; results frozen on 16 October |
| 17 – 30 Oct | Full draft — each member writes their own sections in their own words |
| November | Exams — no work |
| December | Polish, similarity check, choose the venue with the guide, submit |

Until then, keep one running file of decisions and numbers so the paper writes itself later.

## Where — candidate IEEE venues (confirm with the guide)

| Venue | Dates | Deadline | Notes |
|---|---|---|---|
| IEEE EMBC 2027 | 11–15 July 2027, Singapore | Not yet published (EMBC 2026's was 23 January 2026) | Strong fit for health AI; 4–7 pages; in person |
| IEEE ICHI 2027 | To be announced | Early-bird closed 21 Sept 2026; regular deadline not yet published | Health informatics; selective |
| FCRIT's ICNTE | Next edition 2028 | — | Not available in time |

Before paying any fee, check the conference on conferences.ieee.org and confirm it has an IEEE conference record number.

## Outline (IEEE conference format, about 6 pages)

This revises Pratham's existing draft rather than starting again.

| Section | What it says | Where the content comes from |
|---|---|---|
| Title | Causal inference + RAG + second-line type 2 diabetes therapy in India | — |
| Abstract | Problem, method, results (real numbers), intended use | Results files |
| I. Introduction | The clinical decision, why correlation misleads, our contributions | Viva answers 1–7 |
| II. Related work | Treatment selection (TriMaster, Dennis 2022, Güdemann 2026); CATE methods; clinical RAG | Report Chapter 2 |
| III. Problem formulation | Potential outcomes, assumptions, what we estimate | Report Chapter 3 |
| IV. System | Guardrails, causal engine, RAG, audit log | Report Chapters 3–4 |
| V. Experimental setup | India-calibrated synthetic cohort, baselines, metrics | params.yaml, document 02 |
| VI. Results | Tables and figures from `results/` | Benchmark |
| VII. Discussion and limitations | Synthetic data, no real-world validation yet | Viva answer 35 |
| VIII. Ethics and intended use | Intended-use statement; ethics approval for real data | Document 01 |
| Acknowledgment | AI-use disclosure (IEEE requires it) | — |

**What changes from Pratham's draft:** drop fuzzy cognitive maps, DirectLiNGAM as the main method, SHAP, SNOMED and dose simulation; add a proper RAG section, the India focus, real results, and relevant verified references in place of the off-topic ones.

## Rules that protect you

- **AI disclosure:** IEEE requires authors to disclose AI-generated content in the Acknowledgments — name the tool, the sections, and how it was used. AI cannot be an author.
- **Similarity:** under the UGC 2018 regulations, similarity up to 10% is "Level 0 — no penalty". We found no source for any "₹5 lakh fine".
- **Honesty:** never invent results or references; only verified references go in the bibliography.
- **Ownership:** each member rewrites their sections in their own words and can explain every line.

## Suggested division of writing

| Person | Sections |
|---|---|
| Pratham | Introduction, related work, final editing |
| Rhian | Method and results |
| Graceton | System design and RAG |
| Advik | Evaluation, ethics, limitations, references |

## Prompt to use on 17 October (Claude chat or Claude Code, with the results attached)

```text
Here is our results summary and our report chapters. Draft Section VI (Results) of our IEEE conference paper in formal academic English: one table built only from these numbers, two figure captions, and three paragraphs interpreting the results honestly, including limitations. Do not invent any number. Mark anything you are unsure of with [CHECK].
```
