#!/usr/bin/env bash
set -euo pipefail

cd /app
export DJANGO_SETTINGS_MODULE=config.settings

DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR" "${DJANGO_MEDIA_ROOT:-$DATA_DIR/media}"

export DJANGO_DB_PATH="${DJANGO_DB_PATH:-$DATA_DIR/db.sqlite3}"
export DJANGO_MEDIA_ROOT="${DJANGO_MEDIA_ROOT:-$DATA_DIR/media}"
export DJANGO_SERVE_MEDIA="${DJANGO_SERVE_MEDIA:-1}"

HOST="${DAPHNE_HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

if [ -z "${DJANGO_SECRET_KEY:-}" ]; then
  echo "[gy-dashboard] HATA: DJANGO_SECRET_KEY tanımlı değil."
  echo "  Dokploy → Compose → Environment sekmesine ekleyin veya .env dosyasında ayarlayın."
  echo "  Örnek: openssl rand -base64 48"
  echo "  Secret içinde \$ varsa tek tırnak kullanın: DJANGO_SECRET_KEY='...'"
  exit 1
fi

echo "[gy-dashboard] kalıcı veri kontrolü..."
python manage.py guard_persistent_data --phase pre

echo "[gy-dashboard] migrate + collectstatic..."
python manage.py migrate --noinput
python manage.py guard_persistent_data --phase post
python manage.py collectstatic --noinput
python manage.py sync_permissions 2>/dev/null || true
python manage.py ensure_chat 2>/dev/null || true

if [ "${DJANGO_ENSURE_SUPERADMIN:-0}" = "1" ]; then
  python manage.py ensure_superadmin 2>/dev/null || true
fi

if [ "${DJANGO_WHATSAPP_BRIDGE_CAN_SPAWN:-0}" != "1" ] && [ -n "${WHATSAPP_BRIDGE_URL:-}" ]; then
  echo "[gy-dashboard] WhatsApp köprüsü bekleniyor (${WHATSAPP_BRIDGE_URL})..."
  python manage.py wait_whatsapp_bridge --timeout "${DJANGO_WHATSAPP_BRIDGE_WAIT_TIMEOUT:-120}" \
    || echo "[gy-dashboard] UYARI: köprü henüz hazır değil — whatsapp-bridge servisini kontrol edin."
fi

echo "[gy-dashboard] daphne ${HOST}:${PORT}"
exec daphne -b "$HOST" -p "$PORT" config.asgi:application
