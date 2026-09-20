# DiaCausal in one image: the built page and the API from one origin.
#
#   docker compose up --build        (see compose.yaml and docs/DEPLOY.md)
#
# Stage 1 builds the page with Node; stage 2 is the Python server that serves it.
# Nothing from Node ends up in the final image, and no secret is baked into either.

# ── 1. build the page ────────────────────────────────────────────────────────
FROM node:24-bookworm-slim AS page

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci --no-audit --no-fund
# The guard rules are imported by the page at build time, so they must be here too.
COPY shared/ ./shared/
COPY frontend/ ./frontend/
RUN cd frontend && npm run build

# ── 2. the server ────────────────────────────────────────────────────────────
FROM python:3.12-slim AS app

# ffmpeg libraries are what PyAV needs to read a browser's WebM/Opus recording.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DIACAUSAL_ENV=production \
    DIACAUSAL_DATABASE_URL=sqlite:////data/diacausal.db \
    HF_HOME=/models \
    HF_HUB_DISABLE_XET=1

WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# The speech-to-text model (about 145 MB) is baked in, so the container works offline
# and the first recording does not wait for a download.
COPY backend/app/voice/transcriber.py /tmp/transcriber.py
RUN python -c "import sys; sys.path.insert(0, '/tmp'); import transcriber; print(transcriber.download())" \
 && rm /tmp/transcriber.py

COPY backend/ ./backend/
COPY shared/ ./shared/
COPY scripts/ ./scripts/
COPY --from=page /build/frontend/dist ./frontend/dist

# Run as nobody, and let that user write only to the data directory.
RUN useradd --system --create-home --uid 10001 diacausal \
 && mkdir -p /data /models \
 && chown -R diacausal:diacausal /data /models /app
USER diacausal

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

WORKDIR /app/backend
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
