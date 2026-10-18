"""Step (i): the FastAPI endpoint POST /api/v1/recommend."""

import logging

import pytest
from conftest import EGFR40_PANCREATITIS, TYPICAL
from fastapi.testclient import TestClient

from diacausal import INTENDED_USE
from diacausal.api.main import create_app
from diacausal.causal_inference.recommend import DOSE_PATTERN


@pytest.fixture(scope="module")
def client(engine, tmp_path_factory):
    import diacausal.causal_inference.recommend as rec

    rec.AUDIT_PATH = tmp_path_factory.mktemp("api") / "audit.jsonl"
    with TestClient(create_app(engine)) as c:
        yield c


def body(**patient):
    return {"schema_version": "1.0", "patient": patient}


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["intended_use"] == INTENDED_USE


def test_recommend_returns_the_structured_causal_output(client):
    r = client.post("/api/v1/recommend", json=body(**TYPICAL))
    assert r.status_code == 200
    out = r.json()
    assert out["intended_use"] == INTENDED_USE
    assert out["applicable"] == "APPLICABLE"
    assert r.headers["X-Request-Id"] == out["request_id"]
    for o in out["options"]:
        assert o["status"] == "estimate"
        assert o["effect"]["ci_low"] < o["effect"]["value"] < o["effect"]["ci_high"]
    assert out["versions"]["rules_sha"] and out["versions"]["params_sha"]
    assert not DOSE_PATTERN.search(r.text)


def test_exclusions_come_with_their_sources(client):
    out = client.post("/api/v1/recommend", json=body(**EGFR40_PANCREATITIS)).json()
    sglt2 = next(o for o in out["options"] if o["arm"] == "SGLT2i")
    assert sglt2["status"] == "excluded" and sglt2["effect"] is None
    assert sglt2["safety"][0]["source"] and sglt2["safety"][0]["section"]


@pytest.mark.parametrize(
    "payload,field",
    [
        (body(**TYPICAL, favourite_colour="blue"), "patient.favourite_colour"),
        (body(**{k: v for k, v in TYPICAL.items() if k != "egfr"}), "patient.egfr"),
        (body(**TYPICAL | {"hba1c": 45}), "patient.hba1c"),
        (body(**TYPICAL | {"age": 12}), "patient.age"),
        ({"schema_version": "2.0", "patient": TYPICAL}, "schema_version"),
        ({"patient": TYPICAL}, "schema_version"),
    ],
)
def test_bad_requests_get_422_in_plain_english_with_intended_use(client, payload, field):
    r = client.post("/api/v1/recommend", json=payload)
    assert r.status_code == 422
    out = r.json()
    assert out["intended_use"] == INTENDED_USE
    assert any(p["field"] == field for p in out["problems"]), out
    assert out["message"].startswith("The request was not accepted")


def test_rejected_values_are_not_echoed(client):
    r = client.post("/api/v1/recommend", json=body(**TYPICAL | {"hba1c": 45.678}))
    assert "45.678" not in r.text


def test_unknown_route_still_carries_intended_use(client):
    r = client.get("/api/v1/nothing-here")
    assert r.status_code == 404 and r.json()["intended_use"] == INTENDED_USE


def test_logs_carry_ids_and_statuses_but_no_patient_values(client, caplog):
    with caplog.at_level(logging.INFO, logger="diacausal.engine"):
        client.post("/api/v1/recommend", json=body(**EGFR40_PANCREATITIS))
    text = caplog.text
    assert "SGLT2i=excluded(R01)" in text
    for value in ("25.5", "8.2", "egfr=40", "pancreatitis_history"):
        assert value not in text


def test_openapi_docs_show_intended_use(client):
    assert INTENDED_USE in client.get("/openapi.json").json()["info"]["description"]


def test_an_unexpected_crash_still_answers_in_json_with_the_intended_use_and_never_the_error_text(engine, monkeypatch, caplog):
    """Audit of 17 Oct 2026: a crash used to give plain text 'Internal Server Error' with no intended-use statement."""
    def boom(*a, **k):
        raise RuntimeError("secret detail 9.87 zebra-test")

    monkeypatch.setattr(engine, "recommend", boom)
    with TestClient(create_app(engine), raise_server_exceptions=False) as c:
        caplog.set_level(logging.DEBUG)
        r = c.post("/api/v1/recommend", json=body(**TYPICAL))
    assert r.status_code == 500 and r.headers["content-type"].startswith("application/json")
    assert r.json()["intended_use"] == INTENDED_USE and r.json()["error"] == "internal"
    assert "9.87" not in r.text and "zebra" not in r.text and "secret detail" not in r.text
    logged = " ".join(f"{x.getMessage()} {x.exc_text}" for x in caplog.records)
    assert "RuntimeError" in logged and "9.87" not in logged and "zebra" not in logged  # only the class name is logged
