"""The compact causal output and the number sources of the section 8.9 prompt (the number check itself: tests/guards/test_output_guards.py)."""

from diacausal.llm import prompt_builder as pb


# ── the prompt ───────────────────────────────────────────────────────────────────────────────────────────────────
def causal_stub():
    from diacausal.causal_inference.recommend import get_engine
    from diacausal.causal_inference.schemas import PatientIn

    return get_engine().recommend(PatientIn(age=60, sex="female", duration_years=8.0, hba1c=8.2, egfr=40.0, bmi=25.5, pancreatitis_history=True), audit=False)


def test_the_compact_causal_output_has_the_numbers_with_intervals_and_nothing_for_an_excluded_option():
    c = pb.compact_causal(causal_stub())
    by = {o["option"]: o for o in c["options"]}
    assert by["SGLT2i"] == {"option": "SGLT2i", "status": "excluded"}  # R01 removed it: no number, nothing to quote
    assert set(by["SU"]["hba1c_change_6m"]) == {"value", "ci95"} and len(by["SU"]["hba1c_change_6m"]["ci95"]) == 2
    assert c["applicable"] == "APPLICABLE" and "assumptions" not in c


def test_the_number_sources_are_the_causal_output_and_the_drivers_as_shown_to_the_model():
    assert pb.number_sources({"a": 1}, {"b": 2}) == ['{"a":1}', '{"b":2}']
