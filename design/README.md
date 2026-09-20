# Design references

Copied from `DiaCausal/Designs` (the "Recommended" look) so the repo is self-contained.

| File | What it is |
|---|---|
| `chat.html` | Chat screen, hand-written HTML/CSS. **Source of truth for colours, fonts, sizes.** |
| `login.html` | First sign-in sketch; `v1/01–08` below supersede it. |
| `chat-desktop.png`, `chat-phone.png`, `login-desktop.png` | Screenshots of the above. |
| `requirements-notes.jpeg` | The original whiteboard (site structure, tests, API rules). |

Open `chat.html` in a browser to see the target.

## `design/v1/` — every screen, and what builds it

Built screens are marked ✅; the rest are the next prompts in `docs/prompts/`.

| # | Screen | Built by |
|---|---|---|
| 01 | Sign in, step 1 of 2 | ✅ `frontend/src/features/auth/SignInPage.tsx` |
| 02 | Sign in, "Those details did not match" | ✅ same file (error alert + attempts left) |
| 03 | Sign in locked | ✅ same file (locked view) |
| 04 | Step 2 of 2, 6-digit code | ✅ `features/auth/CodePage.tsx` |
| 05 | "That code did not work" | ✅ same file |
| 06 | Set up your authenticator app (QR + key) | ✅ `features/auth/MfaSetupPage.tsx` |
| 07 | How to use DiaCausal (acknowledgement) | ✅ `features/auth/IntendedUsePage.tsx` |
| 08 | "Signed out in 2 minutes" | ✅ `features/auth/SessionTimer.tsx` |
| 09 | Identifier removed — not sent | ✅ `components/chat/GuardNotice.tsx` |
| 10 | Out of scope | ✅ same file (names the topic) |
| 11 | Emergency | ✅ same file (no treatment content) |
| 12 | Cannot answer as written | ✅ same file |
| 13 | Patient panel, empty | `docs/prompts/04-patient-panel.md` |
| 14 | Patient panel, filled | 04-patient-panel |
| 15 | Patient panel, value out of range | 04-patient-panel |
| 16 | Patient panel, "Example data" | 04-patient-panel |
| 17 | Answer: the options compared | `docs/prompts/08-answer-card.md` |
| 18 | Evidence drawer (citations) | 08-answer-card |
| 19 | Insufficient evidence (abstain) | 08-answer-card |
| 20 | Loading, stage by stage | 08-answer-card |

Shared pieces of the built screens live in `frontend/src/features/auth/ui.tsx`; the colours,
fonts and radii are tokens in `frontend/src/index.css`, copied from these files. Fonts come
from the local `@fontsource` packages, never the Google Fonts links in the HTML.
