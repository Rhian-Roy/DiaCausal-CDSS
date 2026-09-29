#!/usr/bin/env python3
"""Narrate the explainer page (docs/midsem/explainer/) with an offline voice.

Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

Reads the narration (captions) from page.html, speaks every sentence with Piper (offline text to
speech), and writes:
  narration/sNN.mp3   one file per scene (the page plays these as "Recorded narrator")
  page.html           the same page with the spoken text and each sentence's start/end time filled in
  index.html          page.html with its own <head>, so it also opens straight from the folder
  narration/full.wav  intro + every scene + outro, for the narrated video (scripts/record_explainer.cjs)

Needs ffmpeg, `pip install piper-tts` and a Piper voice (.onnx + .onnx.json), for example
en_US-lessac-medium from https://huggingface.co/rhasspy/piper-voices:

    python3 scripts/make_explainer.py --voice path/to/en_US-lessac-medium.onnx --piper path/to/piper
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "docs" / "midsem" / "explainer"
BLOCK = re.compile(r'(<script type="application/json" id="narration">\n)(.*?)(\n</script>)', re.S)

# Must match the page's own timeline (record mode) exactly.
INTRO, OUTRO = 3.0, 4.0
LEAD, GAP, TAIL = 0.35, 0.5, 1.1  # seconds: before the first sentence, between sentences, after the last

# Same spoken forms as SPEAK in page.html, so the recording and the browser voice say the same words.
SPEAK = [
    (r"HbA1c", "H B A 1 C"), (r"SGLT2i", "S G L T 2 inhibitor"), (r"SGLT2", "S G L T 2"),
    (r"DPP-4i", "D P P 4 inhibitor"), (r"DPP-4", "D P P 4"), (r"eGFR", "e G F R"), (r"AIPW", "A I P W"),
    (r"IPW", "I P W"), (r"DR-learner", "D R learner"), (r"HC3", "H C 3"), (r"BM25", "B M 25"),
    (r"TF-IDF", "T F I D F"), (r"\bRAG\b", "rag"), (r"\bWHO\b", "W H O"), (r"\bFDA\b", "F D A"),
    (r"NMB-2017", "N M B 2017"), (r"\bBMI\b", "B M I"), (r"\bR0(\d)\b", r"R zero \1"), (r"FastAPI", "Fast A P I"),
    (r"Argon2id", "Argon 2 I D"), (r"CAPTCHA", "captcha"), (r"(\d),(\d{3})", r"\1\2"), (r"−", "minus "), (r"%", " percent"),
]


def spoken(text: str) -> str:
    for pattern, replacement in SPEAK:
        text = re.sub(pattern, replacement, text)
    return text


def say(piper: str, voice: str, text: str, out: Path, length_scale: float) -> None:
    subprocess.run([piper, "-m", voice, "-f", str(out), "--length-scale", str(length_scale)],
                   input=text.encode(), check=True, capture_output=True)


def read_wav(path: Path) -> tuple[bytes, int, int, int]:
    with wave.open(str(path)) as w:
        return w.readframes(w.getnframes()), w.getframerate(), w.getsampwidth(), w.getnchannels()


def write_wav(path: Path, frames: bytes, rate: int, width: int, channels: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(frames)


def write_index(page: str) -> None:
    """page.html with its own <head>, so the folder opens without the artifact viewer."""
    head = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n</head>\n<body>\n')
    (DIR / "index.html").write_text(head + page + "\n</body>\n</html>\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--voice", help="Piper voice .onnx (its .onnx.json next to it)")
    ap.add_argument("--piper", default="piper", help="the piper command")
    ap.add_argument("--length-scale", type=float, default=1.06, help="above 1 speaks a little slower")
    ap.add_argument("--page-only", action="store_true", help="keep the narration; only rewrite index.html from page.html")
    args = ap.parse_args()
    if args.page_only:
        write_index((DIR / "page.html").read_text(encoding="utf-8"))
        print("wrote index.html")
        return
    if not args.voice:
        ap.error("--voice is required (or use --page-only)")

    page = (DIR / "page.html").read_text(encoding="utf-8")
    match = BLOCK.search(page)
    if not match:
        raise SystemExit("page.html has no narration block")
    scenes = json.loads(match.group(2))
    out_dir = DIR / "narration"
    out_dir.mkdir(exist_ok=True)

    full = bytearray()
    fmt = None
    with tempfile.TemporaryDirectory() as tmp:
        for i, scene in enumerate(scenes, start=1):
            frames = bytearray()
            for k, sentence in enumerate(scene["sentences"]):
                sentence["s"] = spoken(sentence["c"])
                part = Path(tmp) / f"{i}_{k}.wav"
                say(args.piper, args.voice, sentence["s"], part, args.length_scale)
                data, rate, width, channels = read_wav(part)
                fmt = fmt or (rate, width, channels)
                bytes_per_second = rate * width * channels
                silence = lambda seconds: bytes(int(seconds * rate) * width * channels)  # noqa: E731
                frames += silence(LEAD if k == 0 else GAP)
                sentence["t0"] = round(len(frames) / bytes_per_second, 3)
                frames += data
                sentence["t1"] = round(len(frames) / bytes_per_second, 3)
            rate, width, channels = fmt
            frames += bytes(int(TAIL * rate) * width * channels)
            scene["dur"] = round(len(frames) / (rate * width * channels), 3)
            wav = Path(tmp) / f"s{i:02d}.wav"
            write_wav(wav, bytes(frames), rate, width, channels)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ac", "1", "-b:a", "64k",
                            str(out_dir / f"s{i:02d}.mp3")], check=True)
            full += frames
            print(f"scene {i:2d}: {scene['dur']:6.2f} s  {scene['title']}")

    rate, width, channels = fmt
    pad = lambda seconds: bytes(int(seconds * rate) * width * channels)  # noqa: E731
    write_wav(out_dir / "full.wav", pad(INTRO) + bytes(full) + pad(OUTRO), rate, width, channels)

    body = "[\n" + ",\n".join(" " + json.dumps(s, ensure_ascii=False) for s in scenes) + "\n]"
    page = page[: match.start(2)] + body + page[match.end(2):]
    (DIR / "page.html").write_text(page, encoding="utf-8")
    write_index(page)
    total = INTRO + sum(s["dur"] for s in scenes) + OUTRO
    print(f"total {total / 60:.1f} min; wrote page.html, index.html, narration/s01-s{len(scenes):02d}.mp3, narration/full.wav")


if __name__ == "__main__":
    main()
