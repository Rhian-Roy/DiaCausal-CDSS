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
