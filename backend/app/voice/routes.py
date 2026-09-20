"""POST /api/v1/transcribe — a short recording in, text out (for the message box).

- Signed-in clinicians only (same checks as chat, including the CSRF token).
- At most 2 MB and 30 seconds; at most 10 clips per person per minute.
- The audio is written to a private temporary file only because the decoder needs a
  file, and deleted as soon as it is decoded — before transcription even starts.
- The log gets the trace ID and the clip length. Never the audio, never the transcript.
- The text goes back INTO the message box; it is never sent to the chat by itself.
"""

import os
import tempfile
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth import audit
from app.auth.deps import AuthProblem, Signed, client_ip, require_clinician
from app.auth.schemas import AuthError
from app.db import get_db
from app.schemas import StrictModel
from app.settings import TRACE_ID_PATTERN, VOICE_MAX_BYTES, VOICE_MAX_SECONDS, VOICE_PER_USER_PER_MINUTE
from app.tracing import log, trace_context
from app.voice import transcriber

router = APIRouter(prefix="/api/v1", tags=["voice"])

ACCEPTED_TYPES = ("audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav", "audio/x-wav", "audio/aac")

_recent: dict[int, deque[float]] = defaultdict(deque)
_recent_lock = threading.Lock()


class TranscribeResponse(StrictModel):
    trace_id: str
    transcript: str
    duration_seconds: float


def _rate_limited(user_pk: int) -> bool:
    now = time.monotonic()
    with _recent_lock:
        times = _recent[user_pk]
        while times and now - times[0] > 60:
            times.popleft()
        if len(times) >= VOICE_PER_USER_PER_MINUTE:
            return True
        times.append(now)
        return False


def reset_rate_limits() -> None:
    with _recent_lock:
        _recent.clear()


@router.post(
    "/transcribe",
    responses={s: {"model": AuthError} for s in (401, 403, 413, 415, 422, 429)},
    openapi_extra={"requestBody": {"content": {t: {"schema": {"type": "string", "format": "binary"}}
                                               for t in ACCEPTED_TYPES}, "required": True}},
)
async def transcribe(
    request: Request,
    x_trace_id: str = Header(pattern=TRACE_ID_PATTERN, description="The browser's trace ID for this recording."),
    signed: Signed = Depends(require_clinician),
    db: Session = Depends(get_db),
) -> TranscribeResponse:
    """Speech to text. Send the raw recording as the body with its audio Content-Type."""
    with trace_context(x_trace_id):
        content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type not in ACCEPTED_TYPES:
            raise AuthProblem(415, "unsupported_audio", "Send the recording as audio (WebM, Ogg, MP4 or WAV).")
        if int(request.headers.get("content-length") or 0) > VOICE_MAX_BYTES:
            raise AuthProblem(413, "audio_too_large", "The recording is too large (the limit is 2 MB).")
        if _rate_limited(signed.user.id):
            raise AuthProblem(429, "slow_down", "Too many recordings. Wait a minute, then try again.",
                               retry_after_seconds=60)

        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > VOICE_MAX_BYTES:
                raise AuthProblem(413, "audio_too_large", "The recording is too large (the limit is 2 MB).")

        samples = await run_in_threadpool(_decode_and_delete, bytes(body))
        del body

        if samples is None or len(samples) == 0:
            log.warning("transcribe: the audio could not be read")
            raise AuthProblem(422, "audio_unreadable", "That recording could not be read. Try again.")
        seconds = round(len(samples) / transcriber.SAMPLE_RATE, 1)
        log.info("transcribe: %.1f s clip received", seconds)
        if seconds > VOICE_MAX_SECONDS + 0.5:
            raise AuthProblem(413, "audio_too_long", f"The recording is {seconds:.0f} seconds; the limit is {VOICE_MAX_SECONDS}.")

        started = time.monotonic()
        text = await run_in_threadpool(transcriber.transcribe, samples)
        del samples
        log.info("transcribe: done in %.1f s", time.monotonic() - started)
        audit.record(db, "transcribe", "done", user_id=signed.user.user_id, client_trace_id=x_trace_id,
                     detail=f"{seconds:.1f} s", ip=client_ip(request))
        return TranscribeResponse(trace_id=x_trace_id, transcript=text, duration_seconds=seconds)


def _decode_and_delete(audio: bytes):
    """Write to a private temp file (the decoder needs a file), decode, delete at once."""
    handle, path = tempfile.mkstemp(prefix="diacausal-voice-")
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(audio)
        return transcriber.decode(path)
    except Exception:  # noqa: BLE001 - any decoder error means "not audio we can read"
        return None
    finally:
        os.remove(path)  # the audio is gone before transcription starts
