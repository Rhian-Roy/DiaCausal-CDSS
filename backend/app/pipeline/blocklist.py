"""The shared guard rules: identifiers, foul language, emergencies, out of scope.

Every list comes from ONE file, shared/guard_rules/rules.v1.json, which the browser
(frontend/src/lib/guards.ts) loads too. So the page and the server give the same
answer; the server's answer is the one that counts, because a request can reach
the API without going through the page. Both are tested against every case in
shared/guard_rules/examples.v1.json, and must agree with reference_guard.py.

Order (first match wins): identifier -> language -> emergency -> out of scope.
- Identifiers and language ignore context: "no Aadhaar 5016 6131 8603" still blocks.
- A negation or history cue up to 4 words BEFORE an emergency or out-of-scope match
  cancels it ("not pregnant", "history of seizures").
- The medical allowlist always wins over the blocklist ("anal fissure" passes).

The matched word is never returned to the user or written to the log.
"""

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import regex

RULES_FILE = Path(__file__).resolve().parents[3] / "shared" / "guard_rules" / "rules.v1.json"
RULES: dict = json.loads(RULES_FILE.read_text(encoding="utf-8"))
RULES_VERSION: str = RULES["version"]

# A word = letters + combining marks + digits, so Devanagari words stay whole
# ("मधुमेह" is one word, not four). An apostrophe inside a word keeps it whole ("fournier's").
_WORD = regex.compile(r"[\p{L}\p{M}\p{N}]+(?:'[\p{L}\p{M}\p{N}]+)*")

BLOCKED_TERMS: frozenset[str] = frozenset(RULES["profanity"]["blocked_words"])
BLOCKED_PHRASES: tuple[str, ...] = tuple(RULES["profanity"]["blocked_phrases"])
MEDICAL_ALLOWLIST: frozenset[str] = frozenset(RULES["medical_allowlist"])

_CUES = RULES["context_cues"]
_CUE_WINDOW: int = _CUES["window_words"]
_EMERGENCY = RULES["emergency"]
_GLUCOSE = regex.compile(_EMERGENCY["glucose_value_regex"], regex.IGNORECASE)
_LOW_MGDL, _HIGH_MGDL = (t["value_mg_dl"] for t in _EMERGENCY["thresholds"])
OUT_OF_SCOPE: dict[str, list[str]] = {k: v for k, v in RULES["out_of_scope"].items() if k != "note"}

ScopeTopic = Literal["type_1", "pregnancy", "under_18", "dka_hhs", "insulin_start"]


@dataclass(frozen=True)
class _Identifier:
    pattern: regex.Pattern
    verhoeff: bool


_IDENTIFIERS = [
    _Identifier(
        regex.compile(spec["regex"], regex.IGNORECASE if spec.get("flags") == "i" else 0),
        spec.get("extra_check") == "verhoeff",
    )
    for spec in RULES["identifiers"].values()
]


# ── helpers ──────────────────────────────────────────────────────────────────

# Verhoeff check digit (Aadhaar's last digit): a 12-digit number that fails it is not an Aadhaar.
_D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],
      [5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]  # fmt: skip
_P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],
      [4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]  # fmt: skip


def verhoeff_ok(digits: str) -> bool:
    check = 0
    for i, ch in enumerate(reversed(digits)):
        check = _D[check][_P[i % 8][int(ch)]]
    return check == 0


def words(text: str) -> list[str]:
    """Normalised words: Unicode NFKC, case-folded, whole words only."""
    return _WORD.findall(unicodedata.normalize("NFKC", text).casefold())


def _phrase_positions(phrases: list[str] | tuple[str, ...], text: str) -> list[int]:
    """Word index where each whole-word phrase match starts."""
    joined = " " + " ".join(words(text)) + " "
    positions = []
    for phrase in phrases:
        key = " " + " ".join(words(phrase)) + " "
        start = joined.find(key)
        while start != -1:
            positions.append(len(joined[:start].split()))
            start = joined.find(key, start + 1)
    return positions


def _cued(text: str, index: int) -> bool:
    """Is there a negation or history cue in the few words before word `index`?"""
    before = " " + " ".join(words(text)[max(0, index - _CUE_WINDOW) : index]) + " "
    return any(f" {cue} " in before for cue in _CUES["negation"] + _CUES["history"])


# ── the checks ───────────────────────────────────────────────────────────────


def has_identifier(text: str) -> bool:
    for identifier in _IDENTIFIERS:
        for match in identifier.pattern.finditer(text):
            if identifier.verhoeff and not verhoeff_ok(regex.sub(r"\D", "", match.group())):
                continue
            return True
    return False


def find_blocked_term(text: str) -> str | None:
    """The first blocked word or phrase in `text`, or None. For internal use only:
    callers must never show or log what it returns."""
    for word in words(text):
        if word in BLOCKED_TERMS and word not in MEDICAL_ALLOWLIST:
            return word
    for phrase in BLOCKED_PHRASES:
        if _phrase_positions([phrase], text):
            return phrase
    return None


def is_emergency(text: str) -> bool:
    if any(not _cued(text, i) for i in _phrase_positions(_EMERGENCY["phrases"], text)):
        return True
    for match in _GLUCOSE.finditer(text):
        value = float(match.group(1))
        unit = (match.group(2) or "mg/dl").lower()
        mg_dl = value * _EMERGENCY["mmol_to_mgdl"] if unit.startswith("mmol") else value
        if (mg_dl < _LOW_MGDL or mg_dl >= _HIGH_MGDL) and not _cued(text, len(words(text[: match.start()]))):
            return True
    return False


def out_of_scope_topic(text: str) -> ScopeTopic | None:
    for topic, phrases in OUT_OF_SCOPE.items():
        if any(not _cued(text, i) for i in _phrase_positions(phrases, text)):
            return topic  # type: ignore[return-value]
    return None


def check(text: str) -> str:
    """The verdict in the words of examples.v1.json: "pass", "block:identifier",
    "block:language", "emergency" or "out_of_scope:<topic>"."""
    if has_identifier(text):
        return "block:identifier"
    if find_blocked_term(text):
        return "block:language"
    if is_emergency(text):
        return "emergency"
    if topic := out_of_scope_topic(text):
        return f"out_of_scope:{topic}"
    return "pass"
