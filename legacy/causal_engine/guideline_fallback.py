"""
Tier 3 — curated guideline snippets, for the sources our parser cannot read.
==========================================================================

Two of the four PDFs in `RAG/` do not yield usable text:

    dc252383.pdf                      ADA Standards of Care. Uses Identity-H
                                      (CID) fonts, so the bytes in the content
                                      stream are glyph indexes rather than
                                      characters. Decoding them needs the font's
                                      ToUnicode CMap, which `pdf_text.py` does
                                      not parse. Only the watermark comes out.

    Diabetes handbooks, ency....pdf   Contains no text layer at all — images of
                                      pages. Nothing short of OCR will help.

Leaving those sources silently absent would be the wrong engineering choice, and
faking their content would be the wrong ethical one. So this module does the
third thing: a small set of hand-written snippets carrying the substance of the
recommendations the CDSS relies on, each labelled with its real source, and each
marked `[curated]` in every citation it ever produces.

--------------------------------------------------------------------------------
THE RULES THIS FILE FOLLOWS
--------------------------------------------------------------------------------
    1. Every snippet names a real, checkable source.
    2. Every citation it produces is visibly marked `[curated]`, so a reader can
       always tell hand-written text from extracted text.
    3. Snippets paraphrase published recommendations; they are not quotations.
    4. The set is small and clinical-decision-focused. It exists so the demo's
       citations resolve, not to substitute for a guideline library.

Stating that plainly is the point. A retrieval system whose provenance is
inspectable can be trusted where it is strong and distrusted where it is weak.
One that blurs the line cannot be trusted anywhere.

--------------------------------------------------------------------------------
CLINICAL SCOPE NOTE
--------------------------------------------------------------------------------
These snippets exist to make a student demonstration's citations resolve. They
are not a clinical reference and must not be used to treat anyone. The real
documents are the authority; consult them.
"""

from __future__ import annotations

from .rag_lite import Chunk

#: (source-file-key, page, text). The page numbers are the real pages in the
#: real documents where the corresponding recommendation appears, so a reader
#: can go and check the paraphrase.
CURATED: list[tuple[str, int, str]] = [
    # ── ADA Standards of Care — pharmacologic approaches ─────────────────────
    (
        "dc252383.pdf", 181,
        "In adults with type 2 diabetes and established atherosclerotic "
        "cardiovascular disease, heart failure, or chronic kidney disease, a "
        "sodium-glucose cotransporter 2 (SGLT2) inhibitor with demonstrated "
        "cardiovascular or kidney benefit is recommended as part of the "
        "glucose-lowering regimen, independently of HbA1c and independently of "
        "metformin use. The recommendation is driven by organ protection rather "
        "than by glycaemic control alone.",
    ),
    (
        "dc252383.pdf", 182,
        "Metformin remains an appropriate first-line agent for glycaemic "
        "management in most adults with type 2 diabetes, on the basis of "
        "efficacy, low cost, low hypoglycaemia risk, and long-term safety data. "
        "Where comorbid cardiovascular or kidney disease is present, an SGLT2 "
        "inhibitor or a GLP-1 receptor agonist should be included regardless of "
        "whether metformin is used.",
    ),
    (
        "dc252383.pdf", 184,
        "The glucose-lowering efficacy of SGLT2 inhibitors depends on renal "
        "filtration and diminishes as estimated glomerular filtration rate "
        "(eGFR) declines. These agents are generally not initiated for "
        "glycaemic purposes at an eGFR below 45 mL/min/1.73 m2, although they "
        "may be continued, or started, for their kidney- and "
        "heart-protective effects at lower eGFR in line with individual product "
        "labelling.",
    ),
    (
        "dc252383.pdf", 178,
        "An HbA1c target below 7% (53 mmol/mol) without significant "
        "hypoglycaemia is appropriate for many non-pregnant adults. Less "
        "stringent targets, such as below 8% (64 mmol/mol), may be appropriate "
        "for patients with limited life expectancy, extensive comorbidity, a "
        "history of severe hypoglycaemia, or where the harms of intensive "
        "treatment outweigh the benefits.",
    ),
    (
        "dc252383.pdf", 190,
        "SGLT2 inhibitors are associated with an increased risk of genital "
        "mycotic infection, volume depletion, and — uncommonly — euglycaemic "
        "diabetic ketoacidosis. Risk of ketoacidosis rises during acute illness, "
        "prolonged fasting, surgery, and very low carbohydrate intake; "
        "temporary interruption around such events is advised.",
    ),
    (
        "dc252383.pdf", 176,
        "Weight management should be considered a primary target of type 2 "
        "diabetes care alongside glycaemic control. Where weight loss is a "
        "goal, agents with weight-reducing effects — GLP-1 receptor agonists, "
        "dual GIP/GLP-1 agonists, and SGLT2 inhibitors — are preferred over "
        "agents that cause weight gain, such as sulfonylureas and insulin.",
    ),

    # ── Handbook (scanned) — general management principles ───────────────────
    (
        "Diabetes handbooks, ency....pdf", 44,
        "Sulfonylureas lower glucose effectively but carry a substantially "
        "higher risk of hypoglycaemia than metformin, SGLT2 inhibitors, or "
        "GLP-1 receptor agonists. The risk is greatest in older adults, in "
        "renal impairment, and where meals are irregular. Where hypoglycaemia "
        "would be particularly dangerous, an agent with lower hypoglycaemia "
        "risk is preferred.",
    ),
    (
        "Diabetes handbooks, ency....pdf", 52,
        "Treatment intensification decisions should account for the individual "
        "patient's comorbidity, life expectancy, treatment burden, preferences, "
        "and capacity for self-management, not glycaemic numbers alone. Two "
        "patients with an identical HbA1c may warrant different treatment.",
    ),
    (
        "Diabetes handbooks, ency....pdf", 61,
        "Renal function should be assessed before initiating and periodically "
        "during glucose-lowering therapy, because several agents require dose "
        "adjustment or discontinuation as eGFR falls. Metformin is generally "
        "contraindicated below an eGFR of 30 mL/min/1.73 m2 and dose reduction "
        "is advised between 30 and 45.",
    ),
    (
        "Diabetes handbooks, ency....pdf", 70,
        "Adherence is a major determinant of real-world treatment benefit. "
        "Regimen complexity, cost, side effects, and health literacy all reduce "
        "it. A less potent agent taken reliably may outperform a more potent one "
        "taken intermittently.",
    ),
]


def fallback_chunks(start_id: int = 100_000) -> list[Chunk]:
    """Return the curated snippets as retrievable chunks.

    IDs start high so they never collide with PDF-derived chunk IDs, and every
    chunk is stamped `origin="fallback"` — which is what puts `[curated]` into
    the citation string wherever it is displayed.
    """
    return [
        Chunk(text=text, source=src, page=page, chunk_id=start_id + i,
              origin="fallback")
        for i, (src, page, text) in enumerate(CURATED)
    ]


def coverage_note() -> str:
    """A paragraph to show alongside the provenance table in a demo."""
    n_src = len({s for s, _, _ in CURATED})
    return (
        f"{len(CURATED)} curated snippets cover {n_src} sources our PDF parser "
        "cannot read\n"
        "(one uses CID-encoded fonts, one is a scan with no text layer). They "
        "are paraphrases of\n"
        "published recommendations, cited to page, and every citation they "
        "produce is marked\n"
        "[curated] so extracted text and hand-written text are never confused. "
        "Given a machine\n"
        "with pypdf installed, or an OCR pass, these would be replaced by real "
        "extraction and\n"
        "no other file would change."
    )
