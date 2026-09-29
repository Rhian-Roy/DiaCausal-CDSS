"""The causal engine, the evidence search (RAG) and the explanation, running inside the chat app."""

import re

from app.pipeline import output_guard
from app.pipeline.context import PipelineContext
from app.schemas import EvidencePart, Passage, Sentence, StageStatus, TextPart
from tests.conftest import PATIENT

FULL = {**PATIENT, "sex": "male"}
# Demo patient 2 of the website: eGFR 40 and past pancreatitis.
KIDNEY = {**PATIENT, "sex": "female", "age_years": 60, "diabetes_duration_years": 8, "hba1c_percent": 8.2,
          "egfr_ml_min_1_73m2": 40, "bmi_kg_m2": 25.5, "past_pancreatitis": True}
DOSE = re.compile(r"\b\d+(\.\d+)?\s*(mg|mcg|microgram|milligram)s?\b|\b(once|twice)\s+(a\s+)?daily\b", re.I)


def ask(client, chat_body, text="What should I add to metformin?", patient=FULL):
    return client.post("/api/v1/chat", json=chat_body(text, parts=[{"type": "text", "text": text}, patient])).json()


def part(data, kind):
    return next((p for p in data["parts"] if p["type"] == kind), None)


def test_all_six_stages_run_for_a_complete_patient(client, chat_body):
    data = ask(client, chat_body)
    assert data["outcome"] == "answered"
    assert [s["status"] for s in data["stages"]] == ["passed"] * 6


def test_every_estimate_has_a_95_percent_range(client, chat_body):
    estimates = part(ask(client, chat_body), "estimates")
    assert estimates is not None and len(estimates["estimates"]) == 3
    shown = [e for e in estimates["estimates"] if e["status"] == "estimate"]
    assert shown, "a typical patient gets at least one estimate"
    for e in shown:
        r = e["hba1c_change"]
        assert r["ci_low"] <= r["value"] <= r["ci_high"]
        assert e["propensity"] >= 0.05  # below 0.05 it must say insufficient evidence instead
    for e in estimates["estimates"]:
        if e["status"] != "estimate":
            assert e["hba1c_change"] is None and e["reason"]
    assert "synthetic" in estimates["data_note"] and "clinician decides" in estimates["decision"]


def test_an_option_removed_by_the_guardrails_never_gets_a_number(client, chat_body):
    data = ask(client, chat_body, patient=KIDNEY)
    options = {o["option"]: o["status"] for o in part(data, "options")["options"]}
    estimates = {e["option"]: e for e in part(data, "estimates")["estimates"]}
    for option, status in options.items():
        if status == "do_not_use":
            assert estimates[option]["status"] == "excluded" and estimates[option]["hba1c_change"] is None
    # the engine's own rule (R01: eGFR below 45) excludes the SGLT2 inhibitor as well
    assert estimates["sglt2i"]["status"] == "excluded" and estimates["sglt2i"]["hba1c_change"] is None


def test_missing_patient_details_are_named_not_guessed(client, chat_body):
    data = ask(client, chat_body, patient={k: v for k, v in FULL.items() if k != "hba1c_percent"})
    stage = data["stages"][2]
    assert stage["name"] == "causal_engine" and stage["status"] == "skipped"
    assert stage["detail"] == "Needs HbA1c in the patient panel."
    assert part(data, "estimates") is None


def test_the_evidence_is_quoted_and_cited(client, chat_body):
    data = ask(client, chat_body, "Is ketoacidosis a risk with SGLT2 inhibitors?")
    evidence = part(data, "evidence")
    assert evidence["status"] == "answered" and evidence["backend"] == "template"
    numbers = {p["n"] for p in evidence["passages"]}
    assert evidence["sentences"]
    for sentence in evidence["sentences"]:
        assert set(sentence["cites"]) <= numbers
        cited = next(p for p in evidence["passages"] if p["n"] == sentence["cites"][0])
        assert sentence["text"] in cited["text"]  # quoted exactly from the passage it cites
    assert any("ketoacidosis" in s["text"].lower() for s in evidence["sentences"])
    assert "[1]" in part(data, "text")["text"] or "[2]" in part(data, "text")["text"]


def test_a_question_outside_the_sources_says_insufficient_evidence(client, chat_body):
    data = ask(client, chat_body, "How much does glimepiride cost in India?")
    evidence = part(data, "evidence")
    assert evidence["status"] == "insufficient_evidence" and evidence["sentences"] == []
    assert "Insufficient evidence" in part(data, "text")["text"]


def test_a_dose_question_never_gets_a_dose(client, chat_body):
    data = ask(client, chat_body, "What dose of glimepiride should I start with?")
    assert data["outcome"] == "answered"
    evidence = part(data, "evidence")
    assert evidence["sentences"] == []
    everything = str(data["parts"])
    assert not DOSE.search(everything)


def test_output_guard_withholds_any_dose_in_the_evidence():
    ctx = PipelineContext(trace_id="t", parts=[TextPart(type="text", text="hi")])
    ctx.reply_parts = [
        EvidencePart(type="evidence", status="answered", backend="gemini",
                     sentences=[Sentence(text="Start with 10 mg once daily.", cites=[1])],
                     passages=[Passage(n=1, source_id="S01", title="t", section="s", text="x")]),
        TextPart(type="text", text="An answer."),
    ]
    result = output_guard.run(ctx)
    assert result.status is StageStatus.BLOCKED and "dose" in result.detail


def test_no_patient_value_or_question_reaches_the_log(client, chat_body, caplog):
    ask(client, chat_body, "Is ketoacidosis a risk with SGLT2 inhibitors?", patient=KIDNEY)
    log = "\n".join(r.getMessage() for r in caplog.records)
    assert "ketoacidosis" not in log
    for value in ("8.2", "25.5", "female"):
        assert value not in log
