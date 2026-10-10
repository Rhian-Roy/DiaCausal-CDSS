"""Ollama provider: a small model running on this computer; nothing leaves the machine.

Two ways in:

  call_ollama(prompt, cfg)             the older free-text call (numbered [n] citations), kept for the `explain(..., caller=...)` path
  explain_structured(...)              P21: the structured call below, with the template as the fallback for EVERYTHING

The structured call: POST {ollama_url}/api/generate with
    model    the tag of llm.yaml `models.<model>.tag` (never typed anywhere else)
    format   the JSON schema of AnswerDraftV1 (Ollama constrains the reply to it: docs.ollama.com/api/generate, "format")
    options  {"temperature": 0, "num_ctx": 4096}
    stream   false      keep_alive   "10m"      think   only if llm.yaml sets it
and a timeout of `timeout_seconds` (60). With stream false the reply arrives all at once, so that is in effect the whole answer; a
COLD model load can exceed it (then the question is answered by the template; keep_alive keeps the model loaded afterwards).

ANY error, timeout, bad HTTP status, invalid JSON, a draft that is not a valid AnswerDraftV1, or one whose claims fail the citation
check falls back to providers/template.py. The reply says so ("note", and "fallback": a short CODE). Only the exception class and the
code are ever logged or put in the reply, never the model's text, the prompt or the question.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from diacausal.api.schemas import AnswerDraftV1
from diacausal.config import load_rag_config
from diacausal.llm.draft import numbers_match, to_items
from diacausal.llm.providers.template import _reply, template

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


def parse_draft(text: str) -> AnswerDraftV1:
    """The model's text as an AnswerDraftV1 (OllamaError INVALID_JSON or SCHEMA_INVALID otherwise)."""
    try:
        data = json.loads(text)
    except ValueError:
        raise OllamaError("INVALID_JSON") from None
    try:
        return AnswerDraftV1.model_validate(data)
    except ValidationError:
        raise OllamaError("SCHEMA_INVALID") from None


def generate_draft(prompt: str, cfg: dict, tag: str | None = None) -> tuple[AnswerDraftV1, dict]:
    """(the validated draft, the Ollama reply with its timing and token counts)."""
    out = post_generate(request_body(prompt, cfg, tag), cfg)
    return parse_draft(out["response"]), out


@dataclass
class Attempt:
    """One try at a structured answer: what came back, how long the model call took, and the reason it cannot be used (if any)."""

    draft: AnswerDraftV1 | None = None
    items: list[dict] = field(default_factory=list)
    code: str | None = None  # None = usable; else a short CODE (TIMEOUT, UNREACHABLE, HTTP_ERROR, INVALID_JSON, SCHEMA_INVALID, CITATION_CHECK, ...)
    schema_valid: bool = False  # the reply was valid JSON that parsed as an AnswerDraftV1
    seconds: float = 0.0  # the model call only (not the template that may follow)
    prompt_tokens: int | None = None
    eval_tokens: int | None = None


def attempt(evidence: dict, prompt: str, cfg: dict, llm_cfg: dict, tag: str | None = None,
            number_sources: list[str] | None = None) -> Attempt:
    """Ask the model once and check the answer. Never raises: every problem is a `code`. With `number_sources` (the causal output and
    the drivers, as text) every number the draft writes must be in them or be a page or version of a passage it cites (plan 8.10 check
    3), else the code is NUMBER_MISMATCH: a model can never put a number on the card that the causal output does not contain."""
    result, started = Attempt(), time.perf_counter()
    try:
        draft, raw = generate_draft(prompt, llm_cfg, tag)
        result.draft, result.schema_valid = draft, True
        result.prompt_tokens, result.eval_tokens = raw.get("prompt_eval_count"), raw.get("eval_count")
        result.seconds = time.perf_counter() - started
        if not draft.insufficient:
            result.items, problems = to_items(draft, evidence["passages"], float(cfg["explain_min_support"]), int(llm_cfg["max_claims"]))
            if problems or not result.items:
                result.code = "CITATION_CHECK"
            elif number_sources is not None and not numbers_match(draft, number_sources, evidence["passages"])[0]:
                result.code = "NUMBER_MISMATCH"
    except OllamaError as e:
        result.code = e.code
    except Exception as e:  # noqa: BLE001 - anything unexpected is also a fallback; only the class name is kept
        result.code = f"UNEXPECTED_{type(e).__name__}".upper()
    result.seconds = result.seconds or time.perf_counter() - started
    return result


def explain_structured(question: str, evidence: dict, prompt: str, cfg: dict, llm_cfg: dict, idf: dict[str, float] | None = None,
                       tag: str | None = None, number_sources: list[str] | None = None) -> dict:
    """One question and its retrieved evidence -> a cited explanation written by the local model, or the template's
    explanation when anything at all goes wrong. The reply has the same shape as `explain()`'s, plus "fallback": None or a CODE."""
    tried = attempt(evidence, prompt, cfg, llm_cfg, tag, number_sources)
    if tried.code is None and tried.draft is not None and tried.draft.insufficient:
        return _reply(question, "ollama", "INSUFFICIENT_EVIDENCE", [], "the model found no answer in the passages") | {"fallback": None}
    if tried.code is None:
        return _reply(question, "ollama", "SUCCESS", tried.items) | {"fallback": None}
    return fall_back(question, evidence, cfg, idf, tried.code)


def fall_back(question: str, evidence: dict, cfg: dict, idf: dict[str, float] | None, code: str) -> dict:
    """The template's explanation, marked with the CODE that sent us here (also used when the prompt could not be built)."""
    fallback = template(question, evidence, cfg, idf)
    fallback["note"] = f"the local model could not be used ({code}); showing quoted sentences instead"
    return fallback | {"fallback": code}


def _post(url: str, body: dict, headers: dict, timeout: float = 60) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def call_ollama(prompt: str, cfg: dict) -> str:
    """The older free-text call (kept for explain(..., caller=...) and its tests)."""
    out = _post(f"{cfg['ollama_host']}/api/generate",
                {"model": cfg["ollama_model"], "prompt": prompt, "stream": False, "options": {"temperature": 0}}, {}, 180)
    return out["response"]
