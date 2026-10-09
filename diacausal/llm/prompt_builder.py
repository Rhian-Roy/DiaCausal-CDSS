"""The prompts sent to the local model (split out of explain.py in restructure step 7).

    build_prompt        prompt.v1.txt: numbered passages, free-text answer with [n] citations (the older path)
    build_json_prompt   prompt.v2.txt: the template of docs/PLAN_2026-10.md section 8.9, for the structured JSON answer (P21).
                        A PLAIN version: no token budget, no sentence-end cutting and no tests of its own yet; P22 refines it
                        (budget under 1,900 tokens, minified inputs checked, snapshot test).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from diacausal.guards.output_guards import _usable
from diacausal.rag.retrieve.hybrid import WITHHELD

PROMPT = (Path(__file__).resolve().parent / "prompt.v1.txt").read_text(encoding="utf-8")
PROMPT_JSON = (Path(__file__).resolve().parent / "prompt.v2.txt").read_text(encoding="utf-8")


def build_prompt(question: str, passages: list[dict], max_sentences: int) -> str:
    numbered = "\n\n".join(f"[{n}] ({p['citation']['source_id']}, {p['citation']['section']}) {p['text']}"
                           for n, p in _usable(passages))
    return (PROMPT.replace("{max_sentences}", str(max_sentences))
            .replace("{question}", re.sub(r"[{}]", "", question)).replace("{passages}", numbered))


def _interval(iv) -> dict | None:
    return None if iv is None else {"value": iv.value, "ci95": [iv.ci_low, iv.ci_high]}


def compact_causal(causal) -> dict:
    """The causal output reduced to what the explanation may quote: each option's status and its numbers with their 95% intervals
    (the website and the card take every number from the full output, never from the model)."""
    options = []
    for o in causal.options:
        row = {"option": o.arm, "status": o.status}
        if o.status == "estimate":
            row["hba1c_change_6m"] = _interval(o.effect)
            if o.secondary is not None:
                row["weight_change_kg"] = _interval(o.secondary.weight_change_kg)
                row["hypo_risk_pct"] = _interval(o.secondary.hypo_risk_pct)
        options.append(row)
    return {"applicable": causal.applicable, "options": options,
            "comparisons": [{"first": c.first, "second": c.second, "difference": _interval(c.difference)} for c in causal.comparisons]}


def number_sources(causal: dict, drivers: dict) -> list[str]:
    """The texts a draft may take its numbers from: the causal output and the drivers, exactly as the prompt shows them."""
    return [json.dumps(causal, separators=(",", ":")), json.dumps(drivers, separators=(",", ":"))]


def _evidence_block(passages: list[dict]) -> str:
    lines = []
    for p in passages:
        c = p["citation"]
        text = p["text"].replace("<", "&lt;")  # passages are quoted material, never markup that could close the <evidence> tag
        lines.append(f'[{p["chunk_id"]}] {c["title"]}, {c["version"]}, {c["section"]}, p.{c["page"]}: "{text}"')
    return "\n".join(lines)


def build_json_prompt(*, question: str, patient_summary: str, excluded: list[str], causal: dict, drivers: dict, passages: list[dict],
                      max_claims: int = 4) -> str:
    """The section 8.9 prompt, filled. `passages` are the retriever's passages (with chunk_id); a withheld passage is left out."""
    shown = [p for p in passages if p.get("text") and p["text"] != WITHHELD]
    values = {"question": re.sub(r"[{}]", "", question), "patient_summary": patient_summary,
              "excluded": ", ".join(excluded) or "none", "causal": json.dumps(causal, separators=(",", ":")),
              "drivers": json.dumps(drivers, separators=(",", ":")), "evidence": _evidence_block(shown), "max_claims": str(max_claims)}
    out = PROMPT_JSON
    for key, value in values.items():
        out = out.replace("{" + key + "}", value)
    return out
