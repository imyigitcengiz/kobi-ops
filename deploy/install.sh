#!/usr/bin/env bash
# KobiOps — tek komut kurulum: .env üretir, docker compose başlatır
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FORCE=0
DOMAIN="${DOMAIN:-}"

usage() {
  cat <<'EOF'
Kullanım: ./deploy/install.sh [domain] [--force]

  domain   Opsiyonel. Örn: panel.firma.com (HTTPS/CSRF buna göre ayarlanır)
  --force  Var olan .env dosyasının üzerine yazar

Ortam: DOMAIN=panel.firma.com ./deploy/install.sh

Örnek (sadece IP — domain yazmadan):
  git clone https://github.com/imyigitcengiz/kobi-ops.git /opt/kobi-ops
  cd /opt/kobi-ops && ./deploy/install.sh
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    -f|--force) FORCE=1; shift ;;
    *) DOMAIN="$1"; shift ;;
  esac
done

gen_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 48 | tr -d '\n/+=' | head -c 64
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c "import secrets; print(secrets.token_urlsafe(48))"
  else
    echo "Hata: openssl veya python3 gerekli (anahtar üretimi)." >&2
    exit 1
  fi
}

detect_ip() {
  local ip=""
  if command -v hostname >/dev/null 2>&1; then
    ip="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
  fi
  if [[ -z "$ip" ]] && command -v ip >/dev/null 2>&1; then
    ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") print $(i+1)}' || true)"
  fi
  if [[ -z "$ip" ]] && command -v curl >/dev/null 2>&1; then
    ip="$(curl -4fsS --max-time 4 https://api.ipify.org 2>/dev/null || true)"
  fi
  echo "${ip:-127.0.0.1}"
}

is_ipv4() {
  [[ "$1" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]
}

if [[ -f .env && "$FORCE" -ne 1 ]]; then
  echo ".env zaten var. Üzerine yazmak için: ./deploy/install.sh --force"
  echo "Sadece yeniden build: docker compose up -d --build"
  exit 0
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker yok. Kurulum: curl -fsSL https://get.docker.com | sh"
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose plugin gerekli."
  exit 1
fi

IP="$(detect_ip)"
SECRET="$(gen_secret)"

HOSTS="localhost,127.0.0.1,${IP}"
CSRF="http://127.0.0.1:8000,http://localhost:8000,http://${IP}:8000"
SECURE_SSL=0

if [[ -n "$DOMAIN" ]]; then
  DOMAIN="${DOMAIN#https://}"
  DOMAIN="${DOMAIN#http://}"
  DOMAIN="${DOMAIN%%/*}"
  DOMAIN="${DOMAIN%%:*}"
  if ! is_ipv4 "$DOMAIN"; then
    HOSTS="${HOSTS},${DOMAIN}"
    # sslip.io / traefik.me: sadece HTTP (Dokploy uyarısı)
    if [[ "$DOMAIN" == *.sslip.io ]] || [[ "$DOMAIN" == *.traefik.me ]]; then
      CSRF="${CSRF},http://${DOMAIN}"
      SECURE_SSL=0
    else
      CSRF="${CSRF},https://${DOMAIN}"
      SECURE_SSL=1
    fi
  else
    HOSTS="${HOSTS},${DOMAIN}"
    CSRF="${CSRF},http://${DOMAIN}:8000"
  fi
fi

cat > .env <<EOF
# Otomatik üretildi: $(date -Is)
DJANGO_SECRET_KEY=${SECRET}
DJANGO_ALLOWED_HOSTS=${HOSTS}
DJANGO_CSRF_TRUSTED_ORIGINS=${CSRF}
DJANGO_SECURE_SSL=${SECURE_SSL}
DJANGO_DEBUG=0
DJANGO_ENSURE_SUPERADMIN=1

WHATSAPP_BRIDGE_URL=http://whatsapp-bridge:3939
DJANGO_WHATSAPP_BRIDGE_CAN_SPAWN=0
DJANGO_WHATSAPP_BRIDGE_AUTO_START=0

MEDIA_COMPRESS_ENABLED=1
EOF

chmod 600 .env 2>/dev/null || true

echo "=== KobiOps kurulum ==="
echo "  .env yazıldı (DJANGO_SECRET_KEY otomatik)"
echo "  ALLOWED_HOSTS: ${HOSTS}"
echo "  CSRF: ${CSRF}"
echo ""
echo "Docker build + başlatılıyor (ilk sefer 5–15 dk sürebilir)..."
docker compose up -d --build

echo ""
echo "=== Hazır ==="
if [[ -n "$DOMAIN" ]] && ! is_ipv4 "$DOMAIN"; then
  if [[ "$DOMAIN" == *.sslip.io ]] || [[ "$DOMAIN" == *.traefik.me ]]; then
    echo "  Panel: http://${DOMAIN}/giris/"
  else
    echo "  Panel: https://${DOMAIN}/giris/"
  fi
else
  echo "  Panel: http://${IP}:8000/giris/"
fi
echo "  İlk giriş: admin / admin"
echo "  Sonra .env içinde DJANGO_ENSURE_SUPERADMIN=0 yapıp: docker compose up -d"
echo ""
