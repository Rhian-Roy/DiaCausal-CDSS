"""Ollama provider: a small model running on this computer; nothing leaves the machine.

Two ways in:

  call_ollama(prompt, cfg)             the older free-text call (numbered [n] citations), kept for the `explain(..., caller=...)` path
  request_draft(prompt, cfg)           P21/P23: the structured call below; it only TALKS to the model. What comes back is not trusted:
                                       diacausal/llm/answer.py runs the seven output checks (diacausal/guards/output_guards.py) on it and
                                       uses the template instead of anything that fails

The structured call: POST {ollama_url}/api/generate with
    model    the tag of llm.yaml `models.<model>.tag` (never typed anywhere else)
    format   the JSON schema of AnswerDraftV1 (Ollama constrains the reply to it: docs.ollama.com/api/generate, "format")
    options  {"temperature": 0, "num_ctx": 4096}
    stream   false      keep_alive   "10m"      think   only if llm.yaml sets it
and a timeout of `timeout_seconds` (60). With stream false the reply arrives all at once, so that is in effect the whole answer; a
COLD model load can exceed it (then the question is answered by the template; keep_alive keeps the model loaded afterwards).

ANY error, timeout or bad HTTP status gives a ModelReply with a CODE and no text, and the template answers (llm/answer.py). Only the
exception class and the code are ever logged or put in a reply, never the model's text, the prompt or the question.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from diacausal.api.schemas import AnswerDraftV1
from diacausal.config import load_rag_config

CONFIG_PATH = Path(__file__).resolve().parents[1] / "llm.yaml"


class OllamaError(Exception):
    """Something went wrong talking to Ollama; `code` is a short upper-case reason (never text from the model)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def load_llm_config(path: Path = CONFIG_PATH) -> dict:
    return load_rag_config(path)


def model_tag(cfg: dict, key: str | None = None) -> str:
    """The Ollama tag for a key of llm.yaml `models` (default: the configured `model`)."""
    key = key or cfg["model"]
    if key not in cfg["models"]:
        raise OllamaError("UNKNOWN_MODEL_KEY")
    return cfg["models"][key]["tag"]


def is_enabled(cfg: dict, request_mode: str) -> bool:
    """The model is used only when BOTH the operator (llm.yaml provider) and the request (mode) say ollama."""
    return cfg["provider"] == "ollama" and request_mode == "ollama"


def request_body(prompt: str, cfg: dict, tag: str | None = None) -> dict:
    body: dict[str, Any] = {
        "model": tag or model_tag(cfg), "prompt": prompt, "stream": False,
        "format": AnswerDraftV1.model_json_schema(),
        "options": {"temperature": cfg["temperature"], "num_ctx": cfg["num_ctx"]},
        "keep_alive": cfg["keep_alive"],
    }
    if cfg.get("think") is not None:
        body["think"] = cfg["think"]
    return body


def post_generate(body: dict, cfg: dict) -> dict:
    """POST to /api/generate; the whole parsed reply. Raises OllamaError(code) on anything that goes wrong."""
    req = urllib.request.Request(f"{cfg['ollama_url'].rstrip('/')}/api/generate", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=float(cfg["timeout_seconds"])) as r:
            raw = r.read()
    except TimeoutError:
        raise OllamaError("TIMEOUT") from None
    except urllib.error.HTTPError:
        raise OllamaError("HTTP_ERROR") from None
    except urllib.error.URLError as e:
        raise OllamaError("TIMEOUT" if isinstance(e.reason, TimeoutError) else "UNREACHABLE") from None
    except OSError:
        raise OllamaError("UNREACHABLE") from None
    try:
        out = json.loads(raw)
    except ValueError:
        raise OllamaError("BAD_REPLY") from None
    if not isinstance(out, dict) or not isinstance(out.get("response"), str):
        raise OllamaError("BAD_REPLY")
    return out


@dataclass
class ModelReply:
    """What came back from one call: the model's text (checked later by the output guards, diacausal/guards/output_guards.py) or the CODE
    of what went wrong in talking to Ollama. Never raises."""

    text: str | None = None
    code: str | None = None  # UNREACHABLE, TIMEOUT, HTTP_ERROR, BAD_REPLY, UNKNOWN_MODEL_KEY, UNEXPECTED_<Class>
    seconds: float = 0.0  # the model call only
    prompt_tokens: int | None = None
    eval_tokens: int | None = None


def request_draft(prompt: str, llm_cfg: dict, tag: str | None = None) -> ModelReply:
    """Ask the model once. The text it returns is NOT trusted: diacausal/llm/answer.py runs the seven output checks on it."""
    started = time.perf_counter()
    reply = ModelReply()
    try:
        out = post_generate(request_body(prompt, llm_cfg, tag), llm_cfg)
        reply.text, reply.prompt_tokens, reply.eval_tokens = out["response"], out.get("prompt_eval_count"), out.get("eval_count")
    except OllamaError as e:
        reply.code = e.code
    except Exception as e:  # noqa: BLE001 - anything unexpected is also a fallback; only the class name is kept
        reply.code = f"UNEXPECTED_{type(e).__name__}".upper()
    reply.seconds = time.perf_counter() - started
    return reply


def _post(url: str, body: dict, headers: dict, timeout: float = 60) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def call_ollama(prompt: str, cfg: dict) -> str:
    """The older free-text call (kept for explain(..., caller=...) and its tests)."""
    out = _post(f"{cfg['ollama_host']}/api/generate",
                {"model": cfg["ollama_model"], "prompt": prompt, "stream": False, "options": {"temperature": 0}}, {}, 180)
    return out["response"]
