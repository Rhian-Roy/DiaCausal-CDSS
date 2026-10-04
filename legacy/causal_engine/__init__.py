"""
DiaCausal CDSS — Causal Engine (basic, fully-transparent implementation)
=======================================================================

Every causal quantity in this package is computed **by hand** in NumPy so that
each step can be explained, line by line, to a non-specialist. Nothing is
hidden behind a library call.

The package is deliberately small and readable:

    data.py               Build a synthetic patient world where WE author the
                          true causal effect, so every method can be *graded*.
    dag.py                The causal graph: confounders, mediators, colliders,
                          and backdoor-path enumeration.
    estimators.py         naive, stratification, g-computation, propensity
                          scores, IPW, stabilised IPW, AIPW, S/T/X-learners.
    diagnostics.py        Are we even allowed to answer? Balance (SMD),
                          overlap/positivity, and E-value sensitivity.
    evaluate.py           Grade every estimator against the authored truth;
                          policy value; predictive-ML vs causal head-to-head.
    crosscheck.py         Prove the hand-written maths agrees with DoWhy/EconML.
    pdf_text.py           Zero-dependency PDF text extraction.
    rag_lite.py           Chunk -> TF-IDF -> top-k retrieval with page citations.
    guardrails.py         Hard clinical safety rules that override any estimate.
    cdss.py               The fusion layer: CATE + guideline citation + guardrails.

Read the acts in order in ``01_Causal_Inference_Basics.ipynb``.
"""

__version__ = "1.0.0"

# A shared, colour-blind-safe palette reused across every figure so the
# notebook, the script and the Streamlit app look like one system.
# (Matches the palette already used in causal_inference_implementation.py.)
PALETTE = {
    "primary": "#0D9488",    # teal      — our estimates
    "secondary": "#0F172A",  # slate     — text / structure
    "truth": "#7C3AED",      # violet    — ground truth
    "alert": "#DC2626",      # red       — wrong / danger
    "success": "#16A34A",    # green     — correct / safe
    "amber": "#D97706",      # amber     — caution
    "muted": "#94A3B8",      # grey      — de-emphasised
}

__all__ = ["PALETTE", "__version__"]
