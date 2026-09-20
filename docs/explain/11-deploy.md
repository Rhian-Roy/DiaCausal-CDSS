# 11 — Deploying it, and why it is built this way

`docker compose up --build -d` gives a working website: the page and the API in one
container, Caddy in front for HTTPS, the database on a volume. Step-by-step instructions
are in [DEPLOY.md](../DEPLOY.md); this is *why*.

## One image, one origin

The Dockerfile has two stages. Node 24 builds the page; `python:3.12-slim` then serves
`frontend/dist` **and** `/api/...` from the same address (`backend/app/web.py`). Nothing
from Node ends up in the final image.

Serving both from one origin means:

- **no CORS at all** — there is no "other site" to allow, so there is no CORS
  configuration to get wrong;
- the `__Host-` session cookie works exactly as designed, because the page and the API
  are the same origin;
- one port, one certificate, one thing to deploy.

In development it is still two servers (Vite on 5173, FastAPI on 8000) because hot
reloading is worth it; Vite forwards `/api` so the page cannot tell the difference.

## Why HTTPS is not optional

Two browser rules decide this, and neither is negotiable:

1. `getUserMedia` — the microphone — is refused on anything except HTTPS or `localhost`.
   Without HTTPS the voice feature simply does not exist on a real host.
2. A `Secure` cookie is refused over plain http, and our session cookie is `Secure` and
   `__Host-` prefixed. Without HTTPS, sign-in cannot work at all on a real host.

So Caddy sits in front and gets a free Let's Encrypt certificate for a real name, or uses
its own local certificate for a laptop demo. The one exception is `http://localhost`,
where the app falls back to a development cookie so a teammate can work in any browser —
and it logs a warning every time it does.

## What is in the image, and what is not

| In | Why |
|---|---|
| The built page, the backend, the shared guard rules, the clinical rules | that is the app |
| The speech-to-text model (~145 MB) | so the container works offline and the first recording is fast |
| `scripts/` and `eval/` | so an evaluator can create an admin and run the 25 vignettes inside the container |

| Out | Why |
|---|---|
| `DIACAUSAL_SECRET_KEY` | a secret in an image is a secret in every copy of that image; it comes from `.env` at run time |
| The database | it belongs to the machine, not the image — a Docker volume at `/data` |
| `node_modules`, `.venv`, notebooks, PDFs, `.env` | `.dockerignore` keeps the build small and the secrets out |

The container runs as a **non-root** user (uid 10001) and can write only to `/data`. The
`app` service publishes no port of its own: the only way in is through the proxy.

## The headers the page is served with

Set once, in `backend/app/web.py`, so the app and the proxy cannot disagree:

| Header | Stops |
|---|---|
| `Content-Security-Policy` with `frame-ancestors 'none'` | another site framing DiaCausal (clickjacking), and the page loading code from anywhere else |
| `X-Content-Type-Options: nosniff` | a browser guessing that an upload is a script |
| `Referrer-Policy: no-referrer` | a trace ID or address leaking to another site |
| `Permissions-Policy: microphone=(self), camera=(), geolocation=()` | anything but our own page using the microphone |
| `Strict-Transport-Security` (production + HTTPS only) | a downgrade to http for a year |

The API documentation page is **off** in production: it is a development tool, and
`/docs`, `/redoc` and `/openapi.json` answer 404 there. A request body over 4 MB is
refused from its `Content-Length` before any of it is read.

## The evaluation pack

`eval/` holds 25 **synthetic** vignettes — every clinical guardrail rule, every guard, the
abstain paths and ordinary questions — plus `run_vignettes.py`, which runs them through the
real pipeline and writes a results table (25 of 25 on this build). Alongside them are the
**System Usability Scale** questionnaire and a **doctor feedback sheet** whose first
question is whether any answer was unsafe. No real patient data is in the folder, and none
may be put into it.

## Viva questions

**1. Why one container serving both the page and the API, instead of two?**
One origin removes CORS completely, makes the `__Host-` cookie straightforward, and leaves
one port and one certificate to manage. Two containers would mean a proxy rule, a CORS
policy and two ways for the cookie to go wrong — for a single-page app of this size the
split buys nothing.

**2. Why not a serverless host like Vercel or Netlify?**
The backend is a long-lived process holding a 145 MB speech-to-text model in memory, it
needs a writable disk for the SQLite database, and the audio must stay on our machine.
Serverless platforms give none of those: they stop idle processes, have no persistent
disk, and would mean sending recordings to somebody else's computer.

**3. Where do the secrets live?**
In `.env` on the deploying machine, read as environment variables at start-up — never in
the image, never in git (`.gitignore` covers `.env`, and `.dockerignore` keeps it out of
the build). The app refuses to start if the key is missing or malformed, with a message
saying how to make a new one.

**4. What happens to the database when you update?**
It is a volume, so it survives. Alembic migrations run automatically when the app starts,
so the tables come up to date with the code. Backups are a file copy of
`/data/diacausal.db`, and the backup is useless without `DIACAUSAL_SECRET_KEY` — which is
why the checklist says to store that key somewhere else.

**5. Is it ready for real patients?**
No, and the checklist in DEPLOY.md ends with three unticked lines that say why: the
clinical rules are still a draft until the collaborating doctor signs them off, the
foul-word lists still need Member D's review, and the secret key must be backed up off the
machine. The software cannot tick those for you, and every screen and every reply repeats
that this is a research prototype, not a medical device.
