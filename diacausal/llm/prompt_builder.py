"""The prompts sent to the local model (split out of explain.py in restructure step 7).

    build_prompt        prompt.v1.txt: numbered passages, free-text answer with [n] citations (the older path)
    build_llm_prompt    prompt.v2.txt: the template of docs/PLAN_2026-10.md section 8.9 (saved in docs/PROMPT_TEMPLATE.md), filled from
                        the request, the rules' result, the causal output, the drivers and the retrieved evidence (P22)

What `build_llm_prompt` guarantees (tests/llm/test_prompt_budget.py):
    - the estimate stays within `prompt_budget_tokens` (1,900) of llm.yaml; the estimate is words x `tokens_per_word` (1.4)
    - at most `max_passages` (5) passages; one that does not fit is shortened by WHOLE SENTENCES, never in the middle of one, and
      left out when not even its first sentence fits; the causal output and the question are never shortened (too long -> PromptError)
    - the causal output and the drivers are minified JSON; a "<" in anything that came from outside is written "&lt;", so a
      passage cannot close the <evidence> tag; line breaks in the question and the passages become spaces
    - the prompt holds no patient identifier: only age, sex, HbA1c, eGFR and BMI with its class, and never the request ID
      (a question that the identifier guard would block is refused: PromptError)
    - an option the rules removed is listed with its rule ID, has no number, and no driver

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from diacausal.api.schemas import AskRequestV1, CausalOutputV1, DriverV1, EligibleOptionsV1, EvidenceBundleV1, EvidenceChunkV1
from diacausal.config import load_rag_config
from diacausal.guards.output_guards import _usable, sentences
from diacausal.rag.retrieve.hybrid import WITHHELD

PROMPT = (Path(__file__).resolve().parent / "prompt.v1.txt").read_text(encoding="utf-8")
PROMPT_JSON = (Path(__file__).resolve().parent / "prompt.v2.txt").read_text(encoding="utf-8")
LLM_CONFIG_PATH = Path(__file__).resolve().parent / "llm.yaml"
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


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
    return [_mini(causal), _mini(drivers)]


# ── the budgeted prompt (P22) ────────────────────────────────────────────────────────────────────────────────────

class PromptError(Exception):
    """The prompt cannot be built safely. `code` is a CODE, never free text (nothing the user typed is in it); the caller uses the
    template instead."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class BuiltPrompt:
    text: str
    tokens: int  # the estimate: words x tokens_per_word, rounded up
    budget: int
    shown: tuple[str, ...]  # chunk IDs that are in the prompt, in order
    shortened: tuple[str, ...]  # of those, the ones cut to whole sentences
    left_out: tuple[str, ...]  # chunk IDs beyond max_passages, withheld, or too long for even one sentence
    number_sources: tuple[str, ...]  # the causal output and the drivers exactly as the prompt shows them (the number check reads these)


def prompt_settings(path: Path = LLM_CONFIG_PATH) -> dict:
    cfg = load_rag_config(path)
    return {key: cfg[key] for key in ("prompt_budget_tokens", "tokens_per_word", "max_passages", "max_claims")}


def estimate_tokens(text: str, tokens_per_word: float = 1.4) -> int:
    """The plan's estimate: whitespace-separated words x 1.4, rounded up."""
    return math.ceil(len(text.split()) * tokens_per_word)


def _plain(text: str) -> str:
    """Text from outside the system (the question, a passage and its labels): one line, and no "<" that could open or close a tag."""
    return " ".join(str(text).split()).replace("<", "&lt;")


def _mini(value) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _drivers_json(drivers: Mapping[str, Sequence[DriverV1]], removed: set[str]) -> dict:
    """{option: [{feature, value, contribution[, ci95]}]} for options that were not removed by the rules and have a driver."""
    return {option: [d.model_dump(mode="json", exclude_none=True, exclude={"schema_version"}) for d in rows]
            for option, rows in drivers.items() if rows and option not in removed}


def _passage_line(chunk: EvidenceChunkV1, text: str) -> str:
    where = f", p.{chunk.page}" if chunk.page is not None else ""
    return f'[{chunk.chunk_id}] {_plain(chunk.source)}, {_plain(chunk.version)}, {_plain(chunk.section)}{where}: "{_plain(text)}"'


def _fit(chunk: EvidenceChunkV1, room: float, per_word: float) -> tuple[str, bool] | None:
    """The passage line within `room` tokens as (line, shortened): the whole text if it fits, else its first whole sentences;
    None when not even the first sentence fits."""
    whole = _passage_line(chunk, chunk.text)
    if estimate_tokens(whole, per_word) <= room:
        return whole, False
    kept: list[str] = []
    for s in sentences(chunk.text):
        if estimate_tokens(_passage_line(chunk, " ".join([*kept, s])), per_word) > room:
            break
        kept.append(s)
    return (_passage_line(chunk, " ".join(kept)), True) if kept else None


def build_llm_prompt(request: AskRequestV1, eligible: EligibleOptionsV1 | None, causal: CausalOutputV1,
                     drivers: Mapping[str, Sequence[DriverV1]] | None, evidence: EvidenceBundleV1, *,
                     max_claims: int | None = None, settings: dict | None = None) -> BuiltPrompt:
    """The section 8.9 prompt, filled and kept within the budget. `drivers` is empty until P25. Raises PromptError with a code:
    PROMPT_IDENTIFIER (the question holds an identifier), PROMPT_NO_EVIDENCE (no passage to show), PROMPT_TOO_LONG (the parts that
    are never shortened leave no room for a passage)."""
    from diacausal.guards import input_guards
    from diacausal.output.formatter import patient_summary

    cfg = settings or prompt_settings()
    budget, per_word, max_passages = int(cfg["prompt_budget_tokens"]), float(cfg["tokens_per_word"]), int(cfg["max_passages"])
    if input_guards.identifier(request).status == "BLOCK":
        raise PromptError("PROMPT_IDENTIFIER")
    removed = {h.option for h in eligible.excluded} if eligible else set()
    causal_json, drivers_json = _mini(compact_causal(causal)), _mini(_drivers_json(drivers or {}, removed))
    values = {"question": _plain(request.question), "patient_summary": patient_summary(request, causal.bmi_category),
              "excluded": ", ".join(f"{h.option} ({h.rule_id})" for h in eligible.excluded) if eligible and eligible.excluded else "none",
              "causal": causal_json, "drivers": drivers_json, "max_claims": str(max_claims or cfg["max_claims"])}

    def fill(evidence_block: str) -> str:
        # one pass, so a "{...}" typed in the question is never read as a placeholder
        return _PLACEHOLDER.sub(lambda m: {**values, "evidence": evidence_block}.get(m.group(1), m.group(0)), PROMPT_JSON)

    candidates = [c for c in evidence.chunks if c.text and c.text != WITHHELD]
    if not candidates:
        raise PromptError("PROMPT_NO_EVIDENCE")
    chosen, skipped = candidates[:max_passages], [c.chunk_id for c in candidates[max_passages:]]
    skipped += [c.chunk_id for c in evidence.chunks if not c.text or c.text == WITHHELD]
    left = budget - estimate_tokens(fill(""), per_word)
    lines, shown, shortened = [], [], []
    for i, chunk in enumerate(chosen):
        fitted = _fit(chunk, left / (len(chosen) - i), per_word)  # a fair share of what is left; an unused share passes on
        if fitted is None:
            skipped.append(chunk.chunk_id)
            continue
        line, cut = fitted
        lines.append(line)
        shown.append(chunk.chunk_id)
        shortened += [chunk.chunk_id] if cut else []
        left -= estimate_tokens(line, per_word)
    if not lines:
        raise PromptError("PROMPT_TOO_LONG")
    text = fill("\n".join(lines))
    tokens = estimate_tokens(text, per_word)
    if tokens > budget:  # cannot happen (each line was rounded up on its own); stated so a change that breaks it fails loudly
        raise PromptError("PROMPT_TOO_LONG")
    return BuiltPrompt(text=text, tokens=tokens, budget=budget, shown=tuple(shown), shortened=tuple(shortened), left_out=tuple(skipped),
                       number_sources=(causal_json, drivers_json))
