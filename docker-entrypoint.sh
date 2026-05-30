#!/usr/bin/env bash
set -euo pipefail

cd /app
export DJANGO_SETTINGS_MODULE=config.settings

# Panel otomatik yapılandırma (Coolify / Dokploy / 1Panel)
if [[ -f /app/deploy/bootstrap-env.sh ]]; then
  # shellcheck source=/dev/null
  source /app/deploy/bootstrap-env.sh
fi

DATA_DIR="${DATA_DIR:-/data}"
mkdir -p "$DATA_DIR" "${DJANGO_MEDIA_ROOT:-$DATA_DIR/media}"

export DJANGO_DB_PATH="${DJANGO_DB_PATH:-$DATA_DIR/db.sqlite3}"
export DJANGO_MEDIA_ROOT="${DJANGO_MEDIA_ROOT:-$DATA_DIR/media}"
export DJANGO_SERVE_MEDIA="${DJANGO_SERVE_MEDIA:-1}"

# Coolify PORT=8000 enjekte eder (panel portu) — uygulama konteyneri her zaman 80 dinler
if [[ "${KOBIOPS_COMPOSE_STACK:-0}" == "1" ]]; then
  export PORT=80
fi

HOST="${DAPHNE_HOST:-0.0.0.0}"
PORT="${PORT:-80}"

if [ -z "${DJANGO_SECRET_KEY:-}" ]; then
  echo "[gy-dashboard] HATA: DJANGO_SECRET_KEY üretilemedi."
  echo "  Panel → Environment → DJANGO_SECRET_KEY ekleyin veya /data volume bağlı olduğundan emin olun."
  exit 1
fi

if [ -n "${DATA_DIR:-}" ] && [ ! -w "$DATA_DIR" ]; then
  echo "[gy-dashboard] HATA: ${DATA_DIR} yazılamıyor — Docker Compose volume (gy_data:/data) bağlı mı?"
  exit 1
fi

echo "[gy-dashboard] kalıcı veri kontrolü..."
python manage.py guard_persistent_data --phase pre --verbose

echo "[gy-dashboard] migrate + collectstatic..."
python manage.py migrate --noinput
python manage.py guard_persistent_data --phase post
python manage.py collectstatic --noinput
python manage.py sync_permissions 2>/dev/null || true
python manage.py ensure_chat 2>/dev/null || true

if [ "${DJANGO_ENSURE_SUPERADMIN:-0}" = "1" ]; then
  python manage.py ensure_superadmin --reset-password 2>/dev/null || true
else
  python manage.py ensure_superadmin 2>/dev/null || true
fi

if [ "${DJANGO_WHATSAPP_BRIDGE_WAIT_ON_START:-0}" = "1" ] && [ "${DJANGO_WHATSAPP_BRIDGE_CAN_SPAWN:-0}" != "1" ] && [ -n "${WHATSAPP_BRIDGE_URL:-}" ]; then
  echo "[gy-dashboard] WhatsApp köprüsü bekleniyor (${WHATSAPP_BRIDGE_URL})..."
  python manage.py wait_whatsapp_bridge --timeout "${DJANGO_WHATSAPP_BRIDGE_WAIT_TIMEOUT:-30}" \
    || echo "[gy-dashboard] UYARI: köprü henüz hazır değil — panel yine de başlıyor."
fi

echo "[gy-dashboard] daphne ${HOST}:${PORT}"
exec daphne -b "$HOST" -p "$PORT" config.asgi:application
