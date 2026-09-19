<!-- Owner: C | Model: Sonnet 5 | Effort: default | Branch: feat/voice | Start: only if ahead -->
# Prompt 11: Voice input — OPTIONAL, only if ahead by 12 Oct

**How to run:** in Claude Code type `/model`, choose **Sonnet 5**, set effort to **default**, then type:
`Do docs/prompts/11-voice.md exactly. First create and switch to the branch feat/voice from an up-to-date main.`

---
Read CLAUDE.md, backend/app/voice/README.md and frontend/src/features/voice/README.md. Time-box: 1.5 days; if not done, stop and leave the mic disabled. Plan first and wait for my OK.
1. Browser records with MediaRecorder (ask for mic permission only on press; clear recording indicator; max 30 s).
2. POST /api/v1/transcribe (signed-in only, rate-limited, size limit) -> faster-whisper (tiny or base, int8, pinned) on our server, with an initial prompt listing drug names and units (metformin, empagliflozin, dapagliflozin, sitagliptin, vildagliptin, glimepiride, gliclazide, HbA1c, eGFR, mg/dL).
3. Transcript goes INTO the message box, never auto-sent; numbers highlighted for the doctor to confirm; the usual guards run when they press Enter.
4. Audio deleted right after transcription; log only trace ID and clip length.
5. Tests with 5 short recorded sample clips; update check_all and docs.
6. Write docs/explain/12-voice.md with 5 viva questions.

---
When you are completely finished (all tests green):
1. Run `python3 scripts/check_all.py` and show me the last line.
2. Commit, push this branch, and open a pull request to main (use `gh pr create`; if `gh` is not logged in, walk me through `gh auth login` step by step).
3. Give me the pull-request link.
4. Write a 5-line plain-English summary of what changed that I can paste into our team WhatsApp.
Do NOT merge the pull request — I will get it reviewed first.
