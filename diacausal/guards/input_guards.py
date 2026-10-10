"""The seven input guards of docs/PLAN_2026-10.md section 8.6: scope, identifier, red flag, injection, range and unit,
length and language, dose request. All are deterministic text rules; none calls a model.

    run_input_guards(request) -> GuardResultV1      all seven, in the order of 8.6 (never stops early)
    scope(request) ... dose_request(request)        each returns a GuardResultV1 with its one check
    evaluate(request) -> list[GuardResultV1]         the seven separate results (the layer reads their messages)

REUSED, not rewritten:
  * the word lists and regexes (identifiers, out-of-scope topics, emergency phrases, foul language and its medical
    allowlist, the "not" / "history of" cues) are read from shared/guard_rules/rules.v1.json, the same file the chat
    app's page and server read; edit them there;
  * the helper functions (word splitting that keeps Devanagari whole, phrase matching, cue check, Verhoeff check
    digit) are PORTED from shared/guard_rules/reference_guard.py (standard library only; backend/app/pipeline/
    blocklist.py needs the third-party `regex` package and is not importable from here). tests/guards runs all 47
    shared examples through both, so the copies cannot drift;
  * the block wording for identifier, emergency, out of scope and "cannot answer as written" is the chat app's
    (frontend/src/components/chat/GuardNotice.tsx), and the dose wording is NO_DOSE_NOTE of the explanation layer.
NEW here (trigger values in data/params.yaml, section `guards`, all TEAM-SET): the length and language limits, the
glucose thresholds, honorific plus name, injection phrases, role tags and encoded blobs, the unit and range check of
numbers typed in the question, and the dose-request patterns.

A message NEVER repeats what matched (it could be the identifier itself): every message below is fixed text, and the
only words inserted into one come from this file's own lists (a topic name, a field name).

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from functools import lru_cache

from diacausal.api.schemas import AskRequestV1, GuardCheckV1, GuardResultV1
from diacausal.api.schemas.patient import RANGES
from diacausal.config import ROOT, Params, load_params

RULES_FILE = ROOT / "shared" / "guard_rules" / "rules.v1.json"
RULES: dict = json.loads(RULES_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _params() -> Params:
    return load_params()


def _p(name: str):
    return _params().get(f"guards.{name}")


# ── ported from shared/guard_rules/reference_guard.py ────────────────────────────────────────────────────────────
WORD = re.compile(r"(?:[^\W_]|[\u0300-\u036f\u0900-\u0903\u093a-\u094f\u0951-\u0957\u0962\u0963])+(?:'(?:[^\W_]|[\u0900-\u097f])+)*")

_D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],
      [5,9,8,7,6,0,4,3,2,1],[6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]  # fmt: skip
_P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],
      [4,2,8,6,5,7,3,9,0,1],[2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]  # fmt: skip


def verhoeff_ok(num: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(num)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def norm(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def words(text: str) -> list[str]:
    return WORD.findall(norm(text))


def phrase_hits(phrases, text: str) -> list[int]:
    """Word index where each whole-word phrase match starts."""
    joined = " " + " ".join(words(text)) + " "
    hits = []
    for phrase in phrases:
        key = " " + " ".join(words(phrase)) + " "
        start = joined.find(key)
        while start != -1:
            hits.append(len(joined[:start].split()))
            start = joined.find(key, start + 1)
    return hits


def cued(text: str, index: int) -> bool:
    """A negation or history cue in the few words before word `index` ("not pregnant", "history of seizures")."""
    toks = words(text)
    window = RULES["context_cues"]["window_words"]
    before = " ".join(toks[max(0, index - window):index])
    return any(f" {c} " in f" {before} " for c in RULES["context_cues"]["negation"] + RULES["context_cues"]["history"])


def _uncued_hit(phrases, text: str) -> bool:
    return any(not cued(text, i) for i in phrase_hits(phrases, text))


def _present_state(text: str) -> bool:
    return bool(phrase_hits(_p("present_state_words"), text))


def _about_drugs_in_general(text: str) -> bool:
    """"Can SGLT2 inhibitors cause ketoacidosis?" asks about a drug; "Admitted with DKA yesterday" reports a patient.
    A knowledge word makes the first reading, a present-state word cancels it."""
    return bool(phrase_hits(_p("knowledge_question_words"), text)) and not _present_state(text)


# ── plain-language messages (fixed text; nothing the user typed is ever repeated) ────────────────────────────────
MESSAGES = {
    "scope": "DiaCausal covers adults with type 2 diabetes already on metformin. {about} Use your usual guideline or refer as you normally would.",
    "identifier": "Please remove patient identifiers (Aadhaar, phone, PAN, email, names) and ask again. Describe the patient by age, sex, lab values and current therapy instead.",
    "red_flag": "This may be an emergency. Follow your emergency protocol. DiaCausal has not answered this question and will not suggest treatment for it.",
    "injection": "This message contains instructions aimed at the software itself, so it was not used. Please ask your clinical question in plain words.",
    "hba1c_unit": "HbA1c must be given in % (for example 8.4), not in mmol/mol. Please convert it and ask again.",
    "range": "A value in your question or the form is outside the range DiaCausal accepts ({name}). Please check the number and its unit.",
    "too_short": "Please write a little more: a question needs at least {n} characters.",
    "too_long": "Please shorten the question to {n} characters or fewer.",
    "not_english": "Please write your question in English.",
    "language": "Cannot answer as written. Please rephrase your question.",
    "dose_request": "DiaCausal never gives doses. Doses come only from the official drug label and the treating clinician.",
}
TOPIC_NAMES = {
    "type_1": "This question is about type 1 diabetes.",
    "pregnancy": "This question is about pregnancy or breastfeeding.",
    "under_18": "This question is about a patient under 18.",
    "insulin_start": "This question is about starting insulin.",
    "not_on_metformin": "This patient is marked as not on metformin.",
}
_LABELS = {"age": ("age", "years"), "duration_years": ("diabetes duration", "years"), "hba1c_pct": ("HbA1c", "%"),
           "egfr": ("eGFR", "mL/min/1.73m²"), "bmi": ("BMI", "kg/m²"), "waist_cm": ("waist", "cm"),
           "glucose_mg_dl": ("glucose", "mg/dL")}


def field_name(key: str) -> str:
    """e.g. "HbA1c 4 to 20 %": the label and the accepted range, both taken from RANGES (never typed twice)."""
    label, unit = _LABELS[key]
    low, high = RANGES[key]
    return f"{label} {low:g} to {high:g} {unit}"


def _result(check_id: str, blocked: str | None) -> GuardResultV1:
    return GuardResultV1(status="BLOCK" if blocked else "PASS",
                         checks=[GuardCheckV1(id=check_id, result="BLOCK" if blocked else "PASS")], blocked_reason=blocked)


# ── 1. scope ─────────────────────────────────────────────────────────────────────────────────────────────────────
_SCOPE_TOPICS = ("type_1", "pregnancy", "under_18", "insulin_start")
_AGE_TEXT = re.compile(r"\b(\d{1,3})\s*[- ]?(?:years?|yrs?|y)[- ]?(?:old|of age)\b|\baged?\s+(\d{1,3})\b", re.I)


def scope(request: AskRequestV1) -> GuardResultV1:
    """Adult, type 2, on metformin; type 1, pregnancy, children and starting insulin are out."""
    patient = request.patient
    if patient.type1:
        return _result("scope", MESSAGES["scope"].format(about=TOPIC_NAMES["type_1"]))
    if not patient.on_metformin:
        return _result("scope", MESSAGES["scope"].format(about=TOPIC_NAMES["not_on_metformin"]))
    if patient.age < RANGES["age"][0]:
        return _result("scope", MESSAGES["scope"].format(about=TOPIC_NAMES["under_18"]))
    text = request.question
    label_question = bool(phrase_hits(_p("label_question_words"), text)) and not _present_state(text)
    for topic in _SCOPE_TOPICS:
        if topic == "type_1" and label_question:
            continue  # "are SGLT2 inhibitors approved for type 1 diabetes?" asks about the label
        if _uncued_hit(RULES["out_of_scope"][topic], text):
            return _result("scope", MESSAGES["scope"].format(about=TOPIC_NAMES[topic]))
    for m in _AGE_TEXT.finditer(text):
        value = int(m.group(1) or m.group(2))
        if value < RANGES["age"][0] and not cued(text, len(words(text[: m.start()]))):
            return _result("scope", MESSAGES["scope"].format(about=TOPIC_NAMES["under_18"]))
    return _result("scope", None)


# ── 2. identifier ────────────────────────────────────────────────────────────────────────────────────────────────
def _identifier_patterns() -> list[tuple[re.Pattern, bool]]:
    out = []
    for spec in RULES["identifiers"].values():
        flags = re.I if spec.get("flags") == "i" else 0
        out.append((re.compile(spec["regex"], flags), spec.get("extra_check") == "verhoeff"))
    return out


_IDENTIFIERS = _identifier_patterns()


@lru_cache(maxsize=1)
def _honorific_name() -> re.Pattern:
    titles = "|".join(re.escape(t) for t in _p("honorifics"))
    return re.compile(rf"(?i:\b(?:{titles})\b)\.?\s+[A-Z\u0900-\u097F][^\W\d_]+")


def has_identifier(text: str) -> bool:
    """True if the text holds an Aadhaar, ABHA, Indian mobile, PAN, email, or an honorific followed by a name. Cues are ignored here.
    Also used by the output guards (P23) on a model's draft."""
    need_checksum = bool(_p("aadhaar_checksum_required"))
    for pattern, is_aadhaar in _IDENTIFIERS:
        for m in pattern.finditer(text):
            if is_aadhaar and need_checksum and not verhoeff_ok(re.sub(r"\D", "", m.group())):
                continue
            return True
    return bool(_honorific_name().search(text))


def identifier(request: AskRequestV1) -> GuardResultV1:
    """Aadhaar, ABHA, Indian mobile, PAN, email, and an honorific followed by a name. Cues are ignored here."""
    return _result("identifier", MESSAGES["identifier"] if has_identifier(request.question) else None)


# ── 3. red flag ──────────────────────────────────────────────────────────────────────────────────────────────────
_GLUCOSE = re.compile(RULES["emergency"]["glucose_value_regex"], re.I)


def _to_mg_dl(value: float, unit: str | None) -> float:
    return value * _p("mmol_to_mg_dl") if (unit or "mg/dl").lower().startswith("mmol") else value


def _glucose_is_emergency(mg_dl: float) -> bool:
    return mg_dl < _p("glucose_low_below_mg_dl") or mg_dl > _p("glucose_high_above_mg_dl")


def red_flag(request: AskRequestV1) -> GuardResultV1:
    """DKA, unconsciousness, seizure, severe hypoglycaemia, or a glucose below 54 or above 400 mg/dL in the question
    or the form. A "not" / "history of" cue just before the words cancels the text match (the form value never is)."""
    text = request.question
    words_alone = _uncued_hit(RULES["emergency"]["phrases"], text) or _uncued_hit(RULES["out_of_scope"]["dka_hhs"], text)
    if words_alone and not _about_drugs_in_general(text):
        return _result("red_flag", MESSAGES["red_flag"])
    for m in _GLUCOSE.finditer(text):
        mg_dl = _to_mg_dl(float(m.group(1)), m.group(2))
        if _glucose_is_emergency(mg_dl) and not cued(text, len(words(text[: m.start()]))):
            return _result("red_flag", MESSAGES["red_flag"])
    if request.patient.glucose_mg_dl is not None and _glucose_is_emergency(request.patient.glucose_mg_dl):
        return _result("red_flag", MESSAGES["red_flag"])
    return _result("red_flag", None)


# ── 4. injection ─────────────────────────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _role_tags() -> list[re.Pattern]:
    return [re.compile(pattern) for pattern in _p("injection_role_tags")]


def _looks_encoded(text: str) -> bool:
    for m in re.finditer(r"[A-Za-z0-9+/]{%d,}={0,2}" % int(_p("base64_min_run")), text):
        run = m.group()
        if any(c.isupper() for c in run) and any(c.islower() for c in run) and any(c.isdigit() for c in run):
            return True
    return False


def injection(request: AskRequestV1) -> GuardResultV1:
    text = request.question
    if phrase_hits(_p("injection_phrases"), text) or any(p.search(text) for p in _role_tags()) or _looks_encoded(text):
        return _result("injection", MESSAGES["injection"])
    return _result("injection", None)


# ── 5. range and unit ────────────────────────────────────────────────────────────────────────────────────────────
_NUM = r"(\d{1,4}(?:\.\d+)?)"
_TEXT_VALUES = {
    "hba1c": re.compile(r"(?:\bhb\s?a1c\b|\ba1c\b|\bglycated h(?:a)?emoglobin\b)\D{0,12}?" + _NUM + r"\s*(%|mmol\s*/\s*mol|mmol per mol|ifcc)?", re.I),
    "egfr": re.compile(r"\begfr\b\D{0,12}?" + _NUM, re.I),
    "bmi": re.compile(r"\bbmi\b\D{0,12}?" + _NUM, re.I),
    "glucose": re.compile(r"\b(?:glucose|sugar|cbg|rbs|fbs|grbs|bg)\b\D{0,12}?" + _NUM + r"\s*(mg/dl|mmol/l|mmol)?", re.I),
}
_RANGE_KEY = {"hba1c": "hba1c_pct", "egfr": "egfr", "bmi": "bmi", "glucose": "glucose_mg_dl"}


def _is_a_time(text: str, end: int) -> bool:
    ignore = "|".join(_p("number_followed_by_words_to_ignore"))
    return re.match(rf"\s*(?:{ignore})\b", text[end:], re.I) is not None


def range_unit(request: AskRequestV1) -> GuardResultV1:
    """The ranges of plan 8.2 (docs/INPUT_RANGES.md), for the form fields and for values typed in the question.
    HbA1c in mmol/mol, or above 20, is refused with a request for %."""
    patient = request.patient.model_dump()
    for name, (low, high) in RANGES.items():
        value = patient.get(name)
        if value is None:
            continue
        if not low <= value <= high:
            return _result("range", MESSAGES["hba1c_unit"] if name == "hba1c_pct" and value > high else MESSAGES["range"].format(name=field_name(name)))
    text = request.question
    for name, pattern in _TEXT_VALUES.items():
        for m in pattern.finditer(text):
            if _is_a_time(text, m.end(1)):
                continue
            value = float(m.group(1))
            unit = (m.group(2) or "").lower().replace(" ", "") if pattern.groups >= 2 else ""
            if name == "hba1c":
                if unit in {w.replace(" ", "") for w in _p("mmol_per_mol_words")} or value > RANGES["hba1c_pct"][1]:
                    return _result("range", MESSAGES["hba1c_unit"])
            if name == "glucose":
                value = _to_mg_dl(value, unit)
            low, high = RANGES[_RANGE_KEY[name]]
            if not low <= value <= high:
                return _result("range", MESSAGES["range"].format(name=field_name(_RANGE_KEY[name])))
    for m in _AGE_TEXT.finditer(text):
        if int(m.group(1) or m.group(2)) > RANGES["age"][1]:
            return _result("range", MESSAGES["range"].format(name=field_name("age")))
    return _result("range", None)


# ── 6. length and language ───────────────────────────────────────────────────────────────────────────────────────
_BLOCKED_WORDS = set(RULES["profanity"]["blocked_words"])
_ALLOWED_WORDS = set(RULES["medical_allowlist"])


def _is_latin(ch: str) -> bool:
    return unicodedata.name(ch, "").startswith("LATIN")


def length_language(request: AskRequestV1) -> GuardResultV1:
    """3 to 500 characters, English, and no foul language (the chat app's list, with its medical allowlist)."""
    text = request.question
    n = len(text.strip())
    if n < _p("question_min_chars"):
        return _result("length_language", MESSAGES["too_short"].format(n=_p("question_min_chars")))
    if n > _p("question_max_chars"):
        return _result("length_language", MESSAGES["too_long"].format(n=_p("question_max_chars")))
    letters = [ch for ch in text if ch.isalpha()]
    if not letters or sum(not _is_latin(ch) for ch in letters) / len(letters) > _p("non_latin_letter_share_max"):
        return _result("length_language", MESSAGES["not_english"] if letters else MESSAGES["language"])
    if any(w in _BLOCKED_WORDS and w not in _ALLOWED_WORDS for w in words(text)) or phrase_hits(RULES["profanity"]["blocked_phrases"], text):
        return _result("length_language", MESSAGES["language"])
    return _result("length_language", None)


# ── 7. dose request ──────────────────────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _dose_patterns() -> list[re.Pattern]:
    return [re.compile(pattern, re.I) for pattern in _p("dose_patterns")]


def dose_request(request: AskRequestV1) -> GuardResultV1:
    """A request for an amount of a drug. Doses come only from the cited tables, never from this system."""
    text = unicodedata.normalize("NFKC", request.question)
    if any(p.search(text) for p in _dose_patterns()):
        return _result("dose_request", MESSAGES["dose_request"])
    return _result("dose_request", None)


# ── all seven ────────────────────────────────────────────────────────────────────────────────────────────────────
GUARDS: tuple[tuple[str, Callable[[AskRequestV1], GuardResultV1]], ...] = (  # the order of plan 8.6
    ("scope", scope), ("identifier", identifier), ("red_flag", red_flag), ("injection", injection),
    ("range", range_unit), ("length_language", length_language), ("dose_request", dose_request),
)
# Which message is shown when several guards block: an emergency first (it must never hide behind another notice),
# then the order of 8.6.
SHOW_FIRST = ("red_flag", "scope", "identifier", "injection", "range", "length_language", "dose_request")
CODES = {"scope": "OUT_OF_SCOPE", "identifier": "IDENTIFIER", "red_flag": "RED_FLAG", "injection": "INJECTION",
         "range": "OUT_OF_RANGE", "length_language": "LENGTH_OR_LANGUAGE", "dose_request": "DOSE_REQUEST"}


def evaluate(request: AskRequestV1) -> list[GuardResultV1]:
    """The seven results, in the order of 8.6. All seven always run."""
    return [fn(request) for _, fn in GUARDS]


def combine(results: list[GuardResultV1]) -> GuardResultV1:
    by_id = {r.checks[0].id: r for r in results}
    blocked = [cid for cid in SHOW_FIRST if by_id[cid].status == "BLOCK"]
    return GuardResultV1(status="BLOCK" if blocked else "PASS", checks=[r.checks[0] for r in results],
                         blocked_reason=by_id[blocked[0]].blocked_reason if blocked else None)


def run_input_guards(request: AskRequestV1) -> GuardResultV1:
    return combine(evaluate(request))
