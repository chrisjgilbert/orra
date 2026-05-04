FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY app ./app
COPY wsgi.py ./

RUN useradd --create-home --uid 1000 orra \
 && mkdir -p /data/audio \
 && chown -R orra:orra /data /app

USER orra

ENV DB_PATH=/data/orra.sqlite3 \
    AUDIO_DIR=/data/audio \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

# Single sync worker, long timeout — TTS calls can take minutes.
CMD ["gunicorn", "-w", "1", "--threads", "4", "-t", "600", \
     "-b", "0.0.0.0:8000", "wsgi:app"]
