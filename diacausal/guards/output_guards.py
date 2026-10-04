"""The citation checker: output guards for an explanation (split out of explain.py in restructure step 7).

Plain English: whatever a model writes is checked sentence by sentence before anyone sees it. Every sentence must
cite a passage that was shown, most of its words must appear in the passages it cites, and it must not contain a
dose. `sentences` and `check_answer` are mirrored line by line by web/explain.js (the web parity test proves both
give the same result on 100 questions), so change them together.
"""

from __future__ import annotations

import re

from diacausal.causal_inference.recommend import DOSE_PATTERN
from diacausal.rag.index.bm25 import tokens
from diacausal.rag.retrieve.hybrid import WITHHELD

_SPLIT = re.compile(r"(?:(?<=[.!?])|(?<=\]))\s+(?=[A-Z0-9\"“(•-])")
# The checker splits a model's answer after every citation group, and after .!? before a capital.
_ANSWER_SPLIT = re.compile(r"(?<=\])\s+|(?<=[.!?])\s+(?=[A-Z0-9\"“(•-])")
_CITES = re.compile(r"\s*((?:\[\d+\]\s*)+)[.!?]?\s*$")
_BULLET = re.compile(r"^[-•]\s*")


def sentences(text: str) -> list[str]:
    """Split passage text into sentences; bullet marks removed."""
    parts = []
    for line in re.split(r"\s+(?=[•]\s)|\s+-\s(?=[A-Z])", text):
        for s in _SPLIT.split(line.strip()):
            s = _BULLET.sub("", s).strip()
            if len(s) > 1:
                parts.append(s)
    return parts


def _content(text: str) -> set[str]:
    return set(tokens(text))


def _usable(passages: list[dict]) -> list[tuple[int, dict]]:
    return [(n, p) for n, p in enumerate(passages, start=1) if p["text"] != WITHHELD]


def check_answer(text: str, passages: list[dict], min_support: float) -> tuple[list[dict], list[str]]:
    """Parse a model's answer into cited sentences and list every problem (empty list = it passes)."""
    problems: list[str] = []
    if DOSE_PATTERN.search(text):
        problems.append("the answer contains dose-like text")
    usable = dict(_usable(passages))
    items = []
    for s in _ANSWER_SPLIT.split(text.strip()):
        s = s.strip()
        if not s:
            continue
        m = _CITES.search(s)
        if not m:
            problems.append(f"a sentence has no citation: {s[:60]!r}")
            continue
        cites = sorted({int(x) for x in re.findall(r"\d+", m.group(1))})
        body = s[:m.start()].rstrip(" .") + "."
        missing = [c for c in cites if c not in usable]
        if missing:
            problems.append(f"cites passage(s) {missing} that were not shown")
            continue
        words = _content(body)
        support = set().union(*(_content(usable[c]["text"]) for c in cites))
        share = len(words & support) / len(words) if words else 0.0
        if share < min_support:
            problems.append(f"only {share:.0%} of a sentence's words are in the passages it cites: {body[:60]!r}")
            continue
        items.append({"text": body, "cites": cites})
    if not items and not problems:
        problems.append("empty answer")
    return items, problems
