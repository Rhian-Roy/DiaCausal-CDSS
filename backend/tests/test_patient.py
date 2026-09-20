"""The structured patient part: ranges, limits, what reaches the stages, what is logged."""

import json
import logging

import pytest

from app.patient_ranges import RANGES, bmi_category
from app.schemas import PatientPart

FULL = {
    "type": "patient",
    "age_years": 58,
    "diabetes_duration_years": 6,
    "hba1c_percent": 8.4,
    "egfr_ml_min_1_73m2": 62,
    "bmi_kg_m2": 31.2,
    "established_ascvd": True,
    "ckd": False,
    "heart_failure": False,
    "past_dka": False,
    "recurrent_genital_or_urinary_infection": False,
    "past_pancreatitis": False,
    "past_hypoglycaemia": "none",
    "budget_inr_per_month": 1500,
}


def send(client, chat_body, patient: dict, text: str = "What should I add?"):
    body = chat_body(text)
    body["parts"] = [patient, {"type": "text", "text": text}]
    return client.post("/api/v1/chat", json=body)


def test_a_filled_panel_is_accepted(client, chat_body):
    reply = send(client, chat_body, FULL)
    assert reply.status_code == 200 and reply.json()["outcome"] == "answered"


def test_an_empty_panel_is_accepted(client, chat_body):
    assert send(client, chat_body, {"type": "patient"}).status_code == 200


@pytest.mark.parametrize("field", sorted(RANGES))
def test_both_ends_of_every_range(client, chat_body, field):
    low, high, *_ = RANGES[field]
    for inside in (low, high):
        assert send(client, chat_body, {"type": "patient", field: inside}).status_code == 200, f"{field}={inside}"
    for outside in (low - 1, high + 1):
        reply = send(client, chat_body, {"type": "patient", field: outside})
        assert reply.status_code == 422, f"{field}={outside} should be refused"


def test_the_message_names_the_expected_range(client, chat_body):
    reply = send(client, chat_body, {"type": "patient", "hba1c_percent": 45})
    message = reply.json()["message"]
    assert message == "HbA1c 45% is outside the expected range 4.0–20.0 %. Check the value."


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("age_years", 4, "Age"),
        ("egfr_ml_min_1_73m2", 200, "eGFR"),
        ("bmi_kg_m2", 5, "BMI"),
        ("budget_inr_per_month", -1, "Budget"),
    ],
)
def test_every_out_of_range_message_names_the_field_and_the_range(client, chat_body, field, value, expected):
    message = send(client, chat_body, {"type": "patient", field: value}).json()["message"]
    low, high, unit, *_ = RANGES[field]
    assert message.startswith(expected) and unit in message and "outside the expected range" in message


def test_an_unknown_patient_field_is_refused(client, chat_body):
    reply = send(client, chat_body, {"type": "patient", "weight_kg": 70})
    assert reply.status_code == 422
    assert reply.json()["message"] == '"parts[0].weight_kg" is not a field this API accepts.'


def test_past_hypoglycaemia_has_three_settings(client, chat_body):
    for value in ("none", "mild", "severe"):
        assert send(client, chat_body, {"type": "patient", "past_hypoglycaemia": value}).status_code == 200
    assert send(client, chat_body, {"type": "patient", "past_hypoglycaemia": "a bit"}).status_code == 422


def test_two_patient_parts_are_refused(client, chat_body):
    body = chat_body()
    body["parts"] = [{"type": "patient"}, {"type": "patient"}, {"type": "text", "text": "hi"}]
    reply = client.post("/api/v1/chat", json=body)
    assert reply.status_code == 422
    assert reply.json()["message"] == "A message may carry at most one patient part."


def test_the_fields_the_guardrail_rules_need_are_all_there():
    """clinical/guardrails.v1.yaml refers to these; without them its rules cannot run."""
    for field in ("egfr_ml_min_1_73m2", "past_dka", "recurrent_genital_or_urinary_infection",
                  "past_pancreatitis", "heart_failure", "established_ascvd", "ckd"):
        assert field in PatientPart.model_fields


def test_the_stages_get_the_patient_details(client, chat_body, monkeypatch):
    from app.pipeline import clinical_guardrails
    from app.pipeline.context import passed

    seen = {}

    def remember(ctx):
        seen["patient"] = ctx.patient
        seen["text"] = ctx.text
        return passed(clinical_guardrails.NAME, "saw the panel")

    monkeypatch.setattr(clinical_guardrails, "run", remember)
    send(client, chat_body, FULL, "Which add-on?")

    assert seen["patient"].hba1c_percent == 8.4 and seen["patient"].established_ascvd is True
    assert seen["text"] == "Which add-on?"  # the panel is not part of the text the guards read


def test_patient_values_are_never_logged(client, chat_body, caplog):
    caplog.set_level(logging.INFO, logger="diacausal")
    send(client, chat_body, FULL)

    assert "8.4" not in caplog.text and "1500" not in caplog.text and "31.2" not in caplog.text
    # Only which fields were filled in.
    assert "patient details: age_years, diabetes_duration_years" in caplog.text


def test_an_empty_panel_logs_that_nothing_was_filled_in(client, chat_body, caplog):
    caplog.set_level(logging.INFO, logger="diacausal")
    send(client, chat_body, {"type": "patient"})
    assert "patient details: none filled in" in caplog.text


def test_patient_values_are_not_in_the_audit_log(client, chat_body, db):
    from sqlalchemy import select

    from app.db.models import AuditLog

    send(client, chat_body, FULL)
    rows = str([vars(row) for row in db.scalars(select(AuditLog)).all()])
    assert "8.4" not in rows and "1500" not in rows


def test_the_reply_does_not_echo_the_panel(client, chat_body):
    reply = send(client, chat_body, FULL).json()
    assert "8.4" not in json.dumps(reply["parts"])


@pytest.mark.parametrize(
    ("bmi", "category"),
    [(17, "Underweight"), (18.5, "Normal"), (22.9, "Normal"), (23, "Overweight"), (24.9, "Overweight"),
     (25, "Obese"), (31.2, "Obese")],
)
def test_bmi_uses_asian_indian_cut_offs(bmi, category):
    """Misra et al. JAPI 2009: 23 and 25, not the WHO 25 and 30."""
    assert bmi_category(bmi).startswith(category)


def test_ranges_are_plausibility_limits_not_clinical_thresholds():
    from app import patient_ranges

    assert "plausibility limits, not clinical thresholds" in patient_ranges.__doc__
