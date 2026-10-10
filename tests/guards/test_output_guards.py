"""The seven output checks of docs/PLAN_2026-10.md section 8.10 (P23): at least three adversarial drafts for each, and clean drafts
that must pass. The wording checks (5, 6 and the causal half of 7) are word lists: these tests show what they catch and what they leave."""

import json

import pytest
from output_helpers import GOOD, GOOD2, PASSAGES, SOURCES, draft, eligible, failed, run

from diacausal.api.schemas import GuardedDraftV1
from diacausal.guards.output_guards import CHECK_IDS, numbers_in, numbers_match, parse_draft
from diacausal.rag.retrieve.hybrid import WITHHELD

# ── a clean draft ────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_clean_draft_passes_all_seven_checks_in_the_plans_order():
    g = run(draft(GOOD, GOOD2))
    assert g.status == "PASS" and [c.id for c in g.checks] == list(CHECK_IDS) and all(c.result == "PASS" for c in g.checks)
    assert len(g.draft.evidence_summary) == 2 and g.dropped_claims == 0 and g.fallback_reason is None
    GuardedDraftV1.model_validate(g.model_dump())  # a valid contract object


def test_the_result_is_a_guarded_draft_whose_failures_carry_a_code_and_no_draft():
    g = run("not json")
    assert g.status == "FALLBACK" and g.draft is None and g.fallback_reason == "INVALID_JSON"


def test_all_checks_run_so_every_failed_check_is_recorded():
    bad = draft(GOOD, context="Take it twice daily.", limitations="SGLT2 inhibitors are the best choice and lower HbA1c by 9.99 points.")
    g = run(bad, removed=["SGLT2i"])
    assert g.status == "FALLBACK" and set(failed(g)) == {"numbers", "dose_threshold", "excluded_option"} and g.fallback_reason == "GUARD_NUMBERS"


# ── 1 parse ──────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,code", [
    ("this is not json", "INVALID_JSON"), ('{"question_context": "x"', "INVALID_JSON"), ("", "INVALID_JSON"),
    ('{"question_context": "x"}', "SCHEMA_INVALID"), ("[]", "SCHEMA_INVALID"), ("null", "SCHEMA_INVALID"),
    (draft(extra_field=1), "SCHEMA_INVALID"), (json.dumps({"question_context": 1, "evidence_summary": [], "limitations": "y"}), "SCHEMA_INVALID"),
    (json.dumps({"question_context": "x", "evidence_summary": [{"claim": "c"}], "limitations": "y"}), "SCHEMA_INVALID")])
def test_check_1_a_draft_that_does_not_parse_falls_back(text, code):
    g = run(text)
    assert g.status == "FALLBACK" and failed(g) == ["parse"] and [c.id for c in g.checks] == ["parse"] and g.fallback_reason == code


def test_check_1_an_already_parsed_draft_passes_the_check():
    parsed, code = parse_draft(draft())
    assert code is None and run(parsed).checks[0].id == "parse" and run(parsed).checks[0].result == "PASS"


# ── 2 citations ──────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("claim", [("SGLT2 inhibitors can cause ketoacidosis.", ["S99-00-00"]),  # a chunk ID that was never retrieved
                                   ("SGLT2 inhibitors can cause ketoacidosis.", []),  # no citation at all
                                   ("SGLT2 inhibitors can cause ketoacidosis.", ["S20-00-00", "S99-00-00"]),  # one real, one invented
                                   ("Oranges cure everything in a dark quiet room tonight.", ["S20-00-00"]),  # a real ID, a claim it does not support
                                   ("SGLT2 inhibitors can cause ketoacidosis.", ["s20-00-00"])])  # an ID that differs by case is a different ID
def test_check_2_a_claim_with_a_bad_citation_is_dropped_and_with_none_left_the_draft_abstains(claim):
    g = run(draft(claim))
    assert g.status == "ABSTAIN" and g.draft is None and g.dropped_claims == 1 and failed(g) == ["citations"] and g.fallback_reason == "GUARD_CITATIONS"


def test_check_2_only_the_bad_claim_goes_the_good_ones_stay():
    g = run(draft(GOOD, ("Oranges cure everything in a dark quiet room tonight.", ["S20-00-00"]), GOOD2, ("A made-up claim.", ["S99-00-00"])))
    assert g.status == "PASS" and g.dropped_claims == 2 and failed(g) == ["citations"]
    assert [c.chunk_ids for c in g.draft.evidence_summary] == [["S20-00-00"], ["S01-12-00"]]


def test_check_2_a_withheld_passage_cannot_be_cited():
    withheld = [{**PASSAGES[0], "text": WITHHELD}, PASSAGES[1]]
    assert run(draft(GOOD), passages=withheld).status == "ABSTAIN" and run(draft(GOOD2), passages=withheld).status == "PASS"


def test_check_2_at_most_max_claims_are_looked_at():
    g = run(draft(*[GOOD] * 6), max_claims=2)
    assert g.status == "PASS" and len(g.draft.evidence_summary) == 2 and g.dropped_claims == 0


def test_check_2_an_insufficient_draft_with_no_claims_passes():
    text = json.dumps({"question_context": "x", "evidence_summary": [], "limitations": "No passage answers this.", "insufficient": True})
    g = run(text)
    assert g.status == "PASS" and g.draft.insufficient and g.draft.evidence_summary == []


# ── 3 numbers ────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("where,text", [("limitations", "The estimate is -0.93 points."), ("context", "About 30 percent of patients had it."),
                                        ("claim", "SGLT2 inhibitors can cause ketoacidosis in 4 patients."), ("limitations", "Studied in 2019."),
                                        ("limitations", "Zero point nine is fine but 0.5 is not.")])
def test_check_3_an_invented_number_anywhere_in_the_text_falls_back(where, text):
    if where == "claim":
        g = run(draft(("SGLT2 inhibitors can cause ketoacidosis in 4 patients.", ["S20-00-00"])))
    else:
        g = run(draft(GOOD, **({"limitations": text} if where == "limitations" else {"context": text})))
    assert g.status == "FALLBACK" and "numbers" in failed(g) and g.fallback_reason == "GUARD_NUMBERS"


def test_check_3_a_number_from_the_causal_output_or_a_cited_page_or_version_is_allowed():
    ok = draft(GOOD, limitations="See the 2015-12-04 announcement on page 2. The estimate is -0.882, range -0.974 to -0.791.")
    assert run(ok).status == "PASS"
    assert run(draft(GOOD, limitations="See page 77.")).status == "FALLBACK"  # no cited passage has page 77
    assert run(draft(GOOD, GOOD2, limitations="See page 12.")).status == "PASS"


def test_check_3_digits_inside_names_are_not_numbers():
    assert numbers_in("SGLT-2, DPP-4, SGLT2i, type 2 diabetes and HbA1c at -0.9") == ["-0.9"]
    assert run(draft(GOOD, limitations="HbA1c in type 2 diabetes with an SGLT2 or DPP-4 inhibitor.")).status == "PASS"


def test_check_3_numbers_match_reports_which_numbers_are_not_allowed():
    parsed = parse_draft(draft(GOOD, limitations="Maybe 77 and -0.882."))[0]
    assert numbers_match(parsed, SOURCES, PASSAGES) == (False, ["77"])


# ── 4 dose and threshold ─────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", ["Take 10 mg with food.", "It is taken twice daily.", "A dose of one tablet is usual.", "Use it when eGFR is below the cut-off 30.",
                                  "This applies at 45 mL/min.", "It is contraindicated if the kidneys are weak.", "Do not use if kidney function is low.",
                                  "Stop it if HbA1c is under the target.", "The dosing can be adjusted."])
def test_check_4_dose_and_threshold_text_falls_back(text):
    g = run(draft(GOOD, limitations=text))
    assert g.status == "FALLBACK" and "dose_threshold" in failed(g)


def test_check_4_dose_text_inside_a_claim_that_is_supported_falls_back():
    passages = [{**PASSAGES[0], "text": "Take 10 mg of the medicine once daily as the label says."}, PASSAGES[1]]
    g = run(draft(("Take 10 mg of the medicine once daily as the label says.", ["S20-00-00"])), passages=passages, sources=("{}", "10"))
    assert g.status == "FALLBACK" and "dose_threshold" in failed(g)


@pytest.mark.parametrize("text", ["Dose-dependent effects are described.", "The kidneys filter the blood.", "The age of the patient is listed.", "A threshold exists for each rule."])
def test_check_4_wording_that_is_not_a_dose_or_a_threshold_passes(text):
    assert "dose_threshold" not in failed(run(draft(GOOD, limitations=text)))


# ── 5 an excluded option described positively ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", ["SGLT2 inhibitors are a good choice for this patient.", "Dapagliflozin is recommended here.", "A gliflozin is safe and effective.",
                                  "The SGLT2i is the best option.", "sodium-glucose cotransporter 2 inhibitors are suitable."])
def test_check_5_praise_for_an_excluded_option_falls_back(text):
    g = run(draft(GOOD, limitations=text), removed=["SGLT2i"])
    assert g.status == "FALLBACK" and "excluded_option" in failed(g) and g.fallback_reason in ("GUARD_EXCLUDED_OPTION",)


def test_check_5_praise_in_the_question_context_or_a_claim_is_caught_too():
    assert "excluded_option" in failed(run(draft(GOOD, context="Dapagliflozin is recommended for this patient."), removed=["SGLT2i"]))
    passages = [{**PASSAGES[0], "text": "SGLT2 inhibitors are a good choice for most adults with kidney disease."}, PASSAGES[1]]
    g = run(draft(("SGLT2 inhibitors are a good choice for most adults with kidney disease.", ["S20-00-00"])), removed=["SGLT2i"], passages=passages)
    assert g.status == "FALLBACK" and "excluded_option" in failed(g)


@pytest.mark.parametrize("text", ["SGLT2 inhibitors were removed by rule R01 and are not suitable.", "Dapagliflozin was excluded for this patient.",
                                  "Avoid SGLT2 inhibitors here, they are not recommended.", "DPP-4 inhibitors are a good choice."])
def test_check_5_naming_it_to_say_why_it_was_removed_is_fine_and_praising_an_eligible_option_is_not_this_checks_business(text):
    assert "excluded_option" not in failed(run(draft(GOOD, limitations=text), removed=["SGLT2i"]))


def test_check_5_with_nothing_excluded_nothing_is_checked():
    assert "excluded_option" not in failed(run(draft(GOOD, limitations="SGLT2 inhibitors are a good choice.")))


# ── 6 effect wording for an option marked insufficient ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", ["DPP-4 inhibitors lower HbA1c more than the others.", "Sitagliptin reduces HbA1c by a clear margin.", "A gliptin has a better effect on weight.",
                                  "The DPP4i is superior for this patient."])
def test_check_6_effect_wording_for_an_abstained_option_falls_back(text):
    g = run(draft(GOOD, limitations=text), status={"DPP4i": "insufficient_evidence"})
    assert g.status == "FALLBACK" and "insufficient_wording" in failed(g) and g.fallback_reason == "GUARD_INSUFFICIENT_WORDING"


@pytest.mark.parametrize("text", ["No estimate can be stated for DPP-4 inhibitors; the evidence is insufficient.", "The effect of sitagliptin cannot be judged here.",
                                  "SGLT2 inhibitors lower HbA1c in this patient."])
def test_check_6_saying_that_nothing_can_be_stated_and_describing_other_options_is_fine(text):
    assert "insufficient_wording" not in failed(run(draft(GOOD, limitations=text), status={"DPP4i": "insufficient_evidence"}))


def test_check_6_when_the_option_is_estimated_the_same_words_are_fine():
    assert "insufficient_wording" not in failed(run(draft(GOOD, limitations="DPP-4 inhibitors lower HbA1c.")))


# ── 7 identifiers (BLOCK) and causal wording about a driver ──────────────────────────────────────────────────────
@pytest.mark.parametrize("text", ["Patient Aadhaar 726018159082 was checked.", "Contact someone@example.com for more.", "Phone 9876543210 for the clinic.",
                                  "Mrs Kapoor should come back."])
def test_check_7_an_identifier_blocks_the_draft(text):
    g = run(draft(GOOD, limitations=text))
    assert g.status == "BLOCK" and "identifier_causal" in failed(g) and g.draft is None and g.fallback_reason == "GUARD_IDENTIFIER_CAUSAL"


def test_check_7_the_block_record_never_holds_the_identifier():
    g = run(draft(GOOD, limitations="Patient Aadhaar 726018159082 was checked."))
    assert "726018159082" not in g.model_dump_json()


@pytest.mark.parametrize("text", ["A higher BMI causes the larger effect.", "The estimate is smaller because of eGFR.", "Age leads to a bigger HbA1c fall.",
                                  "The effect is driven by HbA1c at the start.", "Kidney function is responsible for the difference."])
def test_check_7_causal_wording_about_a_driver_falls_back(text):
    g = run(draft(GOOD, limitations=text))
    assert g.status == "FALLBACK" and "identifier_causal" in failed(g) and g.fallback_reason == "GUARD_IDENTIFIER_CAUSAL"


def test_check_7_a_feature_of_the_drivers_list_counts_as_a_driver():
    assert "identifier_causal" not in failed(run(draft(GOOD, limitations="Duration of diabetes causes the difference.")))
    assert "identifier_causal" in failed(run(draft(GOOD, limitations="Duration of diabetes causes the difference."), features=["duration_years"]))


@pytest.mark.parametrize("text", [
    "The question is whether SGLT2 inhibitors can cause ketoacidosis in a 52-year-old male with type 2 diabetes and an HbA1c of 8.4%.",
    "Before starting the medicine, kidney function and other risk factors for acute kidney injury should be assessed due to its association with this risk.",
    "The question is whether a drug can cause acute kidney injury in a woman with HbA1c 8.2%, eGFR 40, and BMI 25.5.",
    "The estimate is larger for patients with a higher BMI.", "The estimate is smaller for patients with lower eGFR.",
                                  "SGLT2 inhibitors can cause ketoacidosis.", "Older age is listed as a feature of this patient."])
def test_check_7_a_cue_far_from_any_driver_and_the_phrasing_the_xai_rule_asks_for_pass(text):
    assert "identifier_causal" not in failed(run(draft(GOOD, limitations=text)))


def test_check_7_the_cue_and_the_driver_must_be_close_in_either_order():
    assert "identifier_causal" in failed(run(draft(GOOD, limitations="Because of age the estimate changes.")))
    assert "identifier_causal" in failed(run(draft(GOOD, limitations="The estimate changes, and eGFR is the reason for it, it is driven by it.")))
    assert "identifier_causal" not in failed(run(draft(GOOD, limitations="Age is listed first and, after a long list of other features that are shown, there may be something that causes trouble.")))


# ── the checks do not depend on the model's wording of anything else ────────────────────────────────────────────
def test_a_failing_check_is_the_only_thing_that_changes_the_status():
    for check, text in [("numbers", "Maybe 77."), ("dose_threshold", "Take it twice daily.")]:
        assert failed(run(draft(GOOD, limitations=text))) == [check]
        assert failed(run(draft(GOOD, limitations="A neutral sentence."))) == []


def test_eligible_helper_builds_the_rule_hits():
    assert [h.option for h in eligible("SGLT2i", "SU").excluded] == ["SGLT2i", "SU"]
