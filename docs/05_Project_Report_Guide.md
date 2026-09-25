# Project Report Guide (Overleaf)

**For:** Pratham (owner) · Keep it ready in case it is asked for on 30 September.

## What you have

- **DiaCausal_Report_Overleaf.zip** — the college's LaTeX template, filled in for DiaCausal. It compiles cleanly with pdfLaTeX (checked).
- **DiaCausal_Report_Draft.pdf** — what it looks like today, with grey placeholder boxes where results will go.

## Put it on Overleaf (2 minutes)

1. Overleaf → **New Project** → **Upload Project** → choose the zip.
2. **Menu** → Compiler: **pdfLaTeX**; Main document: **0Synopsis.tex**.
3. Click **Recompile**. It should build without errors.

## How the results fill in by themselves (Monday)

The report already has slots for results. When a file with the right name is in the Overleaf project, it appears automatically; until then a grey placeholder box is shown.

| Upload this file to Overleaf | It fills |
|---|---|
| `results/results_table.tex` | The benchmark results table in Chapter 5 |
| `results/figures/overlap.png`, `love_plot.png`, `ate_vs_truth.png`, `cate_recovery.png`, `calibration.png` | The result figures in Chapter 5 |
| `screens/demo1.png`, `demo2.png`, `demo3.png` | The demo screenshots in Chapter 5 |
| `code/guardrails.py`, `code/estimators.py` (copied from the repo) | The sample-code listings in Chapter 5 |

To upload: in Overleaf's file tree click **Upload**, and keep the folder names exactly as above. Then update the **Status** column of the implementation table in Chapter 5 — only with what is actually done.

## Where each mentor item is in the report

| Mentor's item | Report location |
|---|---|
| Proposed System | Chapter 3 |
| Hardware & Software Requirements | Chapter 4, "Hardware and software requirement" |
| Timeline / Gantt Chart | Appendix A |
| System Design | Chapter 4 (DFDs, UML, architecture, block diagram) |
| Implementation | Chapter 5 (status, modules, sample code) |
| Initial Results / Demo | Chapter 5 (results table, figures, screenshots) |

## Before you print or submit

- [ ] Confirm the Head of Department's name, and "Dr." for the project coordinator (both are in the Acknowledgement)
- [ ] Update the Status column in Chapter 5 with real progress
- [ ] Every number in the report comes from the results files
- [ ] Run the college similarity check if it is required (aim for under 10%)
- [ ] Decide whether to keep the AI-assistance sentence (it is commented out in the Acknowledgement)
- [ ] Unverified references are deliberately left out of the bibliography — add them only after checking the PDFs

## What is deliberately not in the report yet

RAG results, the doctor's review and the full evaluation. Chapter 6 presents them as planned work, which is exactly what the mentor asked for: work completed so far, plus the plan for the rest.

## If Overleaf shows an error

| Message | What to do |
|---|---|
| `File ... not found` | A file was uploaded into the wrong folder — check the folder names in the table above |
| `Undefined control sequence` | Something was pasted into a .tex file with a stray backslash — undo the last edit |
| Citations show as **[?]** | Recompile once more (the bibliography needs two passes) |
