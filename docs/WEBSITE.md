# The DiaCausal website — use it on any phone or laptop

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

**Live link: <https://diacausal.netlify.app>** (free, HTTPS, always on; no sign-in).

![QR code for the website](../web/icons/qr.png)

## Use it on your iPhone like an app

1. Open <https://diacausal.netlify.app> in **Safari**.
2. Tap **Share** (the square with an arrow) → **Add to Home Screen** → **Add**.
3. It now opens full-screen from its icon and **works without internet** after the first visit.

Android (Chrome): ⋮ menu → **Add to Home screen**. Laptops: just open the link. To share it,
send the link, show the QR code (About tab), or press **Share this website**.

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
- **Privacy:** everything runs on the device. What you type is never sent or stored.
- **Viva sentence:** "The website runs the exact same fitted causal model in the browser; a test
  checks it against Python on 155 patients, so the phone and the server always agree."

## Pages

| Tab | What it shows |
|---|---|
| Try it | Patient form (units, Asian-Indian BMI category), 3 preset patients, colour-coded option cards (red excluded, amber caution, grey insufficient evidence, pine estimate), a 95% range chart, fair comparisons, assumptions, the raw Causal Output JSON |
| Results | Benchmark numbers (bias, 95% coverage, refutation) and the five figures |
| Learn | "Every idea, explained simply" and "Results in plain English" |
| About | What it is and is not, privacy, Add to Home Screen steps, QR code, team |

## Update the website after changing the engine

```bash
.venv/bin/python -m diacausal_engine.export_web   # rewrites web/model.json, results.json, figures, docs
.venv/bin/python -m pytest tests/web -q            # 9 tests: parity with Python, CSP, no doses, iPhone run
```

Commit, then redeploy the `web/` folder to Netlify (drag the folder onto the site's
**Deploys** page at app.netlify.com, or `npx netlify-cli deploy --dir web --prod` after
`netlify login`). `tests/web` fails if `model.json` is out of date, so a stale site cannot slip
through. Bump `VERSION` in `web/sw.js` when files change so phones fetch the new copy.

## Files

`web/index.html`, `styles.css`, `app.js` (the page), `engine.js` (the engine), `model.json`,
`results.json`, `sw.js` + `manifest.webmanifest` (offline, installable), `icons/`, `results/`
(figures), `docs/`, `vendor/marked.min.js` (MIT, licence kept), `netlify.toml` and `vercel.json`
(the same strict security headers: no inline script or style, no framing, no referrer).

## Limits

- It is the **causal engine only**. The sign-in chat app (FastAPI, React, voice, database) needs
  a real server; see [DEPLOY.md](DEPLOY.md).
- Synthetic data only; the clinician decides; it never shows drug doses.
- Netlify may inject its own preview toolbar script; our security policy blocks it, which shows
  harmless console messages. It can be turned off in the Netlify site settings.
- Vercel is also configured (`web/vercel.json`) but the project could not be created on that
  account (permission error), so Netlify hosts it.
