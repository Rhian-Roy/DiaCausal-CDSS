"""NEVER log patient values, question text, prompts, passages or secrets (plan 8.5, AGENTS.md invariant 7).

A distinctive fake patient (HbA1c 9.87) and the question "zebra-test" go through the whole pipeline; the test fails if
either appears in ANY captured log record (message, arguments, exception text) or in what the console printed, and
the same when a layer fails with an exception whose message contains them."""

import json
import logging

from pipeline_helpers import body

from diacausal.orchestrator import layers

SECRETS = ("9.87", "zebra-test", "zebra")
PATIENT = dict(age=47, sex="M", duration_years=3.0, hba1c_pct=9.87, egfr=77.0, bmi=29.3)


def everything_logged(caplog, capsys) -> str:
    out = capsys.readouterr()
    records = " ".join(
        f"{r.name} {r.getMessage()} {r.msg} {r.args} {r.exc_text} {r.exc_info}" for r in caplog.records)
    return records + out.out + out.err


def test_neither_the_distinctive_value_nor_the_question_reaches_any_log(client, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    r = client.post("/api/v1/ask", json=body(PATIENT, "zebra-test", "priv1"))
    assert r.status_code == 200
    assert "9.87" in r.text and "zebra-test" in r.text  # the reply to the clinician does carry them
    logged = everything_logged(caplog, capsys)
    assert "[priv1] entered input guards layer" in logged  # the trace really was captured
    for secret in SECRETS:
        assert secret not in logged, f"{secret!r} was logged"


def test_the_patient_numbers_are_not_in_the_audit_line_either(client, audit_file):
    client.post("/api/v1/ask", json=body(PATIENT, "zebra-test", "priv2"))
    text = audit_file.read_text()
    line = json.loads(text.splitlines()[-1])
    assert line["request_id"] == "priv2" and set(line) >= {"engine", "params_sha", "rules_sha", "options"}
    for secret in (*SECRETS, "77.0", "29.3"):
        assert secret not in text


def test_a_failing_layer_logs_the_class_and_the_reply_leaks_nothing(client, caplog, capsys, monkeypatch):
    caplog.set_level(logging.DEBUG)

    def broken(ctx):
        raise ValueError(f"cannot search {ctx.request.question!r} for hba1c {ctx.request.patient.hba1c_pct}")

    monkeypatch.setattr(layers, "retrieval_layer", broken)
    r = client.post("/api/v1/ask", json=body(PATIENT, "zebra-test", "priv3"))
    assert r.status_code == 500
    assert r.json()["request_id"] == "priv3" and r.json()["error"] == "internal"
    for secret in SECRETS:
        assert secret not in r.text
    logged = everything_logged(caplog, capsys)
    assert "[priv3] failed retrieval layer error=ValueError" in logged
    assert "[priv3] ask: failed error=ValueError" in logged
    for secret in SECRETS:
        assert secret not in logged, f"{secret!r} was logged"


def test_a_rejected_request_does_not_echo_or_log_what_was_sent(client, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    r = client.post("/api/v1/ask", json=body({**PATIENT, "hba1c_pct": 123.456}, "zebra-test", "priv4"))
    assert r.status_code == 422 and "123.456" not in r.text
    logged = everything_logged(caplog, capsys)
    assert "123.456" not in logged and "zebra" not in logged


def test_a_rule_order_violation_is_a_failure_not_a_number(client, monkeypatch):
    """If the engine ever returned an estimate for an option the rules removed, the request fails (invariant 2)."""
    from diacausal.causal_inference.schemas import Cost, Interval, OptionOut

    real = layers.write_audit

    def sneaky(result, patient, *a, **k):
        raise AssertionError("not reached")

    engine = client.app.state.engine
    original = engine.recommend

    def recommend(patient, audit=True, audit_path=None):
        result = original(patient, audit=False)
        bad = [o if o.arm != "SGLT2i" else OptionOut(
            arm="SGLT2i", name=o.name, example_molecule=o.example_molecule, status="estimate", safety=o.safety,
            effect=Interval(value=-1.0, ci_low=-1.2, ci_high=-0.8), cost=Cost(inr_per_month=None, label="price unavailable"))
            for o in result.options]
        return result.model_copy(update={"options": bad})

    monkeypatch.setattr(engine, "recommend", recommend)
    patient = dict(age=60, sex="F", duration_years=8.0, hba1c_pct=8.2, egfr=40.0, bmi=25.5)  # R01 removes the SGLT2i
    r = client.post("/api/v1/ask", json=body(patient, "Can SGLT2 inhibitors cause ketoacidosis?", "viol"))
    assert r.status_code == 500 and "estimate" not in r.text
