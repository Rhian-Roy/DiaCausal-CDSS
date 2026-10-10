"""Write web/guards.json: everything web/guards.js needs to run the seven input guards in the browser (P27).

    python -m diacausal.guards.export_web

Nothing is typed into web/guards.js: the word lists come from shared/guard_rules/rules.v1.json, the trigger values from
data/params.yaml (section `guards`), the ranges from diacausal/api/schemas/patient.py, the messages and the patterns from
diacausal/guards/input_guards.py. Python regular expressions are translated here to JavaScript ones that mean the same
(`(?im)` at the start becomes the flags; `[^\\W_]` becomes `[\\p{L}\\p{N}]` and `[^\\W\\d_]` becomes `\\p{L}` under the `u` flag;
the honorific's case-insensitive titles are spelled out letter by letter). tests/web runs both on the same questions and
fails if they differ, or if this file is stale.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import json
import re

from diacausal import INTENDED_USE
from diacausal.api.schemas.patient import RANGES
from diacausal.config import WEB_DIR, file_hash, load_params
from diacausal.guards import input_guards as g

OUT = WEB_DIR / "guards.json"


def js_regex(pattern: str, flags: str = "") -> dict:
    """{source, flags} of the JavaScript regular expression that means the same as the Python one (always with `u`)."""
    m = re.match(r"^\(\?([a-z]+)\)", pattern)
    if m:
        flags += m.group(1)
        pattern = pattern[m.end():]
    pattern = pattern.replace("[^\\W\\d_]", "\\p{L}").replace("[^\\W_]", "[\\p{L}\\p{N}]")
    if "(?" in pattern.replace("(?:", "").replace("(?<!", "").replace("(?<=", "").replace("(?!", "").replace("(?=", ""):
        raise ValueError(f"a Python-only construct is left in {pattern!r}")
    return {"source": pattern, "flags": "".join(sorted(set(flags + "u")))}


def _either_case(text: str) -> str:
    """"mr" -> "[mM][rR]": a case-insensitive word inside an otherwise case-sensitive pattern, written for JavaScript."""
    return "".join(f"[{c.lower()}{c.upper()}]" if c.isalpha() else re.escape(c) for c in text)


def guards_dict() -> dict:
    params = load_params()
    p = params.group("guards")
    rules = g.RULES
    titles = "|".join(_either_case(t) for t in p["honorifics"])
    return {
        "intended_use": INTENDED_USE,
        "versions": {"rules_v1": rules["version"], "params_sha": params.fingerprint, "guards_sha": file_hash(g.__file__.replace(".pyc", ".py"))},
        "params": {k: v for k, v in p.items() if k not in ("dose_patterns", "injection_role_tags", "honorifics")},
        "rules": {"context_cues": rules["context_cues"], "out_of_scope": {k: v for k, v in rules["out_of_scope"].items() if k != "note"},
                  "emergency_phrases": rules["emergency"]["phrases"], "blocked_words": rules["profanity"]["blocked_words"],
                  "blocked_phrases": rules["profanity"]["blocked_phrases"], "medical_allowlist": rules["medical_allowlist"]},
        "regex": {
            "word": js_regex(g.WORD.pattern, "g"),
            "identifiers": [js_regex(spec["regex"], "g" + ("i" if spec.get("flags") == "i" else "")) | {"verhoeff": spec.get("extra_check") == "verhoeff"}
                            for spec in rules["identifiers"].values()],
            "honorific_name": js_regex(rf"\b(?:{titles})\b\.?\s+[A-Zऀ-ॿ][^\W\d_]+"),
            "glucose": js_regex(rules["emergency"]["glucose_value_regex"], "gi"),
            "age_text": js_regex(g._AGE_TEXT.pattern, "gi"),
            "text_values": {name: js_regex(rx.pattern, "gi") for name, rx in g._TEXT_VALUES.items()},
            "role_tags": [js_regex(x) for x in p["injection_role_tags"]],
            "dose": [js_regex(x, "i") for x in p["dose_patterns"]],
            "base64": js_regex(r"[A-Za-z0-9+/]{%d,}={0,2}" % int(p["base64_min_run"]), "g"),
        },
        "messages": g.MESSAGES,
        "topic_names": g.TOPIC_NAMES,
        "scope_topics": list(g._SCOPE_TOPICS),
        "range_key": g._RANGE_KEY,
        "ranges": {k: list(v) for k, v in RANGES.items()},
        "range_names": {k: g.field_name(k) for k in RANGES},
        "order": [name for name, _ in g.GUARDS],
        "show_first": list(g.SHOW_FIRST),
        "codes": g.CODES,
    }


def export() -> dict:
    data = guards_dict()
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


if __name__ == "__main__":
    export()
    print(f"wrote {OUT}")
