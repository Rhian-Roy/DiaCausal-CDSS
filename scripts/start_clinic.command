#!/bin/bash
# DiaCausal on a clinic laptop (macOS). Double-click this file in Finder. docs/OFFLINE_INSTALL.md explains the one-time setup.
#
# It starts the local DiaCausal server on 127.0.0.1:8000 ONLY (this computer; nothing else on the network can reach it), serves the
# website from web/, and opens it in the browser. A local Ollama model writes the answers when Ollama is running and the model is
# pulled; otherwise the template does. The page says which. Close this window to stop DiaCausal.
#
# Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

cd "$(dirname "$0")/.." || exit 1
PY=".venv/bin/python"
URL="http://127.0.0.1:8000/"
if [ ! -x "$PY" ]; then
  echo "DiaCausal is not set up yet: .venv is missing. Follow docs/OFFLINE_INSTALL.md (step 3), then double-click this file again."
  read -r -p "Press Enter to close." _
  exit 1
fi
if curl -fsS --max-time 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
  echo "Ollama is running: the local model writes the answers (if its model is pulled; the page says)."
else
  echo "Ollama is not running: the template writes the answers. To use the model, start Ollama and reload the page."
fi
export DIACAUSAL_LLM_PROVIDER=ollama   # used only when Ollama answers; otherwise the template (diacausal/llm/providers/ollama.py)
echo "Starting DiaCausal on $URL (this computer only). The first start takes about a minute."
(
  for _ in $(seq 1 180); do
    if curl -fsS --max-time 2 "${URL}api/v1/health" >/dev/null 2>&1; then open "$URL"; exit 0; fi
    sleep 1
  done
  echo "DiaCausal did not start within 3 minutes: read the messages above."
) &
exec "$PY" -m uvicorn diacausal.api.main:app --host 127.0.0.1 --port 8000
