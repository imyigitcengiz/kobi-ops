#!/usr/bin/env bash
# Coolify: ön planda Daphne — container hemen kapanmasın diye exec kullanılır.
set -euo pipefail

cd /app
export DJANGO_SETTINGS_MODULE=config.settings

DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR" "${DJANGO_MEDIA_ROOT:-$DATA_DIR/media}"

export DJANGO_DB_PATH="${DJANGO_DB_PATH:-$DATA_DIR/db.sqlite3}"
export DJANGO_MEDIA_ROOT="${DJANGO_MEDIA_ROOT:-$DATA_DIR/media}"

HOST="${DAPHNE_HOST:-0.0.0.0}"
PORT="${PORT:-${DAPHNE_PORT:-8000}}"

echo "[gy-dashboard] migrate + collectstatic..."
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py sync_permissions 2>/dev/null || true

if [ "${DJANGO_ENSURE_SUPERADMIN:-0}" = "1" ]; then
  python manage.py ensure_superadmin 2>/dev/null || true
fi

echo "[gy-dashboard] daphne ${HOST}:${PORT}"
exec daphne -b "$HOST" -p "$PORT" config.asgi:application
