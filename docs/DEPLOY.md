# Running DiaCausal on a real machine

One command starts the whole thing: the page and the API in one container, with HTTPS in
front of it. Works on a clean Windows, macOS or Linux machine with Docker Desktop.

**HTTPS is not optional.** Browsers refuse the microphone and refuse the session cookie on
anything but `https://` or `localhost`, so without it voice and sign-in simply stop working.

---

## 1. Install Docker Desktop

https://www.docker.com/products/docker-desktop/ — install, start it, and wait until the
whale icon says "running". Check in a terminal:

```bash
docker --version
```

## 2. Get the code and make a secret key

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

## 3. Start it

```bash
docker compose up --build -d      # the first build takes a few minutes
docker compose ps                 # both services should say "Up", app "(healthy)"
```

Open **https://localhost:8443**. On a laptop the certificate is Caddy's own, so the browser
asks you to confirm once (that warning is expected here and *only* here — see step 6 for a
real certificate).

## 4. Make the first admin, then the clinicians

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

## 5. Check it works

```bash
docker compose exec app python ../eval/run_vignettes.py    # 25 of 25 vignettes
docker compose logs -f app                                 # one line per stage, with trace IDs
```

Then by hand: sign in, ask a question, check the console lines, try the microphone, and
press **New patient**. `docs/TESTING.md` part 2 is the by-eye list.

## 6. A real address (for a clinic or a demo others can reach)

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

## 7. Backups

The database (accounts, the audit log) is a Docker volume. Copy it out regularly:

```bash
docker compose exec app python -c "import shutil;shutil.copy('/data/diacausal.db','/data/backup.db')"
docker compose cp app:/data/backup.db ./diacausal-backup-$(date +%F).db
```

Keep the backup **and** `DIACAUSAL_SECRET_KEY` — one is useless without the other.
Restore by stopping the stack, copying the file back to `/data/diacausal.db`, and starting
it again. Migrations run automatically when the app starts.

## 8. Updating

```bash
git pull
docker compose up --build -d
```

The database is upgraded automatically at start-up. Check `docker compose logs app` for the
line `clinical_guardrails: rules …` and for any `clinical rule NOT in use — …` warning.

---

## Deploy checklist

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

## When something is wrong

| You see | Likely cause | What to do |
|---|---|---|
| `DIACAUSAL_SECRET_KEY ... not a valid key` | `.env` missing or the key was pasted with a line break | Make a new key (step 2); it ends with `=` |
| Browser warns about the certificate on `localhost` | Caddy's own certificate, expected on a laptop | Accept once, or use a real name (step 6) |
| Sign-in bounces back to the sign-in page | The browser dropped the cookie — you are on plain `http` on a real host | Use HTTPS (step 6). On `localhost` this works in any browser |
| The microphone button does nothing | Not HTTPS, or permission refused | Step 6, then allow the microphone in the address bar |
| `port is already allocated` | Something else uses 8080/8443 | Change `HTTP_PORT` / `HTTPS_PORT` in `.env` |
| The first recording is slow | The model is loading (about a second, once) | Nothing — later ones are fast |
| `clinical rule NOT in use — …` in the log | A rule has a TODO or no source | Expected until Member D fills it in; that rule never fires |
