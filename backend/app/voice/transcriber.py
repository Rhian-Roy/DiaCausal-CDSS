"""faster-whisper, on the CPU, on our own server: audio never leaves the machine.

Model "base" (about 145 MB, downloaded once by scripts/setup.py into the Hugging Face
cache), int8 so it runs fast on an ordinary CPU. An initial prompt lists the drug names
and units doctors will say, so Whisper spells them correctly.
"""

import os
import re
import threading

import numpy as np

# Hugging Face's newer "Xet" downloader stalls on some networks; plain HTTPS works everywhere.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

MODEL_NAME = "base"
# The exact model files (Hugging Face repo Systran/faster-whisper-base), so every
# machine transcribes the same way.
MODEL_REVISION = "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66"
COMPUTE_TYPE = "int8"
SAMPLE_RATE = 16_000

# Written as sentences: Whisper follows a prompt that reads like speech better than a bare
# list (with a list it heard "gliclazide" as "glimepiride" in tests/voice_clips/5-…).
INITIAL_PROMPT = (
    "The patient takes metformin. Options: empagliflozin, dapagliflozin, sitagliptin, "
    "vildagliptin, glimepiride, gliclazide. Check HbA1c and eGFR in mg/dL."
)

DRUGS = ("metformin", "empagliflozin", "dapagliflozin", "sitagliptin", "vildagliptin", "glimepiride", "gliclazide")
TERMS = {"hba1c": "HbA1c", "egfr": "eGFR"}
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")


def _distance(a: str, b: str) -> int:
    """Levenshtein edit distance."""
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def _fix_word(match: re.Match) -> str:
    word = match.group()
    lower = word.lower()
    for term, spelled in TERMS.items():  # "EGFR45" -> "eGFR 45"
        if lower.startswith(term):
            rest = word[len(term):]
            return spelled + (f" {rest}" if rest else "")
    if len(lower) >= 7 and lower not in DRUGS:  # "satagliptin" -> "sitagliptin", only if one drug is that close
        close = [drug for drug in DRUGS if _distance(lower, drug) <= 2]
        if len(close) == 1:
            return close[0]
    return word


def tidy(text: str) -> str:
    """Spell our drug names and lab terms the standard way. The doctor still checks everything."""
    return _WORD.sub(_fix_word, text)

_model = None
_lock = threading.Lock()


def download() -> str:
    """Fetch the model into the local cache (scripts/setup.py calls this)."""
    from faster_whisper import download_model

    return download_model(MODEL_NAME, revision=MODEL_REVISION)


def model():
    """Load the model once, on first use (a second or two)."""
    global _model
    with _lock:
        if _model is None:
            from faster_whisper import WhisperModel

            try:  # offline first: the copy scripts/setup.py downloaded
                _model = WhisperModel(MODEL_NAME, device="cpu", compute_type=COMPUTE_TYPE,
                                      revision=MODEL_REVISION, local_files_only=True)
            except Exception:  # noqa: BLE001 - not downloaded yet: fetch it once (about 145 MB)
                _model = WhisperModel(MODEL_NAME, device="cpu", compute_type=COMPUTE_TYPE, revision=MODEL_REVISION)
        return _model


def decode(path: str) -> np.ndarray:
    """Any browser format (WebM/Opus, MP4/AAC, Ogg, WAV) -> 16 kHz mono samples."""
    from faster_whisper import decode_audio

    return decode_audio(path, sampling_rate=SAMPLE_RATE)


def transcribe(samples: np.ndarray) -> str:
    segments, _info = model().transcribe(
        samples, language="en", beam_size=5, initial_prompt=INITIAL_PROMPT,
        condition_on_previous_text=False, vad_filter=False,
    )
    return tidy(" ".join(segment.text.strip() for segment in segments).strip())
