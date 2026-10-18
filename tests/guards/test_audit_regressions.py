"""Regressions found by the audit of 17 Oct 2026 (each case failed before the fix; see the pull request).

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

import pytest
from guard_helpers import make
from output_helpers import GOOD, draft, failed, run

from diacausal.guards import input_guards as g


def blocked(question):
    return {c.id for c in g.run_input_guards(make(question)).checks if c.result == "BLOCK"}


# 1. The emergency check must not be skipped because the message also holds a "knowledge" word (risk, versus, likely, compared).
@pytest.mark.parametrize("question", [
    "My patient is unconscious, which add-on carries less risk?",
    "He is unconscious and has DKA, what is the risk of adding an SGLT2 inhibitor?",
    "She is having a seizure, which add-on is likely to be safest?",
    "Patient is in diabetic ketoacidosis, SGLT2 inhibitor versus DPP-4 inhibitor?",
    "This patient collapsed, risk of sulfonylurea compared with DPP-4?",
])
def test_an_emergency_about_one_patient_is_never_a_general_drug_question(question):
    assert "red_flag" in blocked(question)


@pytest.mark.parametrize("question", [
    "Can SGLT2 inhibitors cause ketoacidosis?", "What is the risk of ketoacidosis with SGLT2 inhibitors?",
    "What are the symptoms of ketoacidosis in a patient taking an SGLT2 inhibitor?", "Does sitagliptin cause seizures?",
])
def test_a_question_about_a_drug_in_general_is_still_answerable(question):
    assert "red_flag" not in blocked(question)


# 1b. Identifiers hidden by fullwidth characters or zero-width characters; amounts of a drug asked in grams or words; more pregnancy words.
@pytest.mark.parametrize("question,check", [
    ("Phone ９８７６５４３２１０ for results", "identifier"), ("Call 9\u200b876543210", "identifier"), ("Email rao.k＠example.com", "identifier"),
    ("Give 2 g of metformin twice a day?", "dose_request"), ("What is the starting amount of glimepiride?", "dose_request"),
    ("What strength of sitagliptin?", "dose_request"), ("Which add-on in the third trimester?", "scope"),
    ("She is expecting a baby in March, which add-on?", "scope"),
])
def test_the_hidden_or_reworded_cases_are_now_stopped_by_their_own_check(question, check):
    assert check in blocked(question)


# 2. Output checks: the short name "SU" and the sulfonylurea molecules of the corpus count as naming the option.
@pytest.mark.parametrize("sentence", ["SU is a good choice for this patient.", "SUs are recommended here.", "Gliclazide is recommended for this patient.",
                                      "Glipizide would be a good choice here."])
def test_an_excluded_sulfonylurea_is_not_praised_under_any_of_its_names(sentence):
    assert failed(run(draft(GOOD, limitations=sentence), removed=("SU",))) == ["excluded_option"]


def test_effect_wording_about_an_insufficient_sulfonylurea_is_caught_by_its_short_name():
    assert "insufficient_wording" in failed(run(draft(GOOD, limitations="SU lowers HbA1c more than the other options."), status={"SU": "insufficient_evidence"}))


# 3. Output check 4: doses written in words or in grams.
@pytest.mark.parametrize("sentence", ["Take two tablets twice a day with meals.", "Start with 2 g of metformin.", "Give it every 12 hours.",
                                      "One capsule three times a day is usual."])
def test_a_dose_written_in_words_or_grams_fails_check_4(sentence):
    assert "dose_threshold" in failed(run(draft(GOOD, limitations=sentence)))


# 4. Output check 7: plain causal wording about a driver.
@pytest.mark.parametrize("sentence", ["The estimate is larger because the patient's HbA1c is high.", "A higher HbA1c explains the larger benefit.",
                                      "Kidney function drives the difference between the options."])
def test_plain_causal_words_about_a_driver_fail_check_7(sentence):
    assert "identifier_causal" in failed(run(draft(GOOD, limitations=sentence), features=("hba1c_pct", "egfr")))


def test_a_good_draft_still_passes():
    assert failed(run(draft(GOOD))) == []
