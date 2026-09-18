# docker — containers (not built yet)

Today you run the two parts directly (see `CLAUDE.md`). Docker will package them so the
evaluation site runs the same way on any machine.

**Planned files**

| File | Does |
|---|---|
| `backend.Dockerfile` | `python:3.12-slim`, installs `backend/requirements.txt`, runs uvicorn on :8000 |
| `frontend.Dockerfile` | builds `frontend/` with Node 24, serves `dist/` with nginx, which also forwards `/api` to the backend (the job Vite's proxy does in development) |
| `compose.yaml` | starts backend + frontend (+ PostgreSQL once `backend/app/db/` exists) |

**Rules:** no secrets baked into images (pass them as environment variables); run as a
non-root user; keep the backend reachable only through the frontend's `/api` path.
