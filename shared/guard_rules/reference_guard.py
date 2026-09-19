"""Reference implementation of rules.v1.json — used only to prove the examples file is
consistent. The real guards live in frontend/src/lib/guards.ts and backend_guard.py and
must give the same answer on every case in examples.v1.json."""
import json, re, sys, unicodedata
from pathlib import Path

HERE = Path(__file__).parent
RULES = json.loads((HERE / "rules.v1.json").read_text(encoding="utf-8"))
WORD = re.compile(r"(?:[^\W_]|[\u0300-\u036f\u0900-\u0903\u093a-\u094f\u0951-\u0957\u0962\u0963])+(?:'(?:[^\W_]|[\u0900-\u097f])+)*")

_D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],
      [5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]
_P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],
      [4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]
def verhoeff_ok(num: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(num)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0

def norm(text): return unicodedata.normalize("NFKC", text).casefold()
def words(text): return WORD.findall(norm(text))

def _phrase_hits(phrases, text):
    joined = " " + " ".join(words(text)) + " "
    hits = []
    for p in phrases:
        key = " " + " ".join(words(p)) + " "
        start = joined.find(key)
        while start != -1:
            hits.append((p, len(joined[:start].split())))
            start = joined.find(key, start + 1)
    return hits

def _cued(text, index):
    toks = words(text)
    before = " ".join(toks[max(0, index - RULES["context_cues"]["window_words"]):index])
    cues = RULES["context_cues"]["negation"] + RULES["context_cues"]["history"]
    return any(f" {c} " in f" {before} " for c in cues)

def check(text: str) -> str:
    # 1. identifiers (original text, cues ignored)
    for name, spec in RULES["identifiers"].items():
        flags = re.I if spec.get("flags") == "i" else 0
        for m in re.finditer(spec["regex"], text, flags):
            if spec.get("extra_check") == "verhoeff" and not verhoeff_ok(re.sub(r"\D", "", m.group())):
                continue
            return "block:identifier"
    # 2. profanity (allowlist wins)
    allow = set(RULES["medical_allowlist"])
    blocked = set(RULES["profanity"]["blocked_words"])
    if any(w in blocked and w not in allow for w in words(text)) or _phrase_hits(RULES["profanity"]["blocked_phrases"], text):
        return "block:language"
    # 3. emergency (phrases + glucose values), cancelled by negation/history cues
    for p, i in _phrase_hits(RULES["emergency"]["phrases"], text):
        if not _cued(text, i):
            return "emergency"
    for m in re.finditer(RULES["emergency"]["glucose_value_regex"], text, re.I):
        v = float(m.group(1)); unit = (m.group(2) or "mg/dl").lower()
        mgdl = v * RULES["emergency"]["mmol_to_mgdl"] if unit.startswith("mmol") else v
        idx = len(words(text[:m.start()]))
        if (mgdl < 54 or mgdl >= 600) and not _cued(text, idx):
            return "emergency"
    # 4. out of scope, cancelled by cues
    for cat, phrases in RULES["out_of_scope"].items():
        if cat == "note": continue
        for p, i in _phrase_hits(phrases, text):
            if not _cued(text, i):
                return f"out_of_scope:{cat}"
    return "pass"

if __name__ == "__main__":
    cases = json.loads((HERE / "examples.v1.json").read_text(encoding="utf-8"))["cases"]
    bad = [(c["id"], c["expect"], check(c["text"])) for c in cases if check(c["text"]) != c["expect"]]
    for b in bad: print("MISMATCH", b)
    print(f"{len(cases) - len(bad)}/{len(cases)} cases match")
    sys.exit(1 if bad else 0)
