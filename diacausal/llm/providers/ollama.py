"""Ollama provider: a small model running on this computer; nothing leaves the machine (split out of explain.py)."""

from __future__ import annotations

import json
import urllib.request


def _post(url: str, body: dict, headers: dict, timeout: float = 60) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def call_ollama(prompt: str, cfg: dict) -> str:
    out = _post(f"{cfg['ollama_host']}/api/generate",
                {"model": cfg["ollama_model"], "prompt": prompt, "stream": False, "options": {"temperature": 0}}, {}, 180)
    return out["response"]
