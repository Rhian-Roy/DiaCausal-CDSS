# Deploying DiaCausal

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

DiaCausal is submitted as two parts:

| Part | What it is | Where it runs | This file |
|---|---|---|---|
| **The public site** | the static website in `web/` (Patient Details, Investigate, Analysis, Guide, About), with Supabase sign-in | Netlify, at https://diacausal.netlify.app | **section 1** |
| **The engine API** | the FastAPI app `diacausal.api.main` (`/api/v1/ask`, `/api/v1/recommend`) | your own computer | section 2 |

The old chat app (`backend/` and `frontend/`) is **not** part of the submitted system. Its Docker guide is kept, unchanged, at
the end of this file: [Legacy chat app - not part of the submitted system](#legacy-chat-app---not-part-of-the-submitted-system).

---

## 1. The public site (diacausal.netlify.app)

### 1.1 What it costs, and the three rules

- The site is a folder of files. Netlify has **no build step** for it (`web/netlify.toml`: `command = ""`), so a deploy is an
  upload of a folder from your computer.
- The team is on Netlify's Free plan with **300 credits** per billing period (as the Netlify API reported on 11 Oct 2026). A **draft deploy is free**. A **production deploy costs 15 credits**.
  A failed deploy costs nothing.
- **Rule 1: draft first, production by hand only.** Every change goes to a free draft link first. You check it, then you deploy
  the same folder to production yourself.
- **Rule 2: check the credits before every deploy.** The Netlify command line cannot show the balance. Open
  https://app.netlify.com → your team → **Billing** (usage and credits) and look before you deploy.
- **Rule 3: GitHub never deploys.** The site is not connected to GitHub, so a push or a merged pull request deploys nothing.
  `web/netlify.toml` also says `ignore = "exit 0"`, which skips any Git-triggered build if the site were ever connected by
  mistake. `tests/test_ci_workflows.py` fails if a GitHub workflow mentions Netlify, a deploy hook, a deploy token or `--prod`.

### 1.2 One-time setup on your own computer

You need the Netlify command line (`netlify --version` should print a version; if not: `npm install -g netlify-cli`).

```bash
netlify login                     # a browser tab opens: click Authorize
netlify link --name diacausal     # run this from the repo root, once
netlify status                    # should say: Current project: diacausal
```

**The sign-in settings.** The site needs two values from Supabase: the project URL and the *publishable* key
(Supabase dashboard → Project Settings → API Keys). They are kept **in Netlify's settings, not in this repository**, so a
deploy can read them without anyone typing or seeing them. They are already set. If they ever need setting again, type
this **in your own terminal** (it reads the key without showing it on screen or saving it in your shell history):

```bash
netlify env:set SUPABASE_URL "https://<your-project-ref>.supabase.co"
read -rs KEY && netlify env:set SUPABASE_PUBLISHABLE_KEY "$KEY"; unset KEY    # paste the key, press Enter
netlify env:list                  # shows the two names; the values are hidden
```

Never paste the key into a chat, a pull request, an issue or a file in this repository. The publishable key is public
by design (every visitor's browser downloads it, and the database is protected by row-level security), but the project rule is
**no keys in this public repo**: the committed `web/config.json` says `"accounts": "off"`, `scripts/web_config.py` refuses
to write into `web/`, and `tests/web` fails if a key appears anywhere in the repository.

### 1.3 Before every deploy

```bash
git switch main && git pull                 # deploy only what is merged into main
python3 scripts/check_all.py                # must end with "ALL ... CHECKS PASSED"
```

If you changed the engine, the evidence or the guards, regenerate the website's data first (docs/WEBSITE.md, "Update the
website") and bump `VERSION` in `web/sw.js` so installed phones fetch the new files.

### 1.4 Make the deploy folder (a copy of `web/` with the sign-in settings)

```bash
rm -rf /tmp/diacausal-site && cp -R web /tmp/diacausal-site
SUPABASE_URL="$(netlify env:get SUPABASE_URL)" \
SUPABASE_PUBLISHABLE_KEY="$(netlify env:get SUPABASE_PUBLISHABLE_KEY)" \
  .venv/bin/python scripts/web_config.py /tmp/diacausal-site/config.json
```

The key goes only into the copy in `/tmp`, never into `web/`. Deploying from inside the copy makes Netlify read the copied
`netlify.toml`, which carries the security headers. Use the site ID instead of `--site diacausal` if the name is not found
(`cat .netlify/state.json` shows it).

### 1.5 Draft deploy (free)

1. Check the credits (rule 2).
2. Deploy the folder as a draft:
   ```bash
   (cd /tmp/diacausal-site && netlify deploy --site diacausal --dir . --message "draft of main <commit>")
   ```
   It prints a **Draft URL** like `https://<id>--diacausal.netlify.app`. Nothing changes on the real site.
3. Check the draft (section 1.7).

### 1.6 Production deploy (15 credits, by hand only)

Only after the draft passed every check in section 1.7:

1. Check the credits again (rule 2): you need at least 15.
2. Deploy **the same folder**:
   ```bash
   (cd /tmp/diacausal-site && netlify deploy --site diacausal --dir . --prod --message "production: main <commit>")
   ```
3. Repeat section 1.7 on https://diacausal.netlify.app.

### 1.7 Check the deploy

Open the link in a private window, so no old copy of the site is cached. When `docs/DEMO_SCRIPT.md` exists, go through its
screens. Until then, this list (the checks run on 11 Oct 2026):

| # | Check | Expected |
|---|---|---|
| 1 | Open the link | the sign-in page; the intended-use sentence under the header |
| 2 | Security headers: `curl -sI <link> \| grep -i content-security-policy` | a policy that starts `default-src 'self'` |
| 3 | Sign in with your email, password and 6-digit code | Patient Details opens |
| 4 | Open all five tabs | Patient Details, Investigate, Analysis, Guide, About each open |
| 5 | Patient Details → **1 · Typical patient** → Compare | three options compared; the card ends with "The clinician decides." |
| 6 | Tap a citation number on the answer | the evidence drawer opens with source, version, section, page, licence; Esc closes it |
| 7 | Type "Patient unconscious in OPD, which add-on?" in the message box | the red **Emergency** notice, nothing else |
| 8 | Investigate → **Metformin and kidney function** | passages from licence-cleared sources, each with source, version, section, page, licence |
| 9 | Analysis | the A–D table and three charts, labelled "Synthetic benchmark" |

### 1.8 If something is wrong

| You see | What to do |
|---|---|
| `Failed retrieving site data for site diacausal: Not Found` | use the site ID: `--site "$(python3 -c 'import json;print(json.load(open(".netlify/state.json"))["siteId"])')"` |
| The draft shows the old site | open it in a private window (the old copy is cached by the browser's offline store) |
| Sign-in says "Sign-in is off on this copy" | `config.json` was not written into the copy: redo section 1.4 |
| "Forgot password" does not finish | the reset needs your 6-digit code first ("Confirm it is you"); if you lost the authenticator app, ask the team's admin |
| A production deploy is broken | Netlify dashboard → **Deploys** → pick the previous good deploy → **Publish deploy**. Check Billing first: whether this costs credits is UNVERIFIED |

---

## 2. The engine API (`diacausal.api.main`) on your own computer

```bash
.venv/bin/uvicorn diacausal.api.main:app --port 8001     # http://localhost:8001/docs shows /api/v1/ask and /api/v1/recommend
```

It needs the repo-root `.venv` (CLAUDE.md, "Causal engine"). It sends nothing to the internet: no account service, no online
model. The same server also serves the website at `/`, with the same security headers as Netlify.

**On a clinic laptop**, use the start scripts instead (`scripts/start_clinic.bat` on Windows, `scripts/start_clinic.command` on
macOS). They listen on 127.0.0.1:8000 only, use a local Ollama model when it is running, and open the browser. The whole install,
offline after setup, is in [OFFLINE_INSTALL.md](OFFLINE_INSTALL.md).

---

## Legacy chat app - not part of the submitted system

The old chat app (`backend/`, `frontend/`, `Dockerfile`, `compose.yaml`) is kept for reference and is **not** part of what is
submitted. The guide below is unchanged from before 11 Oct 2026; its step numbers refer to its own steps.

### Running the legacy chat app on a real machine

One command starts the whole thing: the page and the API in one container, with HTTPS in
front of it. Works on a clean Windows, macOS or Linux machine with Docker Desktop.


**HTTPS is not optional.** Browsers refuse the microphone and refuse the session cookie on
anything but `https://` or `localhost`, so without it voice and sign-in simply stop working.


#### 1. Install Docker Desktop

https://www.docker.com/products/docker-desktop/ — install, start it, and wait until the
whale icon says "running". Check in a terminal:

```bash
docker --version
```

#### 2. Get the code and make a secret key

```bash
git clone https://github.com/Rhian-Roy/DiaCausal-CDSS.git
cd DiaCausal-CDSS
cp .env.example .env
```

Make a key and put it in `.env` as `DIACAUSAL_SECRET_KEY=`:

```bash
docker run --rm python:3.12-slim sh -c \
  "pip install -q cryptography && python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
```

That key encrypts every authenticator secret in the database. **Back it up somewhere safe
and never commit it.** If it is lost, every clinician must set up their authenticator app
again. If it is stolen *together with* a copy of the database, someone could generate
their 6-digit codes — so treat it like a password.

#### 3. Start it

```bash
docker compose up --build -d      # the first build takes a few minutes
docker compose ps                 # both services should say "Up", app "(healthy)"
```

Open **https://localhost:8443**. On a laptop the certificate is Caddy's own, so the browser
asks you to confirm once (that warning is expected here and *only* here — see step 6 for a
real certificate).

#### 4. Make the first admin, then the clinicians

```bash
docker compose exec app python ../scripts/create_admin.py your.id "Dr Your Name"
```

It asks for a password twice, hidden. Then sign in at https://localhost:8443 — the first
sign-in shows a QR code for Google Authenticator (SETUP.md step 5c has the phone steps).

Afterwards, an admin adds everyone else (each action needs that admin's own password and
current 6-digit code, and is written to the audit log):

```bash
docker compose exec app python ../scripts/admin.py --as your.id create-user dr.mehta "Dr Mehta"
docker compose exec app python ../scripts/admin.py --as your.id list
```

#### 5. Check it works

```bash
docker compose exec app python ../eval/run_vignettes.py    # 25 of 25 vignettes
docker compose logs -f app                                 # one line per stage, with trace IDs
```

Then by hand: sign in, ask a question, check the console lines, try the microphone, and
press **New patient**. `docs/TESTING.md` part 2 is the by-eye list.

#### 5b. Use it on your phone, on the same Wi-Fi (no internet needed)

Handy for showing the team, and the only way to try the **microphone** on a phone.

1. Find the Mac's Bonjour name: `scutil --get LocalHostName` → e.g. `Rhians-MacBook-Air`.
2. Add it to `.env` (keep `localhost` as well, it must come first):
   ```
   SITE_ADDRESS=localhost, Rhians-MacBook-Air.local
   ```
   Then `docker compose up -d proxy && docker compose restart proxy`.
3. On the phone, with Wi-Fi on the same network, open
   **https://Rhians-MacBook-Air.local:8443**

The certificate is Caddy's own, so the phone warns about it. To get past that — and the
microphone will **not** work until you do, because browsers refuse it on an untrusted
page — install the local authority on the phone:

```bash
docker compose cp proxy:/data/caddy/pki/authorities/local/root.crt ~/Desktop/DiaCausal-local-CA.crt
```

**iPhone:** AirDrop that file to the phone → Settings → *Profile Downloaded* → **Install**
→ then Settings → General → About → **Certificate Trust Settings** → turn on full trust
for "Caddy Local Authority". **Android:** Settings → Security → Encryption & credentials →
Install a certificate → CA certificate.

Only do this on phones you control; it tells that phone to trust certificates this Mac
issues. To undo it, delete the profile (iPhone) or the certificate (Android).

#### 6. A real address (for a clinic or a demo others can reach)

1. Point a DNS `A` record at the machine (e.g. `diacausal.example.org`).
2. Open ports **80** and **443** to it, and set them in `.env`:
   ```
   SITE_ADDRESS=diacausal.example.org
   HTTP_PORT=80
   HTTPS_PORT=443
   ```
3. `docker compose up -d`. Caddy gets a free Let's Encrypt certificate automatically and
   renews it. The browser warning from step 3 disappears.

Sizing: 2 CPUs and 4 GB of memory are enough (the speech-to-text model holds ~150 MB and
the rest is idle). Everything runs on that one machine: **no patient text, panel value or
recording is sent to any other company**, which is the reason the whole design is
self-hosted rather than serverless.

#### 7. Backups

The database (accounts, the audit log) is a Docker volume. Copy it out regularly:

```bash
docker compose exec app python -c "import shutil;shutil.copy('/data/diacausal.db','/data/backup.db')"
docker compose cp app:/data/backup.db ./diacausal-backup-$(date +%F).db
```

Keep the backup **and** `DIACAUSAL_SECRET_KEY` — one is useless without the other.
Restore by stopping the stack, copying the file back to `/data/diacausal.db`, and starting
it again. Migrations run automatically when the app starts.

#### 8. Updating

```bash
git pull
docker compose up --build -d
```

The database is upgraded automatically at start-up. Check `docker compose logs app` for the
line `clinical_guardrails: rules …` and for any `clinical rule NOT in use — …` warning.

#### Deploy checklist

Tick every line before a clinician uses it. (Checked on the 2026-09-20 build.)

- [x] `python3 scripts/check_all.py` ends with **ALL CHECKS PASSED** on the commit being deployed
- [x] `eval/run_vignettes.py` reports **25 of 25**
- [x] The image builds from a clean checkout and the container reports **healthy**
- [x] The page and the API are served from **one origin** (no CORS, no second port open)
- [x] HTTPS in front; `Strict-Transport-Security` is sent (production only)
- [x] Security headers present: CSP with `frame-ancestors 'none'`, `nosniff`,
      `Referrer-Policy: no-referrer`, `Permissions-Policy: microphone=(self)`
- [x] The API documentation page (`/docs`) is **off** in production
- [x] A request body over 4 MB is refused before it is read
- [x] The container runs as a **non-root** user, and only `/data` is writable
- [x] **No secret is baked into the image**: the key comes from `.env` at run time
- [x] The session cookie is `__Host-`, `Secure`, `HttpOnly`, `SameSite=Strict` over HTTPS
- [x] Speech-to-text runs **inside** the container, offline (the model is in the image)
- [x] The database is on a volume, not in the image, and a backup has been taken once
- [ ] `DIACAUSAL_SECRET_KEY` is backed up somewhere other than this machine — *you must do this*
- [ ] The clinical rules table has been reviewed by the collaborating doctor
      (`docker compose exec app python -m app.clinical.check` must be clean) — *still a DRAFT*
- [ ] The foul-word lists have been reviewed by Member D — *still a DRAFT*

The last three are deliberately unticked: they are not things the software can do for you,
and **DiaCausal must not be used with real patients until they are done**.

#### When something is wrong

| You see | Likely cause | What to do |
|---|---|---|
| `DIACAUSAL_SECRET_KEY ... not a valid key` | `.env` missing or the key was pasted with a line break | Make a new key (step 2); it ends with `=` |
| Browser warns about the certificate on `localhost` | Caddy's own certificate, expected on a laptop | Accept once, or use a real name (step 6) |
| Sign-in bounces back to the sign-in page | The browser dropped the cookie — you are on plain `http` on a real host | Use HTTPS (step 6). On `localhost` this works in any browser |
| The microphone button does nothing | Not HTTPS, permission refused, or the certificate is not trusted on that device | Step 6 (or 5b on a phone), then allow the microphone in the address bar |
| The phone cannot find `…​.local` | The phone is on mobile data or a different Wi-Fi, or the network blocks Bonjour | Same Wi-Fi; otherwise use step 6 with a real name |
| `port is already allocated` | Something else uses 8080/8443 | Change `HTTP_PORT` / `HTTPS_PORT` in `.env` |
| The first recording is slow | The model is loading (about a second, once) | Nothing — later ones are fast |
| `clinical rule NOT in use — …` in the log | A rule has a TODO or no source | Expected until Member D fills it in; that rule never fires |
