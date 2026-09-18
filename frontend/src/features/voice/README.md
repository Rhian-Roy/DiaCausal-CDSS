# voice — microphone input (not built yet)

**What goes here:** the logic behind the mic button in `src/components/chat/Composer.tsx`
(currently disabled).

**How it will connect:** press to record (browser `MediaRecorder`), press again to stop;
the clip goes to the backend (`backend/app/voice/README.md`), and the returned text is put
**into the message box** for the clinician to check. Nothing is sent to the chat until
they press Enter, so the usual guards and trace-ID console lines still apply.

**Rules:** ask for microphone permission only when the button is pressed; show clearly
while recording; never auto-send a transcript.
