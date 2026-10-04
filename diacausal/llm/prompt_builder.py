"""The prompt sent to the local model (split out of explain.py in restructure step 7). The text is prompt.v1.txt."""

from __future__ import annotations

import re
from pathlib import Path

from diacausal.guards.output_guards import _usable

PROMPT = (Path(__file__).resolve().parent / "prompt.v1.txt").read_text(encoding="utf-8")


def build_prompt(question: str, passages: list[dict], max_sentences: int) -> str:
    numbered = "\n\n".join(f"[{n}] ({p['citation']['source_id']}, {p['citation']['section']}) {p['text']}"
                           for n, p in _usable(passages))
    return (PROMPT.replace("{max_sentences}", str(max_sentences))
            .replace("{question}", re.sub(r"[{}]", "", question)).replace("{passages}", numbered))
