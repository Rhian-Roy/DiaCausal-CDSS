#!/usr/bin/env python3
"""Check that everything in the DiaCausal chat app works, with one command.

    macOS / Linux:  python3 scripts/check_all.py
    Windows:        py scripts/check_all.py

Needs the one-time setup first (scripts/setup.py). Any Python 3.9+ can run this
file; it uses the backend's own Python (backend/.venv) for the backend parts.

What it does, in order:
  1. tools      the right Python and Node are installed
  2. backend    all pytest tests pass
  3. frontend   all Vitest tests pass (incl. the whole press-Enter flow)
  4. build      TypeScript type-check + production build
  5. lint       oxlint finds no problems
  6. live API   starts the real backend on a spare port and sends it real
                requests: a question, an image part, 8001 characters, an empty
                message, an identifier, foul language; checks the replies and the
                trace ID in the backend log
  7. live page  starts the real frontend on a spare port and sends a message
                through its /api proxy to that backend
Servers you may already have running on 8000/5173 are not touched.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
WINDOWS = sys.platform == "win32"
VENV_PY = BACKEND / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")
VITE = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
STAGES = ["backend_guard", "clinical_guardrails", "causal_engine", "rag_retrieval", "llm_explanation", "output_guard"]
SETUP = "py -3.12 scripts/setup.py" if WINDOWS else "python3.12 scripts/setup.py"

results: list[bool] = []
# Talk to our own local servers directly, never through a system proxy.
http = urllib.request.build_opener(urllib.request.ProxyHandler({}))


# ── small helpers ────────────────────────────────────────────────────────────


def section(number: int, title: str) -> None:
    print(f"\n{number}. {title}")


def check(ok: bool, label: str, why: str = "") -> bool:
    results.append(ok)
    print(f"   [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok and why:
        for line in why.strip().splitlines()[-25:]:
            print(f"          {line}")
    return ok


def run(cmd: list[str], cwd: Path, timeout: int = 900) -> tuple[int, str]:
    env = {**os.environ, "NO_COLOR": "1", "FORCE_COLOR": "0", "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.run(
            [str(part) for part in cmd], cwd=cwd, env=env, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, str(error)
    return proc.returncode, ANSI.sub("", proc.stdout + proc.stderr)


def version_of(cmd: list[str]) -> tuple[str, tuple[int, int]]:
    code, out = run(cmd, ROOT, timeout=60)
    match = re.search(r"(\d+)\.(\d+)\.\d+", out)
    if code != 0 or not match:
        return "", (0, 0)
    return match[0], (int(match[1]), int(match[2]))


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def call(url: str, body: dict | None = None, raw: bytes | None = None) -> tuple[int, str, dict]:
    """GET (no body) or POST JSON. Returns (status, text, headers)."""
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with http.open(request, timeout=20) as response:
            return response.status, response.read().decode("utf-8", "replace"), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace"), dict(error.headers)


def wait_until_up(url: str, process: subprocess.Popen, seconds: int = 60) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if process.poll() is not None:
            return False  # it crashed
        try:
            call(url)
            return True
        except OSError:
            time.sleep(0.3)
    return False


def start(cmd: list[str], cwd: Path, log: Path, env: dict | None = None) -> subprocess.Popen:
    with open(log, "w", encoding="utf-8") as handle:
        return subprocess.Popen(
            [str(part) for part in cmd], cwd=cwd, stdout=handle, stderr=subprocess.STDOUT,
            env={**os.environ, "NO_COLOR": "1", **(env or {})},
        )


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def read(log: Path) -> str:
    return ANSI.sub("", log.read_text(encoding="utf-8", errors="replace")) if log.exists() else ""


def parse(text: str) -> dict:
    try:
        data = json.loads(text)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def chat(text: str, trace: str, **overrides) -> dict:
    return {"schema_version": "1.0", "client_trace_id": trace, "parts": [{"type": "text", "text": text}], **overrides}


# ── the checks ───────────────────────────────────────────────────────────────


def check_tools(npm: str | None, node: str | None) -> bool:
    section(1, "Tools")
    py_text, py = version_of([VENV_PY, "--version"]) if VENV_PY.exists() else ("", (0, 0))
    ok = check(py == (3, 12), f"backend Python is 3.12 (found: {py_text or 'none - backend/.venv missing'})")
    node_text, (major, minor) = version_of([node, "--version"]) if node else ("", (0, 0))
    # The pinned test tools (Vitest 5, jsdom 30) support Node 22.22+, 24.15+ and 26+.
    node_ok = (major == 22 and minor >= 22) or (major == 24 and minor >= 15) or major >= 26
    ok &= check(node_ok, f"Node.js 24 LTS (24.15+) installed (found: {node_text or 'none'})")
    ok &= check(bool(npm), "npm installed")
    ok &= check((FRONTEND / "node_modules").is_dir(), "frontend libraries installed (frontend/node_modules)")
    if not ok:
        print(f"\n   Run the one-time setup first:  {SETUP}   (details: docs/SETUP.md)")
    return ok


def check_backend_tests() -> None:
    section(2, "Backend tests (pytest)")
    code, out = run([VENV_PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"], BACKEND)
    passed = re.search(r"(\d+) passed", out)
    check(code == 0, f"{passed[1] if passed else 0} backend tests passed", out)


def check_frontend(npm: str) -> None:
    section(3, "Frontend tests (Vitest, simulated browser)")
    code, out = run([npm, "test"], FRONTEND)
    passed = re.search(r"Tests\s+(?:\d+ failed \| )?(\d+) passed", out)
    check(code == 0, f"{passed[1] if passed else 0} frontend tests passed (incl. Enter -> 4 console lines -> reply)", out)

    section(4, "Frontend type-check + production build")
    code, out = run([npm, "run", "build"], FRONTEND)
    check(code == 0, "TypeScript found no type errors and the build succeeded", out)

    section(5, "Frontend lint (oxlint)")
    code, out = run([npm, "run", "lint"], FRONTEND)
    problems = re.search(r"Found (\d+) warnings? and (\d+) errors?", out)
    clean = code == 0 and (problems is None or problems.groups() == ("0", "0"))
    check(clean, "no lint warnings or errors", out)


def check_live(node: str) -> None:
    trace = "check" + secrets.token_hex(3)
    secret_word = "ZEBRA" + secrets.token_hex(3)  # must never reach the backend log
    logs = Path(tempfile.mkdtemp(prefix="diacausal-check-"))
    api_port, web_port = free_port(), free_port()
    api_url = f"http://127.0.0.1:{api_port}"
    web_url = f"http://127.0.0.1:{web_port}"

    section(6, f"Live backend (real server on port {api_port})")
    api = start([VENV_PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(api_port)],
                BACKEND, logs / "backend.log")
    try:
        if not check(wait_until_up(api_url + "/api/health", api), "backend starts", read(logs / "backend.log")):
            return

        status, text, _ = call(api_url + "/api/health")
        check(status == 200 and parse(text) == {"status": "ok", "schema_version": "1.0"},
              "GET /api/health says ok", text)

        status, text, headers = call(api_url + "/api/v1/chat", chat(f"Test question {secret_word}: what next?", trace))
        reply = parse(text) if status == 200 else {}
        stages = [(s.get("name"), s.get("status")) for s in reply.get("stages", [])]
        expected = [(name, "passed" if name in ("backend_guard", "output_guard") else "skipped") for name in STAGES]
        first_part = (reply.get("parts") or [{}])[0]
        check(status == 200 and reply.get("outcome") == "answered"
              and str(first_part.get("text", "")).startswith("Dummy reply"),
              "a question gets the dummy reply", text)
        check(stages == expected, "reply lists the 6 stages in order: first and last passed, the rest skipped", text)
        check(reply.get("trace_id") == trace and headers.get("X-Trace-Id", headers.get("x-trace-id")) == trace,
              f"reply carries the same trace ID ({trace})", text)

        status, text, _ = call(api_url + "/api/v1/chat",
                               chat("x", trace, parts=[{"type": "image", "url": "scan.png"}]))
        message = str(parse(text).get("message", ""))
        check(status == 422 and 'has type "image"' in message, 'an "image" part is refused with a clear message (422)', text)

        status, text, _ = call(api_url + "/api/v1/chat", chat("a" * 8001, trace))
        message = str(parse(text).get("message", ""))
        check(status == 422 and "8,001 characters" in message, "text over 8000 characters is refused (422)", text)

        status, text, _ = call(api_url + "/api/v1/chat", chat("   ", trace))
        blocked = parse(text) if status == 200 else {}
        check(blocked.get("outcome") == "blocked" and (blocked.get("stages") or [{}])[0].get("status") == "blocked",
              "an empty message is blocked by backend_guard", text)

        status, text, _ = call(api_url + "/api/v1/chat", chat("Patient Aadhaar 726018159082, HbA1c 8.4%", trace))
        reply = parse(text) if status == 200 else {}
        check(reply.get("outcome") == "blocked" and reply.get("reason_code") == "identifier"
              and "726018159082" not in text,
              "a patient identifier is blocked by the server guard (notice 09)", text)

        rude = "bullshit"  # from shared/guard_rules/rules.v1.json
        status, text, _ = call(api_url + "/api/v1/chat", chat(f"what {rude} answer is this", trace))
        reply = parse(text) if status == 200 else {}
        check(reply.get("outcome") == "blocked" and reply.get("reason_code") == "language" and rude not in text,
              "foul language is blocked by the server guard without repeating the word", text)

        time.sleep(0.5)
        log = read(logs / "backend.log")
        check(rude not in log and "726018159082" not in log and "guard rules version" in log,
              "the backend log shows the guard rules version, never the blocked word or identifier", log)
        needed = ["chat request received", *[f"{name}:" for name in STAGES], "reply sent"]
        tagged = [line for line in log.splitlines() if f"[{trace}]" in line]
        check(all(any(word in line for line in tagged) for word in needed),
              f"backend log shows [{trace}] on the request, every stage and the reply", log)
        check(secret_word not in log, "the message text never appears in the backend log", log)

        section(7, f"Live page (real frontend on port {web_port}, /api forwarded to port {api_port})")
        web = start([node, VITE, "--host", "127.0.0.1", "--port", str(web_port), "--strictPort"],
                    FRONTEND, logs / "frontend.log", env={"DIACAUSAL_API_URL": api_url})
        try:
            if not check(wait_until_up(web_url + "/", web), "frontend starts", read(logs / "frontend.log")):
                return
            status, text, _ = call(web_url + "/")
            check(status == 200 and "<title>DiaCausal — Chat</title>" in text, "the chat page loads", text[:500])

            page_trace = "check" + secrets.token_hex(3)
            status, text, _ = call(web_url + "/api/v1/chat", chat("Through the page", page_trace))
            ok = status == 200 and parse(text).get("trace_id") == page_trace
            check(ok, "a message sent via the page's /api reaches the backend and comes back", text or read(logs / "frontend.log"))
        finally:
            stop(web)
    finally:
        stop(api)


def main() -> None:
    # Show each line as it happens, and never crash on a character the terminal can't show
    # (e.g. Windows when the output goes to a file or Git Bash).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace", line_buffering=True)
    started = time.time()
    print("DiaCausal: checking everything")
    npm, node = shutil.which("npm"), shutil.which("node")

    if not check_tools(npm, node):
        sys.exit(1)
    check_backend_tests()
    check_frontend(npm)  # type: ignore[arg-type]
    check_live(node)  # type: ignore[arg-type]

    failed = results.count(False)
    print(f"\n{'=' * 64}")
    if failed == 0:
        print(f"ALL {len(results)} CHECKS PASSED in {time.time() - started:.0f}s.")
        print("Left to check by eye in a real browser: docs/TESTING.md, part 2.")
    else:
        print(f"{failed} of {len(results)} checks FAILED - see the [FAIL] lines above.")
        print("Common fixes are in docs/TESTING.md, part 4.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
