"""The website (web/): same answers as the Python engine, fresh model, safe files.

Run: python -m pytest tests/web -q      (needs Node.js for the parity test)
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from diacausal_engine import INTENDED_USE  # noqa: E402
from diacausal_engine.export_web import model_dict  # noqa: E402
from diacausal_engine.recommend import DOSE_PATTERN, Engine  # noqa: E402
from diacausal_engine.schemas import PatientIn  # noqa: E402
from diacausal_rag.export_web import evidence_dict  # noqa: E402
from diacausal_rag.ingest import ingest  # noqa: E402
from diacausal_rag.retrieve import Retriever  # noqa: E402

WEB = ROOT / "web"
NODE = shutil.which("node")
PRESETS = [
    dict(age=52, sex="male", duration_years=5, hba1c=8.4, egfr=88, bmi=27.0),
    dict(age=60, sex="female", duration_years=8, hba1c=8.2, egfr=40, bmi=25.5, pancreatitis_history=True),
    dict(age=80, sex="male", duration_years=15, hba1c=8.0, egfr=38, bmi=24.0, hypo_history=True, ascvd=True),
    dict(age=30, sex="male", duration_years=5, hba1c=8.0, egfr=90, bmi=22.0, t1d=True),
    dict(age=52, sex="male", duration_years=5, hba1c=8.4, egfr=25, bmi=27.0),
]
FLAGS = ("ascvd", "hf", "hypo_history", "t1d", "dka_history", "pancreatitis_history", "low_income")


def random_patients(n, seed=5):
    rng = np.random.default_rng(seed)
    for _ in range(n):
        yield dict(
            age=int(rng.integers(18, 100)), sex=str(rng.choice(["female", "male"])),
            duration_years=float(np.round(rng.uniform(0, 40), 1)), hba1c=float(np.round(rng.uniform(5, 15), 1)),
            egfr=float(rng.integers(5, 140)), bmi=float(np.round(rng.uniform(15, 50), 1)),
            **{f: bool(rng.random() < 0.15) for f in FLAGS},
        )


@pytest.fixture(scope="module")
def engine():
    return Engine()  # the same reference engine export_web uses


@pytest.fixture(scope="module")
def model():
    return json.loads((WEB / "model.json").read_text())


def test_model_json_is_fresh(engine, model):
    """web/model.json must be the export of the current params, rules and code."""
    fresh = json.loads(json.dumps(model_dict(engine)))
    assert model["versions"] == fresh["versions"], "run: python -m diacausal_engine.export_web"
    for key in ("features", "rules", "thresholds", "support", "prices", "assumptions", "arms"):
        assert model[key] == fresh[key], key
    for part in ("propensity", "dr"):
        for k, v in fresh[part].items():
            assert np.allclose(np.array(model[part][k]), np.array(v), rtol=0, atol=1e-12), f"{part}.{k}"


@pytest.mark.skipif(NODE is None, reason="Node.js is needed to run web/engine.js")
def test_browser_engine_gives_the_same_answers_as_python(engine, model, tmp_path):
    patients = PRESETS + list(random_patients(150))
    (tmp_path / "p.json").write_text(json.dumps(patients))
    js = json.loads(subprocess.run([NODE, str(ROOT / "tests/web/run_engine.cjs"), str(WEB / "model.json"),
                                    str(tmp_path / "p.json")], capture_output=True, text=True, check=True).stdout)
    seen = set()
    for p, j in zip(patients, js):
        py = engine.recommend(PatientIn(**p), audit=False)
        assert j["applicable"] == py.applicable
        assert j["not_applicable_reasons"] == py.not_applicable_reasons
        assert j["bmi_category"] == py.bmi_category
        for jo, po in zip(j["options"], py.options):
            seen.add(po.status)
            assert (jo["arm"], jo["status"]) == (po.arm, po.status), p
            assert [s["rule_id"] for s in jo["safety"]] == [s.rule_id for s in po.safety]
            assert jo["insufficient_reason"] == po.insufficient_reason
            if po.status == "estimate":
                x = np.array([[float({**p, "female": int(p["sex"] == "female")}.get(c, 0)) for c in engine.adjustment]])
                raw = engine.fitted.dr.predict(x, engine.z)[po.arm][0]
                assert np.allclose([jo["_raw"]["value"], jo["_raw"]["ci_low"], jo["_raw"]["ci_high"]], raw, atol=1e-9)
                for k in ("value", "ci_low", "ci_high"):
                    assert abs(jo["effect"][k] - getattr(po.effect, k)) <= 0.0011
        assert [(c["first"], c["second"]) for c in j["comparisons"]] == [(c.first, c.second) for c in py.comparisons]
        assert j["intended_use"] == INTENDED_USE
    assert {"estimate", "excluded", "insufficient_evidence"} <= seen


QUESTIONS = [
    "metformin kidney function eGFR", "Can metformin be used with an eGFR of 35?", "contrast imaging procedure",
    "lactic acidosis risk", "When should metformin be discontinued?", "heart failure", "saxagliptin heart failure",
    "creatinine versus glomerular filtration rate", "side effects of metformin diarrhea nausea",
    "low blood sugar alcohol", "elderly renal function assessed more frequently", "metformin-containing medicines",
    "MedWatch report side effects", "liver disease alcoholism", "What is the capital of France?", "", "the of and",
    "SGLT2 inhibitor", "iodinated contrast 48 hours", "eGFR 30 45", "Métformine rénale", "kidney kidney kidney",
    "blood sugar", "mild to moderate renal impairment", "Before starting metformin obtain eGFR", "annually",
    "patients with type 2 diabetes", "dye injected into a vein X-ray", "pancreatitis", "hypoglycaemia sulfonylurea",
    "FDA labeling changes", "measure of kidney function", "safety announcement", "data summary 1995",
    "chronic kidney disease", "Glucophage", "diet and exercise", "insulin", "heart disease blindness", "eGFR",
]


def test_evidence_json_is_fresh():
    """web/evidence.json must be the export of the current corpus, licence table and settings."""
    data = json.loads((WEB / "evidence.json").read_text())
    assert data == json.loads(json.dumps(evidence_dict())), "run: python -m diacausal_rag.export_web"
    assert data["chunks"], "the confirmed FDA communication should be in the website index"
    assert all(c["citation"]["source_id"] == "S08" for c in data["chunks"])


@pytest.mark.skipif(NODE is None, reason="Node.js is needed to run web/evidence.js")
def test_browser_evidence_search_gives_the_same_passages_as_python(tmp_path):
    chunks = ingest()
    retriever = Retriever(chunks)
    (tmp_path / "q.json").write_text(json.dumps(QUESTIONS))
    js = json.loads(subprocess.run([NODE, str(ROOT / "tests/web/run_evidence.cjs"), str(WEB / "evidence.json"),
                                    str(tmp_path / "q.json")], capture_output=True, text=True, check=True).stdout)
    statuses = set()
    for q, j in zip(QUESTIONS, js):
        py = retriever.search(q)
        statuses.add(py["status"])
        assert j["status"] == py["status"], q
        assert j.get("reason") == py.get("reason"), q
        assert [p["citation"] for p in j["passages"]] == [p["citation"] for p in py["passages"]], q
        assert [p["text"] for p in j["passages"]] == [p["text"] for p in py["passages"]], q
        for jp, pp in zip(j["passages"], py["passages"]):
            assert jp["scores"] == pp["scores"], q
        assert j["intended_use"] == INTENDED_USE
    assert statuses == {"SUCCESS", "INSUFFICIENT_EVIDENCE"}


def test_site_files_carry_the_intended_use_and_no_doses():
    html = (WEB / "index.html").read_text()
    assert INTENDED_USE in html
    for f in WEB.rglob("*"):
        if f.suffix in (".html", ".js", ".css", ".json", ".webmanifest") and "vendor" not in f.parts:
            text = f.read_text()
            if f.name == "model.json":
                text = text.replace(json.loads(text)["dose_pattern"], "")
            assert not DOSE_PATTERN.search(text), f.name


def test_no_clinical_threshold_is_typed_into_the_website_code():
    pattern = re.compile(r"\b(egfr|hba1c|age|bmi)\w*\s*(<=|>=|<|>|===?)\s*\d", re.I)
    for name in ("engine.js", "app.js"):
        for n, line in enumerate((WEB / name).read_text().splitlines(), 1):
            assert not pattern.search(line), f"{name}:{n}: {line.strip()}"


def test_no_inline_script_or_style_so_the_strict_csp_holds():
    html = (WEB / "index.html").read_text()
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), "inline <script>"
    assert "style=" not in html and "<style" not in html
    assert "style=" not in (WEB / "app.js").read_text() and "onclick" not in html
    csp = json.loads((WEB / "vercel.json").read_text())
    header = {h["key"]: h["value"] for rule in csp["headers"] for h in rule["headers"]}
    assert "script-src 'self'" in header["Content-Security-Policy"]
    assert "unsafe-inline" not in header["Content-Security-Policy"]
    # The live site is on Netlify: its headers must be the same as Vercel's.
    toml = (WEB / "netlify.toml").read_text()
    for key, value in header.items():
        assert f'{key} = "{value}"' in toml, f"netlify.toml differs from vercel.json on {key}"


def test_team_details_are_correct():
    """Group 28 is a B.Tech in Computer Engineering; the guide is Mr. Rahul Jadhav."""
    html = (WEB / "index.html").read_text()
    assert "B.Tech in Computer Engineering" in html and "Guide: Mr. Rahul Jadhav." in html
    for path in [*WEB.rglob("*.html"), *WEB.rglob("*.js"), *(ROOT / "docs").rglob("*.md"), ROOT / "README.md"]:
        text = path.read_text(encoding="utf-8")
        assert "Jyoti More" not in text, path
        assert "B.E. Computer" not in text and "B.E. (Computer)" not in text, path


GATE_CASES = [  # (state, expected screen) — the order is sign in, MFA, approval, intended use
    ({"configured": False}, "demo"),
    ({"configured": True}, "signin"),
    ({"configured": True, "session": {}, "recovery": True}, "new-password"),
    ({"configured": True, "session": {}, "verifiedFactors": 0}, "mfa-setup"),
    ({"configured": True, "session": {}, "verifiedFactors": 1, "aal": "aal1"}, "mfa-code"),
    ({"configured": True, "session": {}, "verifiedFactors": 1, "aal": "aal2"}, "loading"),
    ({"configured": True, "session": {}, "verifiedFactors": 1, "aal": "aal2", "profileError": "x"}, "error"),
    ({"configured": True, "session": {}, "verifiedFactors": 1, "aal": "aal2", "profile": {"approved": False, "rejected": True}}, "rejected"),
    ({"configured": True, "session": {}, "verifiedFactors": 1, "aal": "aal2", "profile": {"approved": False}}, "pending"),
    ({"configured": True, "session": {}, "verifiedFactors": 1, "aal": "aal2", "profile": {"approved": True}}, "acknowledge"),
    ({"configured": True, "session": {}, "verifiedFactors": 1, "aal": "aal2",
      "profile": {"approved": True, "intended_use_ack_at": "2026-09-26"}}, "app"),
    # approval never skips MFA: an approved person without the code still sees the code screen
    ({"configured": True, "session": {}, "verifiedFactors": 1, "aal": "aal1",
      "profile": {"approved": True, "intended_use_ack_at": "2026-09-26"}}, "mfa-code"),
]


@pytest.mark.skipif(NODE is None, reason="Node.js is needed to run web/auth.js")
def test_sign_in_steps_come_in_the_right_order():
    script = ("const a=require(process.argv[1]);const c=JSON.parse(process.argv[2]);"
              "process.stdout.write(JSON.stringify({views:c.map(s=>a.gateView(s)),protected:a.PROTECTED,"
              "pw:[a.passwordProblems('short',''),a.passwordProblems('password1234',''),a.passwordProblems('a long enough sentence here','')]}))")
    out = json.loads(subprocess.run([NODE, "-e", script, str(WEB / "auth.js"), json.dumps([c for c, _ in GATE_CASES])],
                                    capture_output=True, text=True, check=True).stdout)
    assert out["views"] == [v for _, v in GATE_CASES]
    assert out["protected"] == ["try", "evidence"]
    assert out["pw"][0] and out["pw"][1] and out["pw"][2] == []


def test_no_account_key_is_committed():
    """The publishable key goes only into the deployed copy (scripts/web_config.py), never into git."""
    cfg = json.loads((WEB / "config.json").read_text())
    assert cfg.get("accounts") == "off" and "supabaseKey" not in cfg and "supabaseUrl" not in cfg
    for f in [*WEB.rglob("*"), *(ROOT / "scripts").glob("*.py"), *(ROOT / "docs").rglob("*.md")]:
        if f.is_file() and f.suffix in (".js", ".json", ".html", ".toml", ".py", ".md") and "vendor" not in f.parts:
            text = f.read_text(encoding="utf-8", errors="ignore")
            assert not re.search(r"sb_publishable_[A-Za-z0-9_-]{10,}|sb_secret_|eyJhbGciOi", text), f
    r = subprocess.run([sys.executable, str(ROOT / "scripts/web_config.py"), str(WEB / "config.json")],
                       capture_output=True, text=True, env={"SUPABASE_URL": "https://abcdefghijabcdefghij.supabase.co",
                                                            "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_test"})
    assert r.returncode == 2 and "Refusing" in r.stderr
    assert json.loads((WEB / "config.json").read_text()) == cfg


def test_account_code_never_sends_patient_details():
    """auth.js and account.js may only touch the profiles table and the two account functions."""
    code = (WEB / "auth.js").read_text() + (WEB / "account.js").read_text()
    assert set(re.findall(r"\.from\(\"(\w+)\"\)", code)) == {"profiles"}
    assert set(re.findall(r"\.rpc\(\"(\w+)\"", code)) == {"acknowledge_intended_use", "approve_user"}
    for field in PatientIn.model_fields:
        assert not re.search(rf"\b{field}\b", code), field
    for name in ("readForm", "recommend(", "DiaCausalEvidence", "EVIDENCE", "MODEL"):
        assert name not in code, name
    assert "supabase" not in (WEB / "engine.js").read_text() + (WEB / "evidence.js").read_text()


def test_accounts_database_is_locked_down():
    sql = "\n".join(p.read_text() for p in sorted((ROOT / "supabase/migrations").glob("*.sql")))
    code = re.sub(r"--[^\n]*|'[^']*'", "", sql).lower()  # without comments and text strings
    assert "enable row level security" in sql
    assert "for update" not in sql and "for insert" not in sql and "for delete" not in sql  # nobody writes directly
    assert "revoke insert, update, delete on table public.profiles from authenticated" in sql
    assert "'aal2'" in sql  # admins act only after their authenticator code
    for word in ("hba1c", "egfr", "bmi", "patient", "question", "answer"):
        assert word not in code, word  # the account database has no place for clinical data


def test_installable_on_a_phone():
    manifest = json.loads((WEB / "manifest.webmanifest").read_text())
    assert manifest["display"] == "standalone" and manifest["start_url"]
    for icon in manifest["icons"]:
        assert (WEB / icon["src"].lstrip("./")).exists(), icon["src"]
    assert (WEB / "icons/apple-touch-icon.png").exists()
    html = (WEB / "index.html").read_text()
    assert 'rel="apple-touch-icon"' in html and 'rel="manifest"' in html


def test_every_file_the_offline_cache_lists_exists():
    sw = (WEB / "sw.js").read_text()
    assets = re.search(r"const ASSETS = \[(.*?)\];", sw, re.S).group(1)
    for path in re.findall(r'"\./([^"]*)"', assets):
        assert (WEB / (path or "index.html")).exists(), path


def test_results_and_docs_are_copied_for_the_site():
    for name in ("overlap", "love_plot", "ate_vs_truth", "cate_recovery", "calibration"):
        assert (WEB / "results" / f"{name}.png").exists()
    assert (WEB / "docs/causal-engine.md").read_text() == (ROOT / "docs/explain/07-causal-engine.md").read_text()
    assert (WEB / "docs/results-summary.md").read_text() == (ROOT / "docs/RESULTS_SUMMARY.md").read_text()


def _chromium():
    for path in ("/opt/pw-browsers/chromium",):
        if Path(path).exists():
            return path
    return None


@pytest.mark.skipif(NODE is None or _chromium() is None or not (ROOT / "e2e/node_modules/playwright").exists(),
                    reason="needs Node, Playwright (e2e/node_modules) and a Chromium binary")
def test_the_site_works_on_an_iphone_sized_screen(tmp_path):
    """Loads the real page at 393x852, runs the three presets, Results, Learn and About."""
    import functools
    import http.server
    import os
    import threading

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB))
    handler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        out = subprocess.run([NODE, str(ROOT / "tests/web/phone_check.cjs"), f"http://127.0.0.1:{server.server_port}/", str(tmp_path)],
                             capture_output=True, text=True, timeout=180, env={**os.environ, "CHROMIUM_PATH": _chromium()})
    finally:
        server.shutdown()
    assert out.returncode == 0, out.stderr[-2000:]
    report = json.loads(out.stdout.strip().splitlines()[-1])
    c = report["checks"]
    assert report["errors"] == []
    assert c["intended"] and c["excluded"] == 1 and c["caution"] >= 1 and c["insufficient"] >= 1
    assert c["tiles"] == 8 and c["docHeadings"] > 10 and c["horizontalOverflow"] is False
    assert c["team"] is True
    assert c["passages"] >= 1 and c["citesFda"] and c["sourcesInSearch"] == 1 and c["abstains"]
    assert c["demoBanner"] and c["accountDemo"]  # a local copy without account settings says sign-in is off
