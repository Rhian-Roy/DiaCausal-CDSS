@echo off
REM DiaCausal on a clinic laptop (Windows). Double-click this file. docs\OFFLINE_INSTALL.md explains the one-time setup.
REM
REM It starts the local DiaCausal server on 127.0.0.1:8000 ONLY (this computer; nothing else on the network can reach it), serves the
REM website from web\, and opens it in the browser. A local Ollama model writes the answers when Ollama is running and the model is
REM pulled; otherwise the template does. The page says which. Close this window to stop DiaCausal.
REM
REM Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

cd /d "%~dp0.."
set "PY=.venv\Scripts\python.exe"
set "URL=http://127.0.0.1:8000/"
if not exist "%PY%" (
  echo DiaCausal is not set up yet: .venv is missing. Follow docs\OFFLINE_INSTALL.md, step 3, then double-click this file again.
  pause
  exit /b 1
)
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:11434/api/version | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo Ollama is not running: the template writes the answers. To use the model, start Ollama and reload the page.
) else (
  echo Ollama is running: the local model writes the answers, if its model is pulled. The page says which.
)
set "DIACAUSAL_LLM_PROVIDER=ollama"
echo Starting DiaCausal on %URL% (this computer only). The first start takes about a minute.
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for ($i = 0; $i -lt 180; $i++) { try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:8000/api/v1/health | Out-Null; Start-Process http://127.0.0.1:8000/; exit 0 } catch { Start-Sleep -Seconds 1 } }"
"%PY%" -m uvicorn diacausal.api.main:app --host 127.0.0.1 --port 8000
