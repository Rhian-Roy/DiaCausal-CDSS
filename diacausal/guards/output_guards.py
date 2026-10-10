"""Output guards: whatever a model writes is checked before anyone sees it (split out of explain.py in restructure step 7; P23).

Two parts:

  1. The citation checker (`sentences`, `check_answer`): every sentence must cite a passage that was shown, most of its words must appear in
     the passages it cites, and it must not contain a dose. Mirrored line by line by web/explain.js (the web parity test proves both give the
     same result on 100 questions), so change them together. The website never uses a model, so part 2 has no mirror.

  2. The seven checks of docs/PLAN_2026-10.md section 8.10 on a model's structured draft (`run_output_guards`, P23):

        1 parse                the text is JSON that parses as AnswerDraftV1                        -> template fallback
        2 citations            each claim cites retrieved chunk IDs and its words are in them        -> DROP the claim; none left -> ABSTAIN
        3 numbers              every number is in the causal output or the drivers, or is a cited page or version -> fallback
        4 dose_threshold       no dose, no "mL/min with a number", no "contraindicated if" ...        -> fallback
        5 excluded_option      no excluded option described positively                                -> fallback
        6 insufficient_wording no effect wording for an option marked insufficient                    -> fallback
        7 identifier_causal    an identifier -> BLOCK; causal wording about a driver                  -> fallback

     All checks 2 to 7 always run (none stops early), so the record lists EVERY check that failed. The result is a `GuardedDraftV1`; the
     caller (diacausal/llm/answer.py) turns anything but PASS into the template's answer and records `fallback_used` with the failed IDs.
     The word lists are in diacausal/guards/output_guards.yaml. Checks 5, 6 and the causal half of 7 are word lists: they catch the
     obvious wordings, not every paraphrase. This module never imports diacausal.llm (a test enforces it).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from diacausal.api.schemas import AnswerDraftV1, CausalOutputV1, DriverV1, EligibleOptionsV1, GuardedDraftV1, OutputCheckV1
from diacausal.causal_inference.recommend import DOSE_PATTERN
from diacausal.config import load_rag_config
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


# ═══ the seven checks of plan 8.10 (P23) ═════════════════════════════════════════════════════════════════════════
CHECK_IDS = ("parse", "citations", "numbers", "dose_threshold", "excluded_option", "insufficient_wording", "identifier_causal")
CONFIG_PATH = Path(__file__).resolve().parent / "output_guards.yaml"

_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?")
# Digits that are part of a NAME, not a number: drug classes ("SGLT-2", "SGLT2i", "DPP-4", "DPP4"), "type 1" / "type 2", "HbA1c".
_NAME = re.compile(r"\b(?:sglt|dpp)[- ]?\d\w*|\btype[- ]?[12]\b|\bhba1c\b", re.I)


def load_output_guard_lists(path: Path = CONFIG_PATH) -> dict:
    """The word lists. A word YAML would read as something else (a bare no or yes becomes false or true) is refused, not skipped."""
    cfg = load_rag_config(path)
    for key in ("positive_cues", "negation_cues", "effect_cues", "causal_cues", "threshold_patterns"):
        if not all(isinstance(w, str) for w in cfg[key]):
            raise ValueError(f"{path.name}: {key} must be all text (quote a word like no or yes)")
    for arm, words in cfg["option_words"].items():
        if not all(isinstance(w, str) for w in words):
            raise ValueError(f"{path.name}: option_words.{arm} must be all text")
    return cfg


@lru_cache(maxsize=1)
def _lists() -> dict:
    cfg = load_output_guard_lists()
    return {"thresholds": [re.compile(p, re.I) for p in cfg["threshold_patterns"]], "option_words": cfg["option_words"],
            "positive": cfg["positive_cues"], "negation": cfg["negation_cues"], "effect": cfg["effect_cues"], "causal": cfg["causal_cues"],
            "driver_words": cfg["driver_words"], "causal_window": int(cfg["causal_window_words"])}


def _has_word(words: Iterable[str], text: str) -> bool:
    """True if any word or phrase is in the (lower-case) text: a long one anywhere (so "gliflozin" is found in "dapagliflozin"), a
    short one only as a whole word (so "age" is not found in "damage")."""
    for w in words:
        w = w.lower()
        if len(w) >= 6:
            if w in text:
                return True
        elif re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", text):
            return True
    return False


def _phrase(words: Iterable[str], text: str) -> bool:
    """True if any cue is in the text as a whole word or phrase."""
    return any(re.search(rf"(?<![a-z0-9]){re.escape(w.lower())}(?![a-z0-9])", text) for w in words)


def numbers_in(text: str) -> list[str]:
    """Every number written in the text, as written ("-0.9", "8.4", "2016"); a minus sign counts as part of the number. The digits
    inside names ("SGLT-2", "DPP-4", "type 2 diabetes", "HbA1c") are not numbers."""
    return [m.group() for m in _NUMBER.finditer(_NAME.sub(" ", text))]


def _normal(number: str) -> str:
    """One spelling per number, so "88", "88.0" and "-88.00" compare equal (a driver's value is exported as 88.0) and "0.50" equals
    "0.5"; the sign is wording ("falls by 0.9"), so it is dropped. Only trailing zeros after a decimal point go: "04" (the day of a
    version date) stays "04" and never lets a "4" through, and "0.038" never equals "0.04"."""
    n = number.lstrip("-").lstrip("+")
    if "." in n:
        n = n.rstrip("0").rstrip(".") or "0"
    return n


def draft_text(draft: AnswerDraftV1) -> str:
    """All the prose of a draft (what a clinician would read), for the number check."""
    return " ".join([draft.question_context, *[c.claim for c in draft.evidence_summary], draft.limitations])


def _prose(draft: AnswerDraftV1) -> list[str]:
    return [t for t in (draft.question_context, *[c.claim for c in draft.evidence_summary], draft.limitations) if t.strip()]


def _sentences_of(draft: AnswerDraftV1) -> list[str]:
    """Every sentence of the draft's prose, lower-case, apostrophes plain (the unit the wording checks look at)."""
    out = []
    for text in _prose(draft):
        for s in sentences(text.replace("’", "'")) or [text]:
            out.append(s.lower())
    return out


def numbers_match(draft: AnswerDraftV1, allowed_sources: Iterable[str], passages: list[dict]) -> tuple[bool, list[str]]:
    """Check 3 (plan 8.10): (ok, the numbers that are not allowed). A number is allowed if it appears in one of `allowed_sources` (the
    causal output and the drivers, as text), or is the page or a number of the version of a passage the draft cites."""
    allowed = {_normal(n) for text in allowed_sources for n in numbers_in(text)}
    by_id = {p["chunk_id"]: p for p in passages}
    cited = {cid for c in draft.evidence_summary for cid in c.chunk_ids}
    for cid in cited:
        p = by_id.get(cid)
        if p:
            allowed |= {_normal(n) for n in numbers_in(f"{p['citation']['page']} {p['citation']['version']}")}
    unlisted = [n for n in numbers_in(draft_text(draft)) if _normal(n) not in allowed]
    return not unlisted, unlisted


# ── check 1 ──────────────────────────────────────────────────────────────────────────────────────────────────────
def parse_draft(text: str) -> tuple[AnswerDraftV1 | None, str | None]:
    """Check 1: (the draft, None), or (None, "INVALID_JSON" | "SCHEMA_INVALID"). Nothing of the text is kept."""
    try:
        data = json.loads(text)
    except ValueError:
        return None, "INVALID_JSON"
    try:
        return AnswerDraftV1.model_validate(data), None
    except ValidationError:
        return None, "SCHEMA_INVALID"


# ── check 2 ──────────────────────────────────────────────────────────────────────────────────────────────────────
def keep_supported_claims(draft: AnswerDraftV1, passages: list[dict], min_support: float) -> tuple[list, int]:
    """Check 2: (the claims that stay, how many were dropped). A claim stays if it cites at least one chunk ID, every ID is a passage
    that was retrieved (and not withheld), and most of its words are in the passages it cites (the citation checker's rule)."""
    usable = {p["chunk_id"]: p for _, p in _usable(passages)}
    kept = []
    for claim in draft.evidence_summary:
        if not claim.chunk_ids or any(cid not in usable for cid in claim.chunk_ids):
            continue
        words = _content(claim.claim)
        support = set().union(*(_content(usable[cid]["text"]) for cid in claim.chunk_ids))
        if words and len(words & support) / len(words) >= min_support:
            kept.append(claim)
    return kept, len(draft.evidence_summary) - len(kept)


# ── check 4 ──────────────────────────────────────────────────────────────────────────────────────────────────────
def has_dose_or_threshold(draft: AnswerDraftV1) -> bool:
    text = draft_text(draft).replace("’", "'")
    return bool(DOSE_PATTERN.search(text)) or any(p.search(text) for p in _lists()["thresholds"])


# ── checks 5 and 6 ───────────────────────────────────────────────────────────────────────────────────────────────
def option_words(causal: CausalOutputV1, arm: str) -> list[str]:
    """The ways the draft may name an option: its class words (output_guards.yaml), its name and its example molecule."""
    words = list(_lists()["option_words"].get(arm, []))
    if len(arm) >= 4:
        words.append(arm)
    for o in causal.options:
        if o.arm == arm:
            words += [w for w in (o.name, o.example_molecule) if w]
    return [w.lower() for w in words]


def praises_excluded_option(draft: AnswerDraftV1, eligible: EligibleOptionsV1 | None, causal: CausalOutputV1) -> bool:
    """Check 5: a sentence names an option the rules removed AND uses a positive cue (recommend, suitable, effective, ...) without a
    negation cue (not, avoid, excluded, ...). Naming it to say why it was removed is fine."""
    lists = _lists()
    for arm in {h.option for h in eligible.excluded} if eligible else set():
        words = option_words(causal, arm)
        for s in _sentences_of(draft):
            if _has_word(words, s) and _phrase(lists["positive"], s) and not _phrase(lists["negation"], s):
                return True
    return False


def effect_wording_for_insufficient(draft: AnswerDraftV1, causal: CausalOutputV1) -> bool:
    """Check 6: a sentence names an option marked insufficient evidence AND uses effect wording (lowers, reduces, effect, ...) without
    saying that nothing can be stated (not, insufficient, uncertain, ...)."""
    lists = _lists()
    for o in causal.options:
        if o.status != "insufficient_evidence":
            continue
        words = option_words(causal, o.arm)
        for s in _sentences_of(draft):
            if _has_word(words, s) and _phrase(lists["effect"], s) and not _phrase(lists["negation"], s):
                return True
    return False


# ── check 7 ──────────────────────────────────────────────────────────────────────────────────────────────────────
def driver_names(drivers: Mapping[str, Sequence[DriverV1]] | None) -> list[str]:
    """The words a draft may use for a driver: the always-on patient values, every alias of a feature in DRIVERS, and (P26) the
    plain-words label the card shows for it (params.yaml xai.labels, e.g. "starting HbA1c", "diabetes duration")."""
    cfg = _lists()["driver_words"]
    names = list(cfg["always"])
    labels = _driver_labels()
    for rows in (drivers or {}).values():
        for d in rows:
            names += cfg["aliases"].get(d.feature, [d.feature.replace("_", " ")])
            if d.feature in labels:
                names.append(labels[d.feature])
    return sorted(set(n.lower() for n in names))


@lru_cache(maxsize=1)
def _driver_labels() -> dict[str, str]:
    from diacausal.config import load_params

    return {f: spec["text"] for f, spec in load_params().get("xai.labels").items()}


def has_identifier_text(draft: AnswerDraftV1) -> bool:
    from diacausal.guards.input_guards import has_identifier

    return any(has_identifier(t) for t in _prose(draft))


def _near(names: Iterable[str], cues: Iterable[str], sentence: str, window: int) -> bool:
    """True if a causal cue and a driver word are within `window` words of each other (either order) in the sentence."""
    for cue in cues:
        for m in re.finditer(rf"(?<![a-z0-9]){re.escape(cue.lower())}(?![a-z0-9])", sentence):
            before = " ".join(sentence[:m.start()].split()[-window:])
            after = " ".join(sentence[m.end():].split()[:window])
            if _has_word(names, before) or _has_word(names, after):
                return True
    return False


def has_causal_wording_about_a_driver(draft: AnswerDraftV1, drivers: Mapping[str, Sequence[DriverV1]] | None) -> bool:
    """A sentence in which a causal cue (because of, causes, leads to, ...) stands within a few words of a driver (age, HbA1c, eGFR, BMI, or
    a feature in DRIVERS). SHAP drivers describe the model, never a cause (AGENTS.md XAI RULE). A drug that "can cause" an adverse event in a
    sentence that merely mentions the patient's HbA1c is not flagged (benchmark finding, output_guards.yaml `causal_window_words`)."""
    names, lists = driver_names(drivers), _lists()
    return any(_near(names, lists["causal"], s, lists["causal_window"]) for s in _sentences_of(draft))


# ── all seven ────────────────────────────────────────────────────────────────────────────────────────────────────
def failed_checks(guarded: GuardedDraftV1) -> list[str]:
    return [c.id for c in guarded.checks if c.result == "FAIL"]


def _result(check_id: str, ok: bool) -> OutputCheckV1:
    return OutputCheckV1(id=check_id, result="PASS" if ok else "FAIL")


def run_output_guards(model_text: str | AnswerDraftV1, *, passages: list[dict], number_sources: Sequence[str], eligible: EligibleOptionsV1 | None,
                      causal: CausalOutputV1, drivers: Mapping[str, Sequence[DriverV1]] | None = None, min_support: float,
                      max_claims: int = 4) -> GuardedDraftV1:
    """The seven checks of plan 8.10 on what a model returned (its text, or a draft already parsed).

    `passages` are the retriever's passages (with chunk_id); `number_sources` the causal output and the drivers as text, exactly as the
    prompt showed them. Status: BLOCK (an identifier), else FALLBACK (check 1, 3, 4, 5, 6 or the causal half of 7 failed), else ABSTAIN
    (no claim survived check 2), else PASS with the kept claims (`dropped_claims` says how many went). A draft that says `insufficient`
    has no claims to check; checks 3 to 7 still read its prose. Nothing the model wrote is logged or put in a message."""
    if isinstance(model_text, AnswerDraftV1):
        draft, code = model_text, None
    else:
        draft, code = parse_draft(model_text)
    if draft is None:
        return GuardedDraftV1(status="FALLBACK", checks=[_result("parse", False)], fallback_reason=code)
    claims = draft.evidence_summary[:max_claims]
    cut = draft.model_copy(update={"evidence_summary": claims})
    if draft.insufficient:
        kept, dropped = claims, 0
    else:
        kept, dropped = keep_supported_claims(cut, passages, min_support)
    survivor = cut.model_copy(update={"evidence_summary": kept})
    identifier = has_identifier_text(survivor)
    results = {
        "parse": True, "citations": dropped == 0 and (bool(kept) or draft.insufficient),
        "numbers": numbers_match(survivor, number_sources, passages)[0], "dose_threshold": not has_dose_or_threshold(survivor),
        "excluded_option": not praises_excluded_option(survivor, eligible, causal),
        "insufficient_wording": not effect_wording_for_insufficient(survivor, causal),
        "identifier_causal": not identifier and not has_causal_wording_about_a_driver(survivor, drivers)}
    checks = [_result(i, results[i]) for i in CHECK_IDS]
    failed = [i for i in CHECK_IDS if not results[i]]
    hard = [i for i in failed if i != "citations"]
    if identifier:
        return GuardedDraftV1(status="BLOCK", checks=checks, dropped_claims=dropped, fallback_reason="GUARD_IDENTIFIER_CAUSAL")
    if hard:
        return GuardedDraftV1(status="FALLBACK", checks=checks, dropped_claims=dropped, fallback_reason=f"GUARD_{hard[0].upper()}")
    if not kept and not draft.insufficient:
        return GuardedDraftV1(status="ABSTAIN", checks=checks, dropped_claims=dropped, fallback_reason="GUARD_CITATIONS")
    return GuardedDraftV1(status="PASS", checks=checks, draft=survivor, dropped_claims=dropped)
