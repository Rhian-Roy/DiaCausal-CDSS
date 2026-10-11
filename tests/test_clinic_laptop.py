"""The clinic laptop (P29b; docs/OFFLINE_INSTALL.md): the start scripts listen on 127.0.0.1 only, the server serves the website with the
same security headers as Netlify, the page can tell which writer answers, every /ask reply carries its per-layer times, and the
measurement never writes a question or a patient value.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

import csv
import http.server
import importlib.util
import json
import re
import socket
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from diacausal import INTENDED_USE, registry
from diacausal.api.main import create_app, site_headers
from diacausal.llm.golden import PRESET_PATIENTS, load_golden, request_for
from diacausal.llm.providers import ollama

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _measure():
    spec = importlib.util.spec_from_file_location("measure_local", SCRIPTS / "measure_local.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── the start scripts ─────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", ["start_clinic.bat", "start_clinic.command"])
def test_the_start_scripts_listen_on_this_computer_only(name):
    text = (SCRIPTS / name).read_text(encoding="utf-8")
    assert "0.0.0.0" not in text and "--host 0" not in text
    starts = re.findall(r"-m uvicorn diacausal\.api\.main:app --host (\S+) --port (\d+)", text)
    assert starts == [("127.0.0.1", "8000")], starts
    assert "DIACAUSAL_LLM_PROVIDER=ollama" in text and "127.0.0.1:8000" in text and "11434" in text
    assert "Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use." in text


def test_the_windows_script_has_windows_line_endings_and_the_mac_one_can_run():
    assert b"\r\n" in (SCRIPTS / "start_clinic.bat").read_bytes()
    assert (SCRIPTS / "start_clinic.command").stat().st_mode & 0o111, "start_clinic.command must be executable (double-click in Finder)"


# ── the writer switch and its status ──────────────────────────────────────────────────────────────────────────────────────────
def test_the_team_default_is_the_template_and_only_the_environment_switches_on_ollama(monkeypatch):
    monkeypatch.delenv(ollama.PROVIDER_ENV, raising=False)
    assert ollama.load_llm_config()["provider"] == "template"
    monkeypatch.setenv(ollama.PROVIDER_ENV, "ollama")
    assert ollama.load_llm_config()["provider"] == "ollama"
    monkeypatch.setenv(ollama.PROVIDER_ENV, "something-else")
    assert ollama.load_llm_config()["provider"] == "template"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def fake_ollama():
    """A stand-in for a running Ollama: GET /api/tags lists the configured tag (no model, no internet)."""
    tag = ollama.model_tag(ollama.load_llm_config())

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"models": [{"name": tag, "model": tag}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", tag
    server.shutdown()


def test_status_says_ollama_only_when_it_runs_and_has_the_model(fake_ollama):
    url, tag = fake_ollama
    cfg = {**ollama.load_llm_config(), "provider": "ollama", "ollama_url": url}
    assert ollama.status(cfg) == {"provider": "ollama", "writer": "ollama", "model_tag": tag, "ollama_reachable": True, "model_pulled": True}
    other = {**cfg, "models": {**cfg["models"], cfg["model"]: {**cfg["models"][cfg["model"]], "tag": "not-pulled:1b"}}}
    assert ollama.status(other)["writer"] == "template" and ollama.status(other)["model_pulled"] is False
    down = {**cfg, "ollama_url": f"http://127.0.0.1:{_free_port()}"}
    assert ollama.status(down, timeout=0.5)["writer"] == "template" and ollama.status(down, timeout=0.5)["ollama_reachable"] is False
    off = {**cfg, "provider": "template"}
    assert ollama.status(off) == {"provider": "template", "writer": "template", "model_tag": None, "ollama_reachable": False, "model_pulled": False}


# ── the server: the website, its headers, the writer, the timings ─────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


def test_the_server_serves_the_website_with_the_same_headers_as_netlify(client):
    want = site_headers()
    r = client.get("/")
    assert r.status_code == 200 and "<title>DiaCausal" in r.text and INTENDED_USE in r.text
    for header, value in want["/*"].items():
        assert r.headers[header] == value, header
    assert client.get("/sw.js").headers["cache-control"] == want["/sw.js"]["Cache-Control"]
    assert client.get("/web/../data/params.yaml").status_code == 404  # only web/ is served
    assert "content-security-policy" not in client.get("/docs").headers  # the API docs keep FastAPI's own page
    r = client.get("/api/v1/not-a-route")
    assert r.status_code == 404 and r.json()["intended_use"] == INTENDED_USE


def test_only_the_local_server_tells_the_page_it_is_in_clinic_mode(client):
    """The server's config.json is the committed one (accounts off, no key) plus "clinic": true; the committed file has no "clinic",
    so on Netlify the page never asks /api/v1/llm (a 404 there would be a console error)."""
    committed = json.loads((ROOT / "web" / "config.json").read_text())
    served = client.get("/config.json").json()
    assert served == {**committed, "clinic": True} and "clinic" not in committed
    assert not any(k.lower().startswith("supabase") for k in served)
    app = (ROOT / "web" / "app.js").read_text()
    assert "if (config && config.clinic) await detectClinic();" in app


def test_the_page_can_ask_which_writer_answers(client, monkeypatch):
    monkeypatch.delenv(ollama.PROVIDER_ENV, raising=False)
    r = client.get("/api/v1/llm").json()
    assert r["writer"] == "template" and r["intended_use"] == INTENDED_USE and set(r) == {
        "provider", "writer", "model_tag", "ollama_reachable", "model_pulled", "intended_use"}


def test_every_answer_carries_the_time_of_each_layer(client):
    row = load_golden()[0]
    r = client.post("/api/v1/ask", json=json.loads(request_for(row, "template").model_dump_json()))
    assert r.status_code == 200
    timing = _measure().server_timing(r.headers["server-timing"])
    assert list(timing) == [entry.name.replace(" ", "-") for entry in registry.LAYERS]
    assert all(v >= 0 for v in timing.values())


# ── the measurement ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_measure_local_writes_ids_and_times_but_never_a_question_or_a_patient_value(client, tmp_path):
    m = _measure()

    class Here:  # the module's test client, through the script's own measure()
        startup_s = 1.0

        def get(self, path):
            return client.get(path).json()

        def post(self, path, body):
            r = client.post(path, json=body)
            return r.status_code, dict(r.headers), r.json()

    golden = load_golden()[:3]
    rows, summary = m.measure(Here(), golden, "template")
    per_question, totals = m.write(rows, summary, "testbox", tmp_path)
    text = per_question.read_text() + totals.read_text()
    read = list(csv.DictReader(per_question.open()))
    # the columns are exactly ids, the preset NAME, times and guard codes: no column can hold a patient value or any text
    assert list(read[0]) == m.ROW_COLUMNS and not set(m.ROW_COLUMNS) & {f for p in PRESET_PATIENTS.values() for f in p}
    assert [r["id"] for r in read] == [g["id"] for g in golden] and {r["preset"] for r in read} <= set(PRESET_PATIENTS)
    for g in golden:
        assert g["question"] not in text
    s = next(csv.DictReader(totals.open()))
    assert s["questions"] == "3" and s["answered"] == "3" and s["writer_asked"] == "template" and float(s["median_total_ms"]) > 0


def test_the_committed_measurement_has_no_question_text():
    files = sorted((ROOT / "results").glob("local_llm_*.csv"))
    assert files, "run scripts/measure_local.py once and commit its two files"
    questions = [g["question"] for g in load_golden()]
    for f in files:
        text = f.read_text(encoding="utf-8")
        assert not any(q in text for q in questions), f.name


def test_p95_is_the_linear_95th_percentile():
    m = _measure()
    assert m.p95([1, 2, 3, 4, 5]) == pytest.approx(4.8) and m.p95([7]) == 7
    assert m.server_timing("input-guards;dur=3.1, rules;dur=0.4, junk") == {"input-guards": 3.1, "rules": 0.4}
