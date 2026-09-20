# docker — the deployed container

One image serves the built page **and** the API from one origin; Caddy in front of it
provides HTTPS. Full instructions: [docs/DEPLOY.md](../docs/DEPLOY.md). Why it is built
this way, with viva questions: [docs/explain/11-deploy.md](../docs/explain/11-deploy.md).

| File | Does |
|---|---|
| `../Dockerfile` | stage 1 builds the page with Node 24; stage 2 is `python:3.12-slim` with the backend, the built page and the speech-to-text model, running as a non-root user |
| `../compose.yaml` | the `app` container (no port published) and the `proxy` container (Caddy, HTTPS), plus the volume the database lives on |
| `Caddyfile` | HTTPS and pass-through; `SITE_ADDRESS` is `localhost` or a real hostname |
| `../.dockerignore` | keeps `node_modules`, `.venv`, `.env`, databases, notebooks and PDFs out of the build |

```bash
cp .env.example .env     # then put a fresh DIACAUSAL_SECRET_KEY in it
docker compose up --build -d
docker compose exec app python ../scripts/create_admin.py your.id "Dr You"
```

**Rules:** no secret in an image (they come from `.env` at run time); the app container
publishes no port of its own, so the only way in is through the proxy; the database lives
on a volume; the container runs as a non-root user and can write only to `/data`.
