# The DiaCausal website — use it on any phone or laptop

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

**Live link: <https://diacausal.netlify.app>** (free, HTTPS, always on).

![QR code for the website](../web/icons/qr.png)

## Use it on your iPhone like an app

1. Open <https://diacausal.netlify.app> in **Safari**.
2. Tap **Share** (the square with an arrow) → **Add to Home Screen** → **Add**.
3. It now opens full-screen from its icon and **works without internet** after the first visit.

Android (Chrome): ⋮ menu → **Add to Home screen**. Laptops: just open the link. To share it,
send the link, show the QR code (About tab), or press **Share this website**.

## Pages

| Tab | Sign-in? | What it shows |
|---|---|---|
| Try it | approved account | Patient form (units, Asian-Indian BMI category), 3 preset patients, colour-coded option cards (red excluded, amber caution, grey insufficient evidence, pine estimate), a 95% range chart, fair comparisons, assumptions, the raw Causal Output JSON |
| Evidence | approved account | **The RAG part.** Ask a question; it shows the best passages of licence-cleared sources with citations and scores, or "insufficient evidence". How RAG works, and the licence table |
| Results | open | Benchmark numbers (bias, 95% coverage, refutation) and the five figures |
| Learn | open | "Every idea, explained simply" and "Results in plain English" |
| About | open | What it is and is not, privacy, accounts, Add to Home Screen steps, QR code, team |

## Accounts: sign up, sign in, approval

Anyone can ask for an account, but **the team's admin approves each one** before Try it and
Evidence open. The steps, in order (the same order as the chat app's designs 01–08):

1. **Create an account** (name, email, password of at least 12 characters, role: clinician,
   student or examiner, and a tick for the intended-use statement).
2. **Authenticator app (MFA):** scan a QR code with Google or Microsoft Authenticator and type the
   6-digit code. Every later sign-in asks for a fresh code.
3. **Waiting for approval** until the admin approves.
4. **Intended use:** "I have read and understood this" — once.
5. Signed out automatically after **15 minutes** without activity.

**Approving people (admin), from your phone:** sign in → tap your name (top right) → **Approve
accounts (admin)** → **Approve** or **Reject**. The admin must have entered their authenticator
code; the database checks this too.

**What is stored:** only name, email, role, approval date and the intended-use date, in Supabase
(project `diacausal`, Mumbai region). Patient details, questions and results **never leave the
device** — a test scans the account code to prove it never touches them.

**Honest limit:** sign-in decides who can *use* the app. The fitted model and the evidence index
are ordinary website files (they are also in the public GitHub repo), so this is access control
for an evaluation, not secrecy.

### Setting up accounts (done once — already done for diacausal.netlify.app)

| Step | Where | What |
|---|---|---|
| 1 | Supabase | Project `diacausal` (ap-south-1). Database: `supabase/migrations/*.sql` — the `profiles` table with row-level security (each person reads only their own row; nobody writes directly; `approve_user()` works only for an admin who entered their code) |
| 2 | Supabase dashboard → **Authentication → Sign In / Providers → Email** | Turn **off** "Confirm email". Admin approval is the check instead, and Supabase's free email service only reaches members of the Supabase organisation |
| 3 | Supabase dashboard → **Authentication → URL Configuration** | Site URL `https://diacausal.netlify.app` (the forgot-password link returns there) |
| 4 | Supabase SQL editor, after you sign up yourself | `update public.profiles set is_admin = true, approved = true, approved_at = now() where email = 'YOUR EMAIL';` |
| 5 | Deploy | `scripts/web_config.py` writes `config.json` (Supabase URL + publishable key) into the **deploy copy only** |

Forgot password: Supabase sends the reset email. Its free email service only delivers to
members of the Supabase organisation; for everyone else add your own SMTP (Supabase dashboard →
Authentication → Emails → SMTP settings, e.g. a Gmail app password) — or the admin can delete the
account so the person signs up again.

**No key in GitHub.** The committed `web/config.json` says `"accounts": "off"`. On a copy without
account settings (a clone, the tests) every page is open and an amber bar says "Local copy:
sign-in is switched off here". The publishable key is public by design (every visitor's browser
downloads it; the database is protected by row-level security), but the project rule is "no API
keys in this public repo", so `scripts/web_config.py` refuses to write into `web/`, and a test
fails if a key is ever committed.

## How it works (plain English)

- **Analogy:** training the engine is like writing a textbook; answering one patient only needs
  the few pages at the back. We ship those pages (`web/model.json`, a few hundred numbers) to
  the phone, and the phone does the last step itself.
- `python -m diacausal_engine.export_web` fits the same reference engine as the Streamlit demo
  and the API (synthetic cohort, n = 5000, seed 2026). It writes: the propensity model's
  coefficients, the DR-learner's formula and its 95%-interval covariance, the cohort's range,
  the rules from `data/rules.csv` (with sources) and the thresholds from `data/params.yaml`.
- `web/engine.js` repeats `recommend.py` step by step: check the input → **safety rules first**
  → cohort support → propensity (below 0.05 → "insufficient evidence") → estimate with a 95%
  interval → output check (no doses, every number has an interval).
- `python -m diacausal_rag.export_web` writes `web/evidence.json`: each passage's word counts
  (BM25), its TF-IDF vector and its citation. `web/evidence.js` repeats `diacausal_rag/retrieve.py`:
  BM25 + vector search → reciprocal rank fusion → best 5, or "insufficient evidence". Passages with
  dose text are withheld before export.
- **Today's evidence:** the FDA Drug Safety Communication on metformin and reduced kidney function
  (8 April 2016; source S08, US government work, licence confirmed by the team). WHO 2018 (S01)
  waits for Member B's licence check; the FDA saxagliptin/alogliptin communication is next.
- **Viva sentence:** "The website runs the exact same fitted causal model and the exact same
  evidence search in the browser; tests check them against Python on 155 patients and 40
  questions, so the phone and the server always agree."

## Update the website

```bash
.venv/bin/python -m diacausal_engine.export_web   # after an engine change: model.json, results, figures, docs
.venv/bin/python -m diacausal_rag.export_web      # after a corpus or RAG change: evidence.json
.venv/bin/python -m pytest tests/web -q            # 16 tests; fails if either file is stale
```

Then deploy a copy of `web/` with the account settings written in:

```bash
rm -rf /tmp/site && cp -r web /tmp/site
SUPABASE_URL=https://txdzvqcserowgcotpqgj.supabase.co SUPABASE_PUBLISHABLE_KEY=sb_publishable_... \
  .venv/bin/python scripts/web_config.py /tmp/site/config.json
npx netlify-cli deploy --dir /tmp/site --prod      # after netlify login; or drag /tmp/site onto app.netlify.com
```

The publishable key is in the Supabase dashboard → Project Settings → API Keys. Bump `VERSION`
in `web/sw.js` when files change so installed phones fetch the new copy.

## Files

`web/index.html`, `styles.css`, `app.js` (the page), `engine.js` (the engine), `evidence.js`
(the evidence search), `auth.js` (sign-in rules) and `account.js` (sign-in screens),
`model.json`, `evidence.json`, `results.json`, `config.json` (accounts off in git),
`sw.js` + `manifest.webmanifest` (offline, installable), `icons/`, `results/` (figures), `docs/`,
`vendor/` (`marked` and `@supabase/supabase-js`, MIT, licences kept), `netlify.toml` and
`vercel.json` (the same strict security headers: no inline script or style, no framing, no
referrer, and network calls only to this site and the Supabase project).

## Limits

- The full chat app (FastAPI, React, voice, its own accounts with CAPTCHA) needs a real server;
  see [HOSTING_CHAT_APP.md](HOSTING_CHAT_APP.md).
- Synthetic data only; the clinician decides; it never shows drug doses.
- Supabase's free projects pause after a week with no sign-ins; open the Supabase dashboard and
  press **Restore** if sign-in stops working after a long break.
- Netlify may inject its own preview toolbar script; our security policy blocks it, which shows
  harmless console messages. It can be turned off in the Netlify site settings.
- Vercel is also configured (`web/vercel.json`) but the project could not be created on that
  account (permission error), so Netlify hosts it.
