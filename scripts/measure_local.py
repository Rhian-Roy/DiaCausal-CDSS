"""Measure DiaCausal on this computer: the 20 golden questions through POST /api/v1/ask (P29b; docs/OFFLINE_INSTALL.md).

    .venv/bin/python scripts/measure_local.py --machine rtx2050                  # starts its own server in-process (the usual way)
    .venv/bin/python scripts/measure_local.py --machine mac --writer template    # never ask the local model
    .venv/bin/python scripts/measure_local.py --machine mac --url http://127.0.0.1:8000   # a server already started (start_clinic.*)

Each question of eval/llm_golden.csv is asked with its demo patient (diacausal/llm/golden.py), with mode "ollama" when the local
model is available (GET /api/v1/llm) and "template" otherwise. Per-layer times come from the Server-Timing header of the reply.

Writes
    results/local_llm_<machine>.csv          one row per question: id, preset, HTTP status, total and per-layer ms, who wrote the
                                             answer, fallback_used, fallback_reason, failed output guards, dropped claims
    results/local_llm_<machine>_summary.csv  median and 95th-percentile total time, fallback rate, start-up time, writer, model tag
Only question IDs are written: never a question, an answer, a passage or a patient value. In-process, the audit log goes to a temporary
file, never to logs/audit.jsonl.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import statistics
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from diacausal import registry  # noqa: E402
from diacausal.llm.golden import load_golden, request_for  # noqa: E402

OUT = ROOT / "results"
LAYERS = [entry.name.replace(" ", "-") for entry in registry.LAYERS]
ROW_COLUMNS = ["id", "preset", "http_status", "total_ms", *[f"{name}_ms" for name in LAYERS], "writer", "fallback_used",
               "fallback_reason", "failed_checks", "dropped_claims"]
SUMMARY_COLUMNS = ["machine", "date", "questions", "answered", "writer_asked", "model_tag", "median_total_ms", "p95_total_ms",
                   "fallback_rate", "startup_s", "python", "platform"]


def server_timing(header: str) -> dict[str, float]:
    """'input-guards;dur=3.1, rules;dur=0.4' -> {'input-guards': 3.1, 'rules': 0.4}."""
    out = {}
    for part in filter(None, (p.strip() for p in (header or "").split(","))):
        m = re.fullmatch(r"([A-Za-z0-9_-]+);dur=([0-9.]+)", part)
        if m:
            out[m.group(1)] = float(m.group(2))
    return out


def p95(values: list[float]) -> float:
    """The 95th percentile, linear between the two nearest values (the same rule as numpy's default)."""
    xs = sorted(values)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * 0.95
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


class Remote:
    """A server already running (scripts/start_clinic.*)."""

    def __init__(self, url: str):
        self.url = url.rstrip("/")
        self.startup_s = float("nan")

    def get(self, path: str) -> dict:
        with urllib.request.urlopen(self.url + path, timeout=10) as r:
            return json.loads(r.read())

    def post(self, path: str, body: dict) -> tuple[int, dict, dict]:
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.status, dict(r.headers), json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), json.loads(e.read() or b"{}")

    def close(self):
        pass


class InProcess:
    """The same app, started here (FastAPI's test client): no port is opened at all."""

    def __init__(self):
        from fastapi.testclient import TestClient

        from diacausal.api.main import create_app
        from diacausal.causal_inference import recommend

        recommend.AUDIT_PATH = Path(tempfile.gettempdir()) / "diacausal-measure-audit.jsonl"  # never the real audit log
        t0 = time.perf_counter()
        self.client = TestClient(create_app())
        self.client.__enter__()  # runs the start-up: fits the engine, builds the search index
        self.startup_s = time.perf_counter() - t0

    def get(self, path: str) -> dict:
        return self.client.get(path).json()

    def post(self, path: str, body: dict) -> tuple[int, dict, dict]:
        r = self.client.post(path, json=body)
        return r.status_code, dict(r.headers), r.json()

    def close(self):
        self.client.__exit__(None, None, None)


def measure(server, golden: list[dict], writer: str) -> tuple[list[dict], dict]:
    status = server.get("/api/v1/llm")
    mode = "ollama" if writer == "auto" and status.get("writer") == "ollama" else "template"
    rows = []
    for row in golden:
        body = json.loads(request_for(row, mode).model_dump_json())
        t0 = time.perf_counter()
        code, headers, card = server.post("/api/v1/ask", body)
        total = (time.perf_counter() - t0) * 1000
        timing = server_timing({k.lower(): v for k, v in headers.items()}.get("server-timing", ""))
        ok = code == 200
        rows.append({
            "id": row["id"], "preset": row["preset"], "http_status": code, "total_ms": round(total, 1),
            **{f"{name}_ms": round(timing[name], 1) if name in timing else "" for name in LAYERS},
            "writer": card.get("mode", "") if ok else "", "fallback_used": card.get("fallback_used", "") if ok else "",
            "fallback_reason": (card.get("fallback_reason") or "") if ok else "",
            "failed_checks": " ".join(card.get("failed_checks", [])) if ok else "", "dropped_claims": card.get("dropped_claims", "") if ok else "",
        })
        print(f"  {row['id']}  {code}  {total:8.0f} ms  writer={rows[-1]['writer'] or '-'}  fallback={rows[-1]['fallback_reason'] or '-'}", flush=True)
    answered = [r for r in rows if r["http_status"] == 200]
    totals = [float(r["total_ms"]) for r in answered]
    summary = {
        "questions": len(rows), "answered": len(answered), "writer_asked": mode,
        "model_tag": status.get("model_tag") or "" if mode == "ollama" else "",
        "median_total_ms": round(statistics.median(totals), 1) if totals else "",
        "p95_total_ms": round(p95(totals), 1) if totals else "",
        "fallback_rate": round(sum(r["fallback_used"] is True for r in answered) / len(answered), 3) if answered else "",
        "startup_s": round(server.startup_s, 1) if server.startup_s == server.startup_s else "",
    }
    return rows, summary


def write(rows: list[dict], summary: dict, machine: str, out_dir: Path = OUT) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    per_question, totals = out_dir / f"local_llm_{machine}.csv", out_dir / f"local_llm_{machine}_summary.csv"
    with per_question.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=ROW_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    with totals.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_COLUMNS)
        w.writeheader()
        w.writerow({"machine": machine, "date": date.today().isoformat(), **summary, "python": platform.python_version(),
                    "platform": f"{platform.system()} {platform.machine()}"})
    return per_question, totals


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--machine", required=True, help="a short name for this computer, e.g. rtx2050 (letters, digits, - and _)")
    ap.add_argument("--writer", choices=["auto", "template"], default="auto", help="auto: the local model when it is available")
    ap.add_argument("--url", help="measure a server that is already running, e.g. http://127.0.0.1:8000")
    ap.add_argument("--out", type=Path, default=OUT, help="folder for the two CSV files (default: results/)")
    a = ap.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", a.machine):
        ap.error("--machine: use letters, digits, - and _ only")
    if not a.url and a.writer == "auto":
        os.environ.setdefault("DIACAUSAL_LLM_PROVIDER", "ollama")  # as scripts/start_clinic.* do; the template answers if Ollama is not running
    golden = load_golden()
    print(f"Measuring {len(golden)} golden questions on '{a.machine}' (question text is never printed)")
    server = Remote(a.url) if a.url else InProcess()
    try:
        rows, summary = measure(server, golden, a.writer)
    finally:
        server.close()
    per_question, totals = write(rows, summary, a.machine, a.out)
    print(f"writer asked: {summary['writer_asked']} {summary['model_tag']}  median {summary['median_total_ms']} ms  "
          f"p95 {summary['p95_total_ms']} ms  fallback rate {summary['fallback_rate']}  start-up {summary['startup_s']} s")
    print(f"Saved {per_question.relative_to(ROOT) if per_question.is_relative_to(ROOT) else per_question} and {totals.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
