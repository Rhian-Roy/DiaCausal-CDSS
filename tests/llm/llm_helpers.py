"""A fake Ollama server for the tests: it records every request and answers as the test says. No model, no network beyond localhost."""

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class FakeOllama:
    """`reply` is a function (prompt) -> text for the model's "response" field, or a dict {"status": 500} / {"raw": b"..."} /
    {"sleep": seconds, "then": function}. Every request body is kept in `requests`."""

    def __init__(self, reply):
        self.reply, self.requests, self.paths = reply, [], []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append(body)
                outer.paths.append(self.path)
                spec = outer.reply
                if isinstance(spec, dict):
                    if "sleep" in spec:
                        time.sleep(spec["sleep"])
                        spec = {"text": spec["then"](body["prompt"])}
                    if "status" in spec:
                        self.send_response(spec["status"])
                        self.end_headers()
                        return
                    if "raw" in spec:
                        data = spec["raw"]
                    else:
                        data = json.dumps({"response": spec["text"], "prompt_eval_count": 1500, "eval_count": 90}).encode()
                else:
                    data = json.dumps({"response": spec(body["prompt"]), "prompt_eval_count": 1500, "eval_count": 90}).encode()
                try:
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def do_GET(self):
                data = b'{"version":"0.0.0-fake"}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def evidence_lines(prompt: str) -> list[tuple[str, str]]:
    """(chunk_id, quoted text) of every evidence line of a section 8.9 prompt."""
    return re.findall(r'^\[([A-Z]\d+[\w.-]*)\] [^\n]*?: "(.*)"$', prompt, flags=re.M)


def good_draft(prompt: str, claims: int = 1) -> str:
    """A well-behaved model: each claim quotes the start of a real passage (no digits) and cites its chunk id."""
    out = []
    for cid, text in evidence_lines(prompt)[:claims]:
        words = [w for w in text.split() if not re.search(r"\d", w)][:14]
        out.append({"claim": " ".join(words), "chunk_ids": [cid]})
    return json.dumps({"question_context": "The question is about the passages.", "evidence_summary": out, "limitations": "Only the retrieved passages were used."})


# ── inputs for the prompt builder (P22) ──────────────────────────────────────────────────────────────────────────
EXAMPLES = Path(__file__).resolve().parents[1] / "contract" / "examples"


def example(name: str):
    """A validated contract example (tests/contract/examples/<name>.json) as its model; `_note` is the comment key those files allow."""
    from diacausal.api import schemas

    data = json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    data.pop("_note", None)
    return getattr(schemas, name).model_validate(data)


def bundle(*texts: str, page: int | None = 12):
    """An EvidenceBundleV1 of synthetic passages (made-up wording, so no clinical claim is invented): one chunk per text."""
    from diacausal.api.schemas import EvidenceBundleV1

    chunks = [{"chunk_id": f"S0{i + 1}-p{page or 0}-c{i}", "source": f"Synthetic source {i + 1}", "version": "2018", "section": f"Section {i + 1}",
               "page": page, "licence": "synthetic", "text": text, "scores": {"bm25": 1.0, "dense": None, "rrf": 0.03}} for i, text in enumerate(texts)]
    return EvidenceBundleV1.model_validate({"status": "OK", "index_version": "kb@test", "chunks": chunks})


def sentence_block(label: str, sentences: int, words_each: int = 12) -> str:
    """`sentences` sentences of `words_each` made-up words each, numbered so a cut is easy to see."""
    return " ".join(f"{label} sentence {n} " + " ".join(f"w{label}{n}x{k}" for k in range(words_each - 3)) + "." for n in range(1, sentences + 1))
