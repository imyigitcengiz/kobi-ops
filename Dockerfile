# Coolify / production — repo kökündeki Dockerfile
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    DAPHNE_HOST=0.0.0.0 \
    PORT=8000 \
    DATA_DIR=/data \
    DJANGO_DB_PATH=/data/db.sqlite3 \
    DJANGO_MEDIA_ROOT=/data/media \
    DJANGO_SERVE_MEDIA=1 \
    DJANGO_WHATSAPP_BRIDGE_AUTO_START=0 \
    DJANGO_WHATSAPP_BRIDGE_CAN_SPAWN=0 \
    GY_REQUIRE_PERSISTENT_VOLUME=1 \
    DJANGO_DEBUG=0

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libjpeg62-turbo \
    zlib1g \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN sed -i 's/\r$//' docker-entrypoint.sh \
    && mkdir -p /data/media staticfiles \
    && chmod +x docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=8s --start-period=180s --retries=5 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz/' % os.environ.get('PORT', '8000'), timeout=5)" || exit 1

CMD ["./docker-entrypoint.sh"]
