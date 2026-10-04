"""The new guards against the project's shared evidence: the 47 cases in shared/guard_rules/examples.v1.json (which the
chat app's page and server must also agree with) and the 60 gold questions of the RAG evaluation."""

import csv
import json
import sys

import pytest
from guard_helpers import ROOT, make

from diacausal.guards import input_guards as g

SHARED = ROOT / "shared" / "guard_rules"
CASES = json.loads((SHARED / "examples.v1.json").read_text(encoding="utf-8"))["cases"]

# What the shared file calls each outcome, in the guards of plan 8.6. DKA/HHS words are a red flag here (plan 8.6),
# an out-of-scope topic in the chat app; both stop the request.
GUARD_FOR = {"block:identifier": "identifier", "block:language": "length_language", "emergency": "red_flag",
             "out_of_scope:type_1": "scope", "out_of_scope:pregnancy": "scope", "out_of_scope:under_18": "scope",
             "out_of_scope:insulin_start": "scope", "out_of_scope:dka_hhs": "red_flag"}


def blocked_checks(text):
    result = g.run_input_guards(make(text))
    return {c.id for c in result.checks if c.result == "BLOCK"}, result


# The shared file was written for the chat app, which has no English-only rule and no dose guard. These three "pass"
# cases are the ones the new guards 6 and 7 stop on purpose (plan 8.6): everything else must agree.
KNOWN_DIFFERENCES = {
    "p07": "dose_request",  # "Assess renal function before titrating glimepiride."
    "p10": "dose_request",  # "Cumulative dose of glimepiride over 2 years?" ("dose of", plan 8.6)
    "p14": "length_language",  # Hindi text: the new guard is English only
}


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_the_guards_agree_with_the_shared_examples(case):
    blocked, result = blocked_checks(case["text"])
    if case["expect"] == "pass":
        expected = {KNOWN_DIFFERENCES[case["id"]]} if case["id"] in KNOWN_DIFFERENCES else set()
        assert blocked == expected, f"{case['id']} {case['text']!r}: expected {expected or 'a pass'}, got {blocked}"
    else:
        assert GUARD_FOR[case["expect"]] in blocked, f"{case['id']}: {case['expect']} must be caught by {GUARD_FOR[case['expect']]}"
        assert result.status == "BLOCK"


def test_the_known_differences_are_exactly_the_cases_that_only_guards_6_and_7_stop():
    stopped_only_by_new_guards = {
        c["id"] for c in CASES if c["expect"] == "pass" and blocked_checks(c["text"])[0] <= {"dose_request", "length_language"}
        and blocked_checks(c["text"])[0]}
    assert stopped_only_by_new_guards == set(KNOWN_DIFFERENCES)


def test_the_shared_reference_implementation_still_agrees_with_every_example():
    """The chat app's server and page are held to this file; if the examples or rules change, this fails first."""
    sys.path.insert(0, str(SHARED))
    import reference_guard

    assert [c["id"] for c in CASES if reference_guard.check(c["text"]) != c["expect"]] == []


def test_the_ported_helpers_give_the_same_answers_as_the_reference():
    sys.path.insert(0, str(SHARED))
    import reference_guard as ref

    for text in ["Not pregnant, history of seizures", "ALL CAPS Unconscious", "मधुमेह टाइप 2", "Fournier's gangrene", "x"]:
        assert g.words(text) == ref.words(text)
        assert g.phrase_hits(["seizures", "not pregnant"], text) == [i for _, i in ref._phrase_hits(["seizures", "not pregnant"], text)]
    for digits in ["726018159082", "726018159083", "500166131860", "5016613186"]:
        assert g.verhoeff_ok(digits) == ref.verhoeff_ok(digits)


GOLD = list(csv.DictReader((ROOT / "eval" / "rag_gold.csv").read_text(encoding="utf-8").splitlines()))


@pytest.mark.parametrize("row", [r for r in GOLD if r["category"] == "answerable"], ids=lambda r: r["id"])
def test_every_answerable_gold_question_passes_all_seven_guards(row):
    """A guard that stops a question the knowledge base can answer would make part of it unreachable (the first
    version blocked G05, G31-G33 and G35)."""
    blocked, _ = blocked_checks(row["question"])
    assert not blocked, f"{row['id']} {row['question']!r} was blocked by {blocked}"


@pytest.mark.parametrize("row", [r for r in GOLD if r["category"] == "dose"], ids=lambda r: r["id"])
def test_every_dose_gold_question_is_refused_by_the_dose_guard(row):
    blocked, _ = blocked_checks(row["question"])
    assert "dose_request" in blocked, row["question"]


def test_the_gold_questions_are_all_judged_without_error():
    for row in GOLD:
        g.run_input_guards(make(row["question"]))  # including the out-of-scope ones: no crash, any verdict
