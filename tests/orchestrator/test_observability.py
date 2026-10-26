"""Observability (diacausal/observability/, GET /api/v1/observability/...; docs/OBSERVABILITY.md).

What is checked: every layer, part and engine step that really runs is in the trace, in order, with its parent; a stopped, abstaining
or failing request is recorded as what it was; concurrent requests never mix; the card and the engine's output are identical with and
without recording; nothing a patient or a question contains reaches the store or the API; only this computer can read the traces;
retention, filters and the off switch work; a trace that cannot be written never touches the clinician's reply."""

import json
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pipeline_helpers import PRESETS, body

from diacausal import registry
from diacausal.api.main import create_app
from diacausal.observability import recorder, store as store_module
from diacausal.observability.store import TraceStore
from diacausal.orchestrator import layers

LOCAL = ("127.0.0.1", 50000)
ENGINE_STEPS = ["safety rules", "cohort support check", "propensity overlap", "DR-learner estimate", "interval width check",
                "secondary outcomes", "engine output check"]
LAYER_NAMES = [e.name for e in registry.LAYERS]
EMERGENCY = "Patient unconscious in OPD, which add-on?"


@pytest.fixture()
def traces(tmp_path):
    s = TraceStore(tmp_path / "traces.sqlite3")
    yield s
    s.close()


@pytest.fixture()
def local(engine, audit_file, traces):
    with TestClient(create_app(engine, trace_store=traces), client=LOCAL) as c:
        yield c


def ask(c, preset="typical", question=None, rid="o1", **changes):
    patient, q = PRESETS[preset]
    return c.post("/api/v1/ask", json=body({**patient, **changes}, question or q, rid))


def stored(c, r) -> dict:
    return c.get(f"/api/v1/observability/traces/{r.headers['x-trace-id']}").json()["trace"]


def layer_spans(t):
    return [s for s in t["spans"] if s["kind"] == "layer"]


def children(t, name):
    parent = next(s["span_id"] for s in t["spans"] if s["kind"] == "layer" and s["name"] == name)
    return [s for s in t["spans"] if s["parent_id"] == parent]


def test_every_layer_part_and_engine_step_that_runs_is_in_the_trace_in_order(local):
    r = ask(local)
    assert r.status_code == 200 and r.headers["x-request-id"] == "o1"
    t = stored(local, r)
    assert t["request_id"] == "o1" and t["status"] == "completed" and t["http_status"] == 200 and t["workflow"] == "ask"
    assert [s["name"] for s in layer_spans(t)] == LAYER_NAMES
    assert all(s["status"] == "completed" and s["duration_ms"] is not None and s["parent_id"] is None for s in layer_spans(t))
    assert [s["component"] for s in layer_spans(t)] == [e.function for e in registry.LAYERS]
    causal = children(t, "causal engine")
    assert [s["name"] for s in causal] == [*ENGINE_STEPS, "shap drivers"]  # the engine's steps, then the drivers part
    assert [s["name"] for s in children(t, "retrieval")] == ["query processing"]
    assert [s["name"] for s in children(t, "explanation")] == ["prompt builder"]
    assert [s["name"] for s in children(t, "output guards")] == ["full output checks"]
    assert [s["name"] for s in children(t, "formatter")] == ["evidence levels"]
    starts = [s["start_ms"] for s in t["spans"]]
    assert starts == sorted(starts), "spans are listed in the order they started"
    assert {s["pipeline"] for s in t["spans"]} == {"guards", "ci", "rag", "llm", "output"}
    # what the spans say matches what the card says
    card = r.json()
    rules = next(s for s in layer_spans(t) if s["name"] == "rules")["summary"]
    assert rules["eligible"] == [o for o in ("SGLT2i", "DPP4i", "SU") if o not in {x["option"] for x in card["excluded"]}]
    fmt = next(s for s in layer_spans(t) if s["name"] == "formatter")["summary"]
    assert fmt["evidence_levels"] == [{"option": lv["option"], "level": lv["level"]} for lv in card["evidence_levels"]]
    assert fmt["claims"] == len(card["claims"]) and t["context"]["versions"] == card["versions"]
    retrieval = next(s for s in layer_spans(t) if s["name"] == "retrieval")["summary"]
    assert retrieval["status"] == "SUCCESS" and retrieval["passages"]
    cited = {c["chunk_id"] for claim in card["claims"] for c in claim["citations"]}
    assert cited <= {p["chunk_id"] for p in retrieval["passages"]}, "every passage the card cites is one the retrieval span lists"


def test_the_card_and_the_engine_output_are_identical_with_and_without_recording(engine, audit_file, traces, monkeypatch):
    def cards():
        with TestClient(create_app(engine, trace_store=traces), client=LOCAL) as c:
            return [ask(c, preset, rid=f"same{i}").json() for i, preset in enumerate(PRESETS)]

    on = cards()
    monkeypatch.setenv("DIACAUSAL_OBSERVABILITY", "off")
    off = cards()
    assert on == off
    # the engine itself, inside and outside a running trace
    from diacausal.api.schemas.patient import to_engine_patient
    from diacausal.api.schemas import AskRequestV1

    monkeypatch.delenv("DIACAUSAL_OBSERVABILITY")
    patient = to_engine_patient(AskRequestV1.model_validate(body(*PRESETS["egfr40_pancreatitis"])).patient)
    plain = engine.recommend(patient, audit=False).model_dump(exclude={"request_id"})
    t = recorder.start("test", "inside")
    try:
        traced = engine.recommend(patient, audit=False).model_dump(exclude={"request_id"})
    finally:
        recorder.finish(t, http_status=200)
    assert plain == traced and [s.name for s in t.spans] == ENGINE_STEPS


def test_a_stopped_request_lists_the_layers_it_never_reached(local):
    r = ask(local, question=EMERGENCY, rid="o2")
    assert r.status_code == 422
    t = stored(local, r)
    assert t["status"] == "blocked" and t["code"] == "RED_FLAG" and t["http_status"] == 422
    first, *rest = layer_spans(t)
    assert first["name"] == "input guards" and first["status"] == "abstained" and first["code"] == "RED_FLAG" and first["error_type"] is None
    assert {"check": "red_flag", "result": "BLOCK"} in first["summary"]["checks"]
    assert [s["name"] for s in rest] == LAYER_NAMES[1:]
    assert all(s["status"] == "not run" and s["duration_ms"] is None for s in rest)
    assert t["ci_status"] == t["rag_status"] == "not run"


def test_an_abstaining_layer_makes_the_request_partial(local):
    r = ask(local, question="zebra-test", rid="o3")
    assert r.status_code == 200
    t = stored(local, r)
    retrieval = next(s for s in layer_spans(t) if s["name"] == "retrieval")
    assert retrieval["status"] == "abstained" and retrieval["code"] == "NO_EVIDENCE"
    assert retrieval["summary"]["status"] == "INSUFFICIENT_EVIDENCE" and retrieval["summary"]["reason"] in ("NO_MATCH", "LOW_COVERAGE")
    assert t["status"] == "partial" and t["rag_status"] == "abstained" and t["n_warnings"] >= 1


def test_a_failing_layer_is_recorded_by_class_and_the_rest_as_not_run(local, monkeypatch):
    def broken(ctx):
        raise ValueError(f"cannot search {ctx.request.question!r}")

    monkeypatch.setattr(layers, "retrieval_layer", broken)
    r = ask(local, rid="o4")
    assert r.status_code == 500
    t = stored(local, r)
    assert t["status"] == "failed" and t["failed_stage"] == "retrieval" and t["error_type"] == "ValueError" and t["n_errors"] == 1
    by_name = {s["name"]: s for s in layer_spans(t)}
    assert by_name["retrieval"]["status"] == "failed" and by_name["causal engine"]["status"] == "completed"
    assert [by_name[n]["status"] for n in LAYER_NAMES[4:]] == ["not run"] * 3
    assert "cannot search" not in json.dumps(t)  # the class, never the message
    summary = local.get("/api/v1/observability/summary").json()["stored"]
    assert summary["failures"]["rag"] == 1 and summary["recent_problems"][0]["trace_id"] == t["trace_id"]


def test_concurrent_requests_keep_separate_traces(local):
    ids = [f"par{i}" for i in range(6)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        replies = list(pool.map(lambda rid: ask(local, preset=list(PRESETS)[int(rid[-1]) % 3], rid=rid), ids))
    assert all(r.status_code == 200 for r in replies)
    seen = set()
    for rid, r in zip(ids, replies):
        t = stored(local, r)
        assert t["request_id"] == rid and t["trace_id"] not in seen
        seen.add(t["trace_id"])
        assert [s["name"] for s in layer_spans(t)] == LAYER_NAMES
        assert [s["name"] for s in children(t, "causal engine")] == [*ENGINE_STEPS, "shap drivers"]
        assert len({s["span_id"] for s in t["spans"]}) == len(t["spans"])
    assert local.get("/api/v1/observability/traces", params={"q": "par"}).json()["total"] == 6


def test_nothing_a_patient_or_question_contains_reaches_the_store_or_the_api(local, traces):
    secrets = ("9.87", "zebra", "quokka")
    for rid, question in (("p1", "zebra-test"), ("p2", "Can SGLT2 inhibitors cause ketoacidosis in a quokka?"), ("p3", EMERGENCY + " zebra")):
        ask(local, rid=rid, question=question, hba1c_pct=9.87)
    raw = traces.path.read_bytes().decode("latin-1")
    with sqlite3.connect(traces.path) as db:
        docs = " ".join(row[0] for row in db.execute("SELECT doc FROM traces"))
    api = " ".join(local.get(path).text for path in ("/api/v1/observability/summary", "/api/v1/observability/traces",
                                                      "/api/v1/observability/engine"))
    api += " ".join(local.get(f"/api/v1/observability/traces/{t['trace_id']}").text
                    for t in local.get("/api/v1/observability/traces").json()["traces"])
    assert docs.count('"request_id"') == 3
    for secret in secrets:
        assert secret not in raw and secret not in docs and secret not in api.lower(), secret
    assert "unconscious" not in docs.lower() and "ketoacidosis" not in docs.lower()


@pytest.mark.parametrize("host", ["testclient", "10.0.0.7", "192.168.1.20"])
def test_only_this_computer_can_read_the_traces(engine, audit_file, traces, host):
    with TestClient(create_app(engine, trace_store=traces), client=(host, 50000)) as c:
        r = ask(c, rid="far1")
        assert r.status_code == 200  # the answer itself is unaffected
        for path in ("summary", "traces", "engine", f"traces/{r.headers['x-trace-id']}"):
            reply = c.get(f"/api/v1/observability/{path}")
            assert reply.status_code == 403 and "far1" not in reply.text and reply.json()["intended_use"]


def test_bad_ids_and_filters_are_refused_without_echo(local):
    r = ask(local, rid="o5")
    assert local.get("/api/v1/observability/traces/" + r.headers["x-trace-id"]).status_code == 200
    for bad in ("ABCDEF0123456789", "123", "1b99ecfc577c472e0", "zz99ecfc577c472e"):
        assert local.get(f"/api/v1/observability/traces/{bad}").status_code == 422
    assert local.get("/api/v1/observability/traces/0000000000000000").status_code == 404
    for params in ({"q": "x%"}, {"q": "a' OR '1'='1"}, {"status": "bogus"}, {"limit": 0}, {"limit": 500}, {"sort": "name"},
                   {"pipeline": "dna"}):
        reply = local.get("/api/v1/observability/traces", params=params)
        assert reply.status_code == 422, params
        assert "OR '1'" not in reply.text


def test_filters_sorting_and_pages(local):
    ask(local, rid="f-ok")
    ask(local, rid="f-stop", question=EMERGENCY)
    ask(local, rid="f-thin", question="zebra-test")
    get = lambda **p: local.get("/api/v1/observability/traces", params=p).json()  # noqa: E731
    assert get()["total"] == 3
    assert [t["request_id"] for t in get(status="blocked")["traces"]] == ["f-stop"]
    assert {t["request_id"] for t in get(problems=True)["traces"]} == {"f-stop", "f-thin"}
    assert [t["request_id"] for t in get(pipeline="rag", pipeline_status="abstained")["traces"]] == ["f-thin"]
    assert {t["request_id"] for t in get(pipeline="ci")["traces"]} == {"f-ok", "f-thin"}  # the blocked one never reached it
    newest = get()["traces"]
    assert [t["request_id"] for t in newest] == ["f-thin", "f-stop", "f-ok"]
    by_time = get(sort="duration", order="asc")["traces"]
    assert [t["duration_ms"] for t in by_time] == sorted(t["duration_ms"] for t in by_time)
    page = get(limit=1, offset=1)
    assert page["total"] == 3 and [t["request_id"] for t in page["traces"]] == ["f-stop"]
    assert "spans" not in newest[0], "the list never carries the spans"
    since = newest[1]["started_at"]
    assert {t["request_id"] for t in get(since=since)["traces"]} == {"f-thin", "f-stop"}


def test_the_summary_counts_what_is_stored(local):
    empty = local.get("/api/v1/observability/summary").json()
    assert empty["stored"]["total"] == 0 and empty["stored"]["answered_share"] is None and empty["stored"]["duration_ms"]["mean"] is None
    ask(local, rid="s1")
    ask(local, rid="s2", question=EMERGENCY)
    s = local.get("/api/v1/observability/summary").json()["stored"]
    assert s["total"] == 2 and s["by_status"]["completed"] == 1 and s["by_status"]["blocked"] == 1 and s["answered_share"] == 0.5
    assert s["duration_ms"]["n"] == 2 and s["duration_ms"]["mean"] > 0
    assert [p["request_id"] for p in s["recent_problems"]] == ["s2"]


def test_retention_keeps_the_newest_and_drops_the_old(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "KEEP_TRACES", 3)
    s = TraceStore(tmp_path / "r.sqlite3")
    import time

    now = time.time()
    for i in range(5):
        s.save({"trace_id": f"{i:016x}", "request_id": f"r{i}", "source": "server", "workflow": "ask", "started_at": now - 10 + i,
                "status": "completed", "spans": []})
    s.save({"trace_id": "f" * 16, "request_id": "ancient", "source": "server", "workflow": "ask", "started_at": now - 40 * 86400,
            "status": "completed", "spans": []})
    total, rows = s.query()
    assert total == 3 and [r["request_id"] for r in rows] == ["r4", "r3", "r2"]
    s.close()


def test_switched_off_records_and_serves_nothing(engine, audit_file, traces, monkeypatch):
    monkeypatch.setenv("DIACAUSAL_OBSERVABILITY", "off")
    with TestClient(create_app(engine, trace_store=traces), client=LOCAL) as c:
        r = ask(c, rid="off1")
        assert r.status_code == 200 and "x-trace-id" not in r.headers
        assert c.get("/api/v1/observability/traces").status_code == 404
    assert traces.query()[0] == 0


def test_a_trace_that_cannot_be_written_never_touches_the_reply(engine, audit_file, traces, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    with TestClient(create_app(engine, trace_store=traces), client=LOCAL) as c:
        good = ask(c, rid="w1").json()

        def full(_):
            raise sqlite3.OperationalError("database or disk is full: zebra")

        monkeypatch.setattr(traces, "save", full)
        r = ask(c, rid="w1")
        assert r.status_code == 200 and r.json() == good
    logged = " ".join(rec.getMessage() for rec in caplog.records)
    assert "[w1] observability: trace not stored error=OperationalError" in logged and "zebra" not in logged


def test_the_engine_facts_and_the_pipeline_come_from_the_running_code(local, engine):
    e = local.get("/api/v1/observability/engine").json()
    assert [x["name"] for x in e["layers"]] == LAYER_NAMES and [x["name"] for x in e["parts"]] == [p.name for p in registry.PARTS]
    assert [x["component"] for x in e["layers"]] == [x.function for x in registry.LAYERS]
    facts = e["engine"]
    assert facts["reference_cohort"]["n"] == engine.n and facts["reference_cohort"]["seed"] == engine.seed
    assert sum(facts["reference_cohort"]["patients_per_arm"].values()) == facts["reference_cohort"]["rows_used"]
    assert facts["settings"]["overlap_min_propensity"] == engine.threshold and facts["settings"]["max_interval_width"] == engine.max_width
    assert facts["variables"]["adjusted_for"] == list(engine.adjustment) and "weight_change_6m" in facts["variables"]["not_adjusted"]
    assert facts["fit_measured"] is False and facts["fit_ms"] is None  # this engine was fitted by the test, not timed by the server


def test_a_summary_keeps_only_short_labels_and_numbers():
    long = "x" * 200
    kept = recorder.safe({"a": 1.234567, "b": long, "c": "what about my patient? (age 57)", "d": [1, "ok", {"e": float("nan")}],
                          "bad key!": 1, "SGLT2i": True})
    assert kept == {"a": 1.2346, "b": recorder.REDACTED, "c": recorder.REDACTED, "d": [1, "ok", {"e": None}], "SGLT2i": True}


def test_a_running_request_is_listed_until_it_finishes(local):
    t = recorder.start("ask", "live1")
    try:
        running = local.get("/api/v1/observability/traces", params={"status": "running"}).json()["traces"]
        assert [x["request_id"] for x in running] == ["live1"] and running[0]["status"] == "running"
        assert local.get(f"/api/v1/observability/traces/{t.trace_id}").json()["trace"]["status"] == "running"
    finally:
        recorder.finish(t, http_status=200)
    assert local.get("/api/v1/observability/traces", params={"status": "running"}).json()["traces"] == []
