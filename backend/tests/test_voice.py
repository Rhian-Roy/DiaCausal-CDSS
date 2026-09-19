"""Voice: POST /api/v1/transcribe with faster-whisper, on 5 recorded clips (tests/voice_clips/).

The model runs for real (CPU, int8, about half a second per clip). Checks that do not
need speech use a fake transcriber so they stay fast.
"""

import io
import logging
import math
import os
import struct
import tempfile
import wave
from pathlib import Path

import av
import pytest

from app.voice import routes as voice_routes
from app.voice import transcriber

CLIPS = Path(__file__).parent / "voice_clips"
TRACE = "voice123"

EXPECTED = {
    "1-hba1c-metformin.wav": ["hba1c", "8.4", "metformin"],
    "2-egfr-empagliflozin.wav": ["egfr", "45", "empagliflozin", "10"],
    "3-sitagliptin.wav": ["sitagliptin", "100"],
    "4-fasting-glucose.wav": ["glucose", "180"],
    "5-gliclazide-dapagliflozin.wav": ["gliclazide", "dapagliflozin"],
}


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    voice_routes.reset_rate_limits()


def send(client, audio: bytes, content_type: str = "audio/wav", trace: str = TRACE):
    return client.post("/api/v1/transcribe", content=audio, headers={"Content-Type": content_type, "X-Trace-Id": trace})


def tone_wav(seconds: float) -> bytes:
    """A quiet 440 Hz tone as a 16 kHz WAV (no speech)."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16_000)
        out.writeframes(b"".join(
            struct.pack("<h", int(800 * math.sin(2 * math.pi * 440 * i / 16_000))) for i in range(int(seconds * 16_000))
        ))
    return buffer.getvalue()


def as_webm_opus(wav_bytes: bytes) -> bytes:
    """What Chrome's MediaRecorder sends: WebM with Opus audio."""
    source = av.open(io.BytesIO(wav_bytes))
    target_buffer = io.BytesIO()
    target = av.open(target_buffer, "w", format="webm")
    stream = target.add_stream("libopus", rate=48_000)
    resampler = av.AudioResampler(format="s16", layout="mono", rate=48_000)
    for frame in source.decode(audio=0):
        for resampled in resampler.resample(frame):
            for packet in stream.encode(resampled):
                target.mux(packet)
    for packet in stream.encode(None):
        target.mux(packet)
    target.close()
    return target_buffer.getvalue()


def words(text: str) -> str:
    return " ".join(text.lower().replace(",", " ").replace("?", " ").split())


# ── real speech ──────────────────────────────────────────────────────────────


def test_there_are_5_recorded_clips():
    assert sorted(p.name for p in CLIPS.glob("*.wav")) == sorted(EXPECTED)


@pytest.mark.parametrize("clip", sorted(EXPECTED))
def test_clip_is_transcribed(client, clip):
    reply = send(client, (CLIPS / clip).read_bytes())
    assert reply.status_code == 200, reply.text
    body = reply.json()
    for expected in EXPECTED[clip]:
        assert expected in words(body["transcript"]), body["transcript"]
    assert body["trace_id"] == TRACE and 1 < body["duration_seconds"] < 10


def test_drug_names_and_terms_are_spelled_the_standard_way():
    assert transcriber.tidy("EGFR45 and hba1c 8 on satagliptin") == "eGFR 45 and HbA1c 8 on sitagliptin"
    # Two drugs are both valid names: never "correct" one into the other.
    assert transcriber.tidy("glimepiride and gliclazide") == "glimepiride and gliclazide"


def test_chrome_webm_opus_recording_is_understood(client):
    webm = as_webm_opus((CLIPS / "3-sitagliptin.wav").read_bytes())
    reply = send(client, webm, "audio/webm;codecs=opus")
    assert reply.status_code == 200 and "sitagliptin" in words(reply.json()["transcript"])


def test_the_initial_prompt_lists_the_drugs_and_units():
    for term in ("metformin", "empagliflozin", "dapagliflozin", "sitagliptin", "vildagliptin",
                 "glimepiride", "gliclazide", "HbA1c", "eGFR", "mg/dL"):
        assert term in transcriber.INITIAL_PROMPT
    assert transcriber.COMPUTE_TYPE == "int8" and transcriber.MODEL_NAME in ("tiny", "base")


# ── limits and safety (fake transcriber: no speech needed) ──────────────────


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(transcriber, "transcribe", lambda samples: "HbA1c 8.4 on metformin SECRETWORD")


def test_signed_in_only(anon):
    reply = send(anon, tone_wav(1))
    assert reply.status_code == 401


def test_needs_the_csrf_token(client, fake):
    del client.headers["X-CSRF-Token"]
    assert send(client, tone_wav(1)).status_code == 403


def test_needs_a_trace_id(client, fake):
    reply = client.post("/api/v1/transcribe", content=tone_wav(1), headers={"Content-Type": "audio/wav"})
    assert reply.status_code == 422


def test_refuses_what_is_not_audio(client, fake):
    reply = send(client, b"hello", "text/plain")
    assert reply.status_code == 415 and reply.json()["error"] == "unsupported_audio"


def test_refuses_unreadable_audio(client, fake):
    reply = send(client, b"RIFF this is not really a wav file" * 10)
    assert reply.status_code == 422 and reply.json()["error"] == "audio_unreadable"


def test_refuses_more_than_2_mb(client, fake):
    reply = send(client, b"\0" * (2 * 1024 * 1024 + 1))
    assert reply.status_code == 413 and reply.json()["error"] == "audio_too_large"


def test_refuses_more_than_30_seconds(client, fake):
    reply = send(client, tone_wav(32))
    assert reply.status_code == 413 and reply.json()["error"] == "audio_too_long"


def test_30_seconds_is_fine(client, fake):
    assert send(client, tone_wav(30)).status_code == 200


def test_rate_limited_to_10_per_minute(client, fake):
    clip = tone_wav(0.5)
    assert all(send(client, clip).status_code == 200 for _ in range(10))
    reply = send(client, clip)
    assert reply.status_code == 429 and reply.headers["retry-after"] == "60"


def test_audio_is_deleted_right_after_decoding(client, fake, monkeypatch):
    seen: list[str] = []
    real_decode = transcriber.decode

    def spying_decode(path: str):
        seen.append(path)
        assert os.path.exists(path)  # the file exists while it is decoded ...
        return real_decode(path)

    monkeypatch.setattr(transcriber, "decode", spying_decode)
    assert send(client, tone_wav(1)).status_code == 200
    assert seen and not os.path.exists(seen[0])  # ... and is gone afterwards
    assert not list(Path(tempfile.gettempdir()).glob("diacausal-voice-*"))


def test_audio_is_deleted_even_when_unreadable(client, fake):
    send(client, b"RIFF garbage" * 20)
    assert not list(Path(tempfile.gettempdir()).glob("diacausal-voice-*"))


def test_log_has_trace_id_and_length_but_never_the_transcript(client, fake, caplog):
    caplog.set_level(logging.INFO, logger="diacausal")
    reply = send(client, tone_wav(2))
    assert "SECRETWORD" in reply.json()["transcript"]
    lines = {r.getMessage(): r.trace_id for r in caplog.records if r.name == "diacausal"}
    assert lines["transcribe: 2.0 s clip received"] == TRACE
    assert "SECRETWORD" not in caplog.text and "metformin" not in caplog.text


def test_audit_row_has_length_but_not_the_transcript(client, fake, db):
    from sqlalchemy import select

    from app.db.models import AuditLog

    send(client, tone_wav(2))
    row = db.scalar(select(AuditLog).where(AuditLog.event == "transcribe"))
    assert row.detail == "2.0 s" and row.client_trace_id == TRACE and "SECRETWORD" not in str(vars(row))


def test_transcript_is_only_returned_never_sent_to_chat(client, fake, db):
    from sqlalchemy import select

    from app.db.models import AuditLog

    send(client, tone_wav(1))
    assert db.scalar(select(AuditLog).where(AuditLog.event == "chat")) is None
