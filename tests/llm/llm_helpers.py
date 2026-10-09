"""A fake Ollama server for the tests: it records every request and answers as the test says. No model, no network beyond localhost."""

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


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
