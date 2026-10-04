"""DiaCausal causal engine v0.3 (old import path; the code now lives in the `diacausal` package).

Research prototype for clinician evaluation; not a marketed medical device;
not for unsupervised clinical use.

This package is kept so that `import diacausal_engine...` and `python -m diacausal_engine...` keep working until
restructure step 9 (docs/RESTRUCTURE_PLAN.md). New code imports from `diacausal`.
"""

from diacausal import INTENDED_USE, __version__  # noqa: F401
from diacausal.config import ARMS, CONTRASTS  # noqa: F401
