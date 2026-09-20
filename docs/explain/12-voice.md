# 12 — Voice input (speech to text)

Whiteboard: *"python - stt"*. A doctor presses the microphone in the message box, speaks,
presses it again; the words appear **in the box**, never straight into the chat.

```
mic pressed ─► browser records (MediaRecorder, max 30 s)
            ─► POST /api/v1/transcribe (signed in, CSRF, ≤2 MB)
            ─► faster-whisper on OUR server ─► text back
            ─► text put in the message box, numbers marked
            ─► doctor checks, presses Enter ─► the usual guards run
```

## Why it is built this way

| Decision | Reason |
|---|---|
| **faster-whisper** on our own computer, not a cloud service | A recorded question can contain patient details. Nothing leaves the machine, so there is no third-party processor to add to the ethics application. |
| Model **base**, `int8`, CPU | About 145 MB, half a second per clip on this laptop. `tiny` misheard drug names more often; `small` was slower with no clear gain for our sentences. |
| Pinned model **revision** | Everyone transcribes with exactly the same files (`transcriber.py`: `MODEL_REVISION`). |
| An **initial prompt** naming the drugs and units | Whisper uses it as context. Written as sentences, not a bare list: with a list it heard "gliclazide" as **"glimepiride"** — a different drug. |
| A small **tidy-up** afterwards | "satagliptin" → sitagliptin (only when exactly one drug on our list is within 2 letters), "EGFR45" → "eGFR 45". Never one real drug name into another. |
| The text goes **into the box** | Speech-to-text makes mistakes, and this is a clinical tool. The doctor reads it, fixes it, and only then presses Enter — so every message still passes the guards, the backend guard and the trace-ID logging, exactly like typed text. |
| **Numbers marked** under the box | Doses and lab values are where a mistake matters most ("50" vs "15"). They are highlighted for a last look before sending. |
| Audio **deleted at once** | The file exists only while it is decoded, then it is removed — before transcription even starts. The log and the audit row get the trace ID and the clip length, never the audio or the transcript. |
| Limits: 30 s, 2 MB, 10 per minute per person | Whisper is slow on long audio; the limits keep one person (or a broken page) from tying up the server. |

## What runs where

| Piece | File |
|---|---|
| Model, prompt, tidy-up | `backend/app/voice/transcriber.py` |
| Endpoint, limits, temp file, audit | `backend/app/voice/routes.py` |
| Recording, timer, permission | `frontend/src/features/voice/useVoiceInput.ts` |
| Sending the clip | `frontend/src/features/voice/api.ts` |
| Marking the numbers | `frontend/src/features/voice/HighlightNumbers.tsx` |
| The button and the indicator | `frontend/src/components/chat/Composer.tsx` |

Console (one trace ID per recording): `[id] voice: 4.2 s recorded`,
`[id] voice: transcript put in the message box (not sent)`.

## Tests

`backend/tests/test_voice.py` runs the **five recorded clips** in
`backend/tests/voice_clips/` (macOS voices, three of them Indian English) through the real
model and checks the drug names and numbers come back; it also checks a Chrome-style
WebM/Opus recording, the size, length and rate limits, that the audio file is deleted
(even when unreadable), and that neither log nor audit row contains the transcript.
`frontend/src/features/voice/voice.test.tsx` covers the button with a fake microphone.
`scripts/check_all.py` sends a real clip to the live server.

## Viva questions

**1. Why not use a cloud speech service?**
The clip may contain patient details. Sending it to another company would make them a data
processor, needing consent and a contract. faster-whisper runs on our own machine, so the
audio never leaves it.

**2. Why is the transcript not sent straight to the chat?**
Because speech-to-text is wrong sometimes, and in a clinical tool a wrong dose or drug
matters. Putting the text in the box keeps the doctor in control, and keeps every message
going through the same guards as typed text. Our own test showed why: one clip came back
with a different drug until the prompt was fixed.

**3. How does Whisper know words like "empagliflozin"?**
It is given an *initial prompt* — a sentence mentioning the drugs and units — as context
before it decodes. Afterwards a small tidy-up corrects a near-miss spelling to the one
drug on our list within two letters, and never between two real drug names.

**4. What happens to the audio?**
It is written to a private temporary file (the decoder needs a file), decoded to numbers,
and the file is deleted immediately — before transcription starts, and also when the audio
cannot be read. Only the trace ID and the clip length are recorded.

**5. What stops someone flooding the server with recordings?**
They must be signed in (session cookie + CSRF token), each clip is at most 2 MB and
30 seconds, and each person may send 10 clips a minute; after that the server answers
429 with `Retry-After: 60`.
