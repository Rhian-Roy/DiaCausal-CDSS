# DiaCausal UI — handoff to Claude Code (screens v2, P06)

**For:** Member C (build and deploy). **Review:** Member D (safety wording), Member A (data the screens need).
**Source of truth:** the HTML files in `screens-v2/`. Every screen shares one `<style>` block; `tokens.css` is its `:root`.
**Check:** `python3 handoff/check_screens.py screens-v2` must exit 0. Run it again on the built pages.

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

---

## 1. What to build

A static PWA (the existing `web/` on Netlify with Supabase sign-in) with five tabs:

| Tab | Screens | Purpose |
|---|---|---|
| Patient Details | 13–21, 08–12 | Patient panel + conversation. Compares SGLT2 inhibitor, DPP-4 inhibitor and sulfonylurea for one patient. |
| Investigate | 22, 23 | Search the licence-cleared sources. Shows passages as stored. Never generates text. |
| Analysis | 24 | Synthetic benchmark: versions A–D, SHAP A vs C, LIME stability. |
| Guide | 25 | Intro, problem, solution, workflow, cautions, limitations, advantages. |
| About | 26 | Team, guide, department. |

Signed out: 01–03 (sign in, error, locked), 06 (authenticator setup), 07 (intended-use acknowledgement after the first sign-in).

**Does it fit before Fri 30 Oct with four part-time students?** The shell, the tabs and the static pages (Guide, About, sign-in) fit. Wiring Patient Details to the real engine output is the risky part. If time runs short, the smaller version is: ship 01–03, 07 and Patient Details (13–21), with Investigate, Guide and About as static pages, and Analysis showing the committed benchmark figures as images.

## 2. Layout and breakpoints

| Width | Layout |
|---|---|
| > 900 px (designed at 1280) | Header → intended-use line → tab bar → content. Patient Details: panel 360 px (`--panel-w`) left, conversation right with summary strip, thread and composer. Document tabs: one column, max 1040 px (`--content-w`). Evidence drawer: right side sheet 420 px (`--drawer-w`). |
| ≤ 900 px (designed at 390) | Tab bar moves to the bottom (`--tabbar-h` 64 px, icon + label). Panel collapses into the summary strip; tapping it opens the panel. Tables become one card per row. Drawer becomes a bottom sheet. |

The page is a full-height flex column (`100dvh`); only the thread, the panel and the document area scroll.

## 3. Tokens

Use `tokens.css`. Never write a hex value in a component.

| Group | Tokens |
|---|---|
| Ground and ink | `--ground` #F4F7F3, `--surface` #FFFFFF, `--ink` #12211A, `--ink-muted` #3C4A42, `--ink-placeholder` #6B776F |
| Brand | `--pine` #0E5049, `--pine-dark` #083B36 (hover, intended-use line), `--pine-fill` #E4EEEB, `--pine-hairline` #7FB8A8, `--on-pine` #FFFFFF, `--on-pine-muted` #CFE3DC |
| Lines | `--border-strong` #9FB0A6 (inputs), `--border-soft` #C8D4CB (cards), `--track` #DCE6DF, `--row-muted` #EAEFEB |
| Status | safe `--safe-ink/-line/-fill`, check `--check-*`, danger `--danger-*`, `--on-danger` |
| Type | `--font-body` Atkinson Hyperlegible, `--font-display` Source Serif 4 (headings only), `--font-mono` (authenticator key only) |
| Spacing | `--s1` 4 · `--s2` 8 · `--s3` 12 · `--s4` 16 · `--s5` 22 · `--s6` 24 · `--s7` 32 |
| Shape | `--r-control` 8, `--r-status` 10, `--r-card` 12, `--r-badge` 6, `--r-pill` 999; `--border-w` 2, `--border-w-strong` 3 |
| Sizes | `--h-input` 56, `--h-button` 58, `--h-touch` 52 |

Self-host the two fonts (both SIL OFL, e.g. from `@fontsource`) so the app does not depend on Google Fonts in a hospital network.

## 4. Components

| Component | Variants | Rules |
|---|---|---|
| Status card | Safe to consider · Check first · Do not use | Option name, icon + word, reason, then **Rule R-[ID]** and **Source [source], [version], § [section]** with a citation marker. Colour never carries the meaning alone. |
| Options table | 3 rows | Columns: option + status, HbA1c change at 6 months (estimate, 95% CI, dot-and-interval glyph on a −1.6 to 0 % axis), difference vs DPP-4i (95% CI + “interval excludes/includes 0”), hypoglycaemia risk (Low/Moderate/High, dots + word), weight change (95% CI), cost ₹/month, evidence level. |
| Removed option row | — | `--row-muted` ground, “Not estimated — removed by rule R-[ID] before estimation”. Never show an estimate for a removed option. |
| Finding box | leader · no clear difference | Leader only when the interval vs DPP-4i excludes 0, and only “on HbA1c”. Pine, never green. Otherwise “No clear difference in HbA1c for this patient”, then trade-offs first. |
| Evidence level | Moderate · Low · Insufficient | 3-bar meter + word. Never “High”. |
| Drivers | top 3 | “What drives this estimate”: label, HbA1c points with direction, 95% CI, diverging dot glyph (−0.10 to +0.10). Footnote: “They are not causes.” |
| Citation marker | 1, 2, 3 | `<button>` with `aria-label="Evidence n — open source"`; opens the drawer. |
| Evidence drawer | side sheet · bottom sheet | Source, version, section, page, licence, retrieved date and index version, passage verbatim, “Open in Investigate”, “Report a mismatch”. |
| Notices (in place of an answer) | identifier · out of scope · emergency · blocked | Emergency is the loudest: solid danger bar, 3 px border, no treatment content. |
| Patient panel | empty · filled · out of range · example | Units inside the field; Asian-Indian BMI category under BMI; yes/no and none/mild/severe as radio groups; “New patient” clears panel and conversation. |
| Composer | — | Placeholder “Ask about these three options for this patient”. Send button only. No microphone. Intended-use line underneath. |
| Header | signed in · signed out | Brand + user + Sign out. **No “Research prototype” badge.** Intended-use line directly under it. |

## 5. States and interactions

| Element | State | Behaviour |
|---|---|---|
| Any control | Focus | 3 px `--pine` outline, 2 px offset. Do not change the control's radius. |
| Primary button | Hover / disabled | `--pine-dark` / `--track` ground, `--ink-muted` text, `not-allowed`. |
| Sign in | Error | One message, “Those details did not match”, `role="alert"`; all three fields `aria-invalid`. Never say which field. |
| Sign in | Locked | Replace the form: “Too many attempts. Try again in N minutes or ask your administrator.” |
| Panel field | Out of range | 3 px danger border, `aria-invalid`, message below with `role="alert"`, e.g. “HbA1c 45%? Check the value — expected 4–20%.” Comparison blocked until fixed. |
| Answer | Loading | Six stages, each Waiting → Running → Done (icon + word). Order must match the backend. |
| Answer | Insufficient evidence | Replaces the table. Reasons, what to do instead, “The clinician decides.” |
| Session | 2 minutes left | Modal dialog, focus on “Stay signed in”. On timeout clear the on-screen conversation (the audit log keeps the record without patient values). |
| Tab | Current | `aria-current="page"`, pine text and a 4 px bar (bottom on desktop, top on the phone bar). |

## 6. Content rules (enforced by `check_screens.py`)

1. Never tell the doctor what to add. Headline is always “Three options compared for this patient”. Every answer ends with “The clinician decides.”
2. Only SGLT2 inhibitor, DPP-4 inhibitor and sulfonylurea. No GLP-1 receptor agonist.
3. Every estimate has a 95% interval.
4. Safety cards cite rule ID and source; the source list names only cited sources. No ADA Standards of Care.
5. No dose prompts, no dose in the patient strip, no microphone, no header badge.
6. The intended-use sentence appears at least twice on every screen.

## 7. Data each screen needs (Member A → Member C)

| Field | From | Notes |
|---|---|---|
| Per option: status, rule ID, reason, source/version/section | rules table | Deterministic; runs before estimation. |
| Per remaining option: HbA1c change, 95% CI | causal engine | Absent for removed options. |
| Difference vs DPP-4i, 95% CI | causal engine | Leader logic uses “CI excludes 0”. |
| Weight change, 95% CI | causal engine or cited table | |
| Hypoglycaemia risk category | cited structured table | Not generated by a language model. |
| Cost ₹/month min–max | cited price table | Placeholder until sourced. |
| Evidence level | engine | **Needs a written, cited rule** for Moderate vs Low. |
| Top 3 drivers with 95% CI | engine (bootstrap SHAP) | If intervals are not computed, drop the numbers. |
| Abstain flag + reason | engine | Drives screen 19. |
| Citations: source ID, version, section, page, licence, passage | retrieval index | Passage shown verbatim. |
| Engine version, params hash, rules hash | engine | About tab and citation 1. |

## 8. Open decisions

- Evidence-level rule (Members A, D).
- Bootstrap intervals for drivers (Member A).
- Real rule IDs and sources from `data/rules.csv` to replace R-[ID] and [SOURCE].
- Team emails for About.
- Loading-stage order must match the real pipeline (Members A, B).

## 9. Prompt for Claude Code (paste as one message; Member C)

```text
You are implementing the DiaCausal v2 screens in the existing static PWA in web/ (Netlify, Supabase sign-in).
Deadline for all work: Fri 30 Oct 2026. Plan first, show me the plan, wait for my OK, then build in small steps with a check after each.

Sources of truth (in this repo under design/screens-v2/):
- 01–03, 06–26 *.html: one screen each, responsive (1280 desktop, 390 phone). Copy structure and class names.
- handoff/tokens.css: the only colours, fonts, spacing and radii allowed.
- handoff/HANDOFF.md: layout, components, states, content rules, data fields.
- handoff/check_screens.py: run it on every built page; it must exit 0.

Rules you must keep:
1. Never tell the doctor which drug to add. Headline "Three options compared for this patient"; every answer ends "The clinician decides."
2. Only SGLT2 inhibitor, DPP-4 inhibitor, sulfonylurea. No GLP-1, no ADA, no doses, no microphone, no "Research prototype" badge.
3. Every estimate shows a 95% interval. Never invent numbers: if a field is missing from the engine output, show the placeholder and log it.
4. Safety rules run before estimation; a removed option shows "Not estimated", never an estimate.
5. Keep verbatim, under the header and in the footer: "Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use."
6. Do not use or copy DiaCausal-RAG-Core or kotaemon.
7. Self-host Atkinson Hyperlegible and Source Serif 4 (SIL OFL).

Order of work:
a) tokens.css + shell (header, intended-use line, five tabs, phone bottom bar) + sign-in 01–03, 06, 07.
b) Patient Details static: panel states 13–16, notices 09–12, session modal 08.
c) Answer card 17/21/19 and drawer 18 bound to the engine's JSON (list the exact fields you need first).
d) Investigate 22/23 bound to the retriever; Guide 25, About 26, Analysis 24 static.
After each step run check_screens.py and tell me what failed.
```

## 10. Status of every screen

| Screen | Status | What changed |
|---|---|---|
| 01-signin — Sign in | fixed in P05 | One form: email, password and 6-digit code. CAPTCHA removed. “Research prototype” badge removed; full sentence under the header and in the footer. |
| 02-signin-error — Sign in — details not matched | fixed in P05 | Same vague message, now also covers a wrong or expired code. All three fields marked invalid together, so none is singled out. |
| 03-signin-locked — Sign in — locked | fixed in P05 (shell only) | Copy unchanged. Header badge removed; intended-use line and footer added. |
| 04-signin-step2-code — Two-step code | retired in P05 | The 6-digit code moved into 01. No v2 file. |
| 05-signin-step2-code-error — Two-step code — rejected | retired in P05 | A wrong or expired code is now handled by 02's single message. No v2 file. |
| 06-mfa-setup — Set up authenticator | fixed in P05 | Copy now says email, password and code. Header badge removed; footer added. |
| 07-intended-use — How to use DiaCausal | fixed in P05 | Names the three options; adds “does not tell you which option to add” and “does not show doses”. Duplicate intended-use callout removed (line and footer carry it). |
| 08-session-ending — Session ending | fixed in P05 | Modal unchanged. Background is now the Patient Details tab: tab bar, strip without dose, composer without microphone. |
| 09-notice-identifier — Identifier removed | fixed in P05 (shell only) | Notice text unchanged. Tabs, header, strip and composer updated. |
| 10-notice-out-of-scope — Out of scope | fixed in P05 (shell only) | Notice text unchanged. Tabs, header, strip and composer updated. |
| 11-notice-emergency — Emergency | fixed in P05 (shell only) | Notice text unchanged. Tabs, header, strip and composer updated. |
| 12-notice-blocked — Cannot answer as written | fixed in P05 (shell only) | Notice text unchanged. Tabs, header, strip and composer updated. |
| 13-panel-empty — Patient details — empty | fixed in P05 (shell only) | Panel unchanged. Now the left column of the Patient Details tab; on a phone it stays open because nothing is filled in. |
| 14-panel-filled — Patient details — filled | fixed in P05 (shell only) | Panel unchanged. On a phone the summary strip is collapsed and opens into the panel. |
| 15-panel-out-of-range — Patient details — out of range | fixed in P05 (shell only) | Panel unchanged. Stays open on a phone so the error is visible. |
| 16-panel-example-data — Patient details — example data | fixed in P05 (shell only) | Panel unchanged. Strip collapsed on a phone. |
| 17-answer-options-compared — Three options compared | fixed in P05 | Headline “Three options compared for this patient”. Leader named on HbA1c only, because its interval vs DPP-4i excludes 0. Sulfonylurea removed by a rule shows “Not estimated”. Safety cards show rule ID and source. New Evidence level and “vs DPP-4i” columns. “What drives this estimate” with 95% CIs. GLP-1 and ADA removed. Ends “The clinician decides.” |
| 18-evidence-drawer — Evidence drawer | fixed in P05 | Adds page and licence; S01 WHO 2018 metadata; opens as a side sheet over 17 (bottom sheet on a phone). |
| 19-insufficient-evidence — Insufficient evidence | fixed in P05 | Calmer wording; reasons tied to the 95% interval; points to Investigate; ends “The clinician decides.” |
| 20-loading-stages — Working through it | fixed in P05 | Six stages reordered to the pipeline: input checks, safety rules, causal estimate, retrieval, writing, output checks. |
| 21-answer-no-clear-difference — No clear difference | new | Both intervals vs DPP-4i include 0, so no leader; trade-offs come first; sulfonylurea is “Check first”. |
| 22-investigate — Investigate | new | Search box, example searches, sources list, cited passages with source, version, section, page and licence. |
| 23-investigate-insufficient — Investigate — no passage | new | Insufficient-evidence state. No generated answer. |
| 24-analysis — Analysis | new | Versions A–D table, SHAP A vs C, LIME stability. Labelled synthetic benchmark, example values. |
| 25-guide — Guide | new | Intro, problem statement, solution, workflow, cautions, limitations, advantages. |
| 26-about — About | new | Four members with email placeholders, the guide, B.Tech Computer Engineering, FCRIT. |
| diacausal-login — Recommended login | fixed in P05 | Now generated from 01, so it is identical to it. |
| diacausal-chat — Recommended chat | fixed in P05 | Now generated from 17, so it is identical to it. |
| 00-preview — Preview gallery | new | Every screen at 1280 and 390 side by side. A viewing aid, not a screen. |
| Design canvas A, B, C — Three looks | superseded | Exploration only. Still contain GLP-1, ADA, single-drug headlines and microphones. Do not build from them. |
| Design canvas R-Login, R-Chat, R-Phone — Recommended (canvas) | superseded | Replaced by diacausal-login, diacausal-chat and 01–26. Same problems as the three looks. |
| screens/ 01–20 (P03–P04 copies) — First 20 screens | superseded | Replaced by screens-v2. Still carry the header badge, microphone, dose prompt and dose in the strip. |
