"""DiaCausal RAG pipeline (old import path; the code now lives in the `diacausal.rag` package).

Research prototype for clinician evaluation; not a marketed medical device;
not for unsupervised clinical use.

Kept so that `import diacausal_rag...` and `python -m diacausal_rag...` keep working until restructure step 9
(docs/RESTRUCTURE_PLAN.md). New code imports from `diacausal.rag`.
"""

from diacausal import INTENDED_USE, __version__  # noqa: F401
