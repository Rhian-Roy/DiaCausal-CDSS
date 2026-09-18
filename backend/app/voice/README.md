# voice — speech-to-text (not built yet)

**What goes here:** Python speech-to-text (STT) for the microphone button in the chat box.

**How it will connect**

1. The browser records a short clip and sends it to `POST /api/v1/transcribe`.
2. This module turns it into text (e.g. `faster-whisper`, running on our own server so
   audio never leaves the hospital network).
3. The text goes back **into the message box**, not straight into the chat: the clinician
   reads and corrects it, then presses Enter as usual. So every message still passes the
   same UI guards, backend guards and trace-ID logging as typed text.

**Rules:** do not keep audio after transcription; limit clip length and file size; log
the trace ID and clip duration, never the audio or the transcript.
