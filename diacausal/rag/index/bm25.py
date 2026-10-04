"""BM25 keyword search (split out of retrieve.py in restructure step 6).

Exact words matter in this domain ("eGFR", "pancreatitis"), so keyword search stays the first of the two searches.
`TOKEN` and `tokens` live here because BM25 needs them and hybrid.py imports them from here (not the other way round).
"""

from __future__ import annotations

import math
import re
from collections import Counter

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def tokens(text: str) -> list[str]:
    """Lower-case words without common English stop words ("the", "is", "of" carry no evidence)."""
    return [t for t in TOKEN.findall(text.lower()) if t not in ENGLISH_STOP_WORDS]


class BM25:
    def __init__(self, docs: list[str], k1: float, b: float):
        self.docs = [tokens(d) for d in docs]
        self.k1, self.b = k1, b
        self.avgdl = sum(map(len, self.docs)) / max(len(self.docs), 1)
        df = Counter(t for d in self.docs for t in set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [Counter(d) for d in self.docs]

    def scores(self, query: str) -> list[float]:
        q = tokens(query)
        out = []
        for tf, d in zip(self.tf, self.docs):
            s = 0.0
            for t in q:
                if t in tf:
                    f = tf[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(d) / self.avgdl))
            out.append(s)
        return out
