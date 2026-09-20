# voice — microphone input (built)

The mic button in `src/components/chat/Composer.tsx`.

| File | Does |
|---|---|
| `useVoiceInput.ts` | press to record (`MediaRecorder`; microphone permission is asked for only on press), press again or 30 s to stop, sends the clip, hands back the text |
| `api.ts` | `POST /api/v1/transcribe` with the CSRF token and a trace ID |
| `HighlightNumbers.tsx` | shows the dictated text with every number marked |

**Rules:** never auto-send a transcript — it goes into the message box, and the doctor
presses Enter, so the usual guards and console lines still apply; show clearly while
recording and release the microphone when it stops.

Console: `[id] voice: 4.2 s recorded`, `[id] voice: transcript put in the message box (not sent)`.
Tests: `voice.test.tsx` (fake microphone). Backend: `backend/app/voice/README.md`.
