"""Words that must not pass the guards (the "foul language" list).

Empty on purpose: the agreed list has not been supplied yet. Add lowercase single
words here. The browser has its own copy for instant feedback in
frontend/src/lib/guards.ts — but this one is the one that counts, because a
request can reach the API without going through the browser.
"""

import re

BLOCKED_TERMS: frozenset[str] = frozenset()

_WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)*")


def find_blocked_term(text: str) -> str | None:
    """The first blocked word in `text` (whole words, any case), or None."""
    for word in _WORD.findall(text.casefold()):
        if word in BLOCKED_TERMS:
            return word
    return None
