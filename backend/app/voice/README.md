# voice — speech-to-text (built)

`POST /api/v1/transcribe`: a short recording in, text out, for the message box.
Why it is built this way, and viva questions:
[docs/explain/12-voice.md](../../../docs/explain/12-voice.md).

| File | Does |
|---|---|
| `transcriber.py` | loads faster-whisper (`base`, int8, CPU, pinned revision), the initial prompt with drug names, and the spelling tidy-up |
| `routes.py` | the endpoint: signed-in only, CSRF, ≤2 MB, ≤30 s, 10 per person per minute |

**Rules:** the audio file is deleted as soon as it is decoded; log and audit only the
trace ID and the clip length, never the audio or the transcript; the text goes back to the
browser and into the message box — the server never sends it to the chat itself.

The model (about 145 MB) is downloaded once by `scripts/setup.py`
(`python -c "from app.voice.transcriber import download; download()"`).
