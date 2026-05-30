#!/usr/bin/env bash
# Coolify / Dokploy / 1Panel — ortam değişkenlerini otomatik tamamlar.
# docker-entrypoint.sh kaynaklar; elle .env yazmadan deploy mümkün.
set -euo pipefail

_data_dir="${DATA_DIR:-/data}"
export DATA_DIR="$_data_dir"
mkdir -p "$_data_dir" 2>/dev/null || true

_strip_url_host() {
  local raw="${1:-}"
  raw="${raw#https://}"
  raw="${raw#http://}"
  raw="${raw%%/*}"
  raw="${raw%%:*}"
  echo "$raw"
}

_detect_fqdn() {
  local fqdn=""
  for key in SERVICE_FQDN_APP SERVICE_FQDN COOLIFY_FQDN DOMAIN APP_DOMAIN HOSTNAME; do
    fqdn="${!key:-}"
    if [[ -n "$fqdn" ]]; then
      _strip_url_host "$fqdn"
      return 0
    fi
  done
  for key in SERVICE_URL_APP SERVICE_URL DOKPLOY_DEPLOY_URL APP_URL WEBSITE_URL; do
    local url="${!key:-}"
    if [[ -n "$url" ]]; then
      _strip_url_host "$url"
      return 0
    fi
  done
  return 1
}

_detect_url() {
  local url=""
  for key in SERVICE_URL_APP SERVICE_URL DOKPLOY_DEPLOY_URL APP_URL WEBSITE_URL; do
    url="${!key:-}"
    if [[ -n "$url" ]]; then
      echo "$url"
      return 0
    fi
  done
  local fqdn
  fqdn="$(_detect_fqdn 2>/dev/null || true)"
  if [[ -n "$fqdn" ]]; then
    if [[ "$fqdn" == *".sslip.io"* || "$fqdn" == *".traefik.me"* ]]; then
      echo "http://${fqdn}"
    else
      echo "https://${fqdn}"
    fi
    return 0
  fi
  return 1
}

_detect_ip() {
  local ip=""
  if command -v hostname >/dev/null 2>&1; then
    ip="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
  fi
  if [[ -z "$ip" ]] && command -v ip >/dev/null 2>&1; then
    ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") print $(i+1)}' || true)"
  fi
  echo "${ip:-127.0.0.1}"
}

_gen_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 48 | tr -d '\n/+=' | head -c 64
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c "import secrets; print(secrets.token_urlsafe(48))"
  else
    date +%s | sha256sum | head -c 64
  fi
}

_is_http_only_host() {
  case "$1" in
    *.sslip.io|*.traefik.me) return 0 ;;
    *) return 1 ;;
  esac
}

# --- SECRET KEY (kalıcı: /data/.django_secret_key) ---
_secret_file="${_data_dir}/.django_secret_key"
if [[ -z "${DJANGO_SECRET_KEY:-}" ]]; then
  if [[ -f "$_secret_file" ]]; then
    DJANGO_SECRET_KEY="$(tr -d '\r\n' < "$_secret_file")"
    export DJANGO_SECRET_KEY
  elif [[ -n "${SERVICE_PASSWORD_APP:-}" ]]; then
    export DJANGO_SECRET_KEY="${SERVICE_PASSWORD_APP}"
    printf '%s' "$DJANGO_SECRET_KEY" > "$_secret_file"
    chmod 600 "$_secret_file" 2>/dev/null || true
  elif [[ -n "${SERVICE_REALBASE64_APP:-}" ]]; then
    export DJANGO_SECRET_KEY="${SERVICE_REALBASE64_APP}"
    printf '%s' "$DJANGO_SECRET_KEY" > "$_secret_file"
    chmod 600 "$_secret_file" 2>/dev/null || true
  else
    DJANGO_SECRET_KEY="$(_gen_secret)"
    export DJANGO_SECRET_KEY
    if mkdir -p "$_data_dir" 2>/dev/null; then
      printf '%s' "$DJANGO_SECRET_KEY" > "$_secret_file"
      chmod 600 "$_secret_file" 2>/dev/null || true
      echo "[gy-dashboard] DJANGO_SECRET_KEY otomatik üretildi → ${_secret_file}"
    else
      echo "[gy-dashboard] UYARI: /data yazılamıyor — secret kalıcı kaydedilemedi."
    fi
  fi
fi

# --- ALLOWED_HOSTS ---
if [[ -z "${DJANGO_ALLOWED_HOSTS:-}" ]]; then
  _ip="$(_detect_ip)"
  _fqdn=""
  _fqdn="$(_detect_fqdn 2>/dev/null || true)"
  if [[ -n "$_fqdn" ]]; then
    export DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,${_ip},${_fqdn}"
    echo "[gy-dashboard] ALLOWED_HOSTS otomatik: ${_fqdn}"
  else
    export DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,${_ip}"
    echo "[gy-dashboard] ALLOWED_HOSTS otomatik (IP): ${_ip}"
  fi
fi

# --- CSRF + HTTPS ---
if [[ -z "${DJANGO_CSRF_TRUSTED_ORIGINS:-}" ]]; then
  _url=""
  _url="$(_detect_url 2>/dev/null || true)"
  _fqdn=""
  _fqdn="$(_detect_fqdn 2>/dev/null || true)"
  _ip="$(_detect_ip)"
  _app_port="${PORT:-8080}"
  _csrf="http://127.0.0.1:${_app_port},http://localhost:${_app_port},http://${_ip}:${_app_port}"
  if [[ -n "$_url" ]]; then
    _csrf="${_csrf},${_url}"
    export DJANGO_CSRF_TRUSTED_ORIGINS="$_csrf"
    if [[ "$_url" == https://* ]]; then
      export DJANGO_SECURE_SSL="${DJANGO_SECURE_SSL:-1}"
    elif [[ -z "${DJANGO_SECURE_SSL:-}" ]]; then
      export DJANGO_SECURE_SSL=0
    fi
    echo "[gy-dashboard] CSRF otomatik: ${_url}"
  elif [[ -n "$_fqdn" ]]; then
    if _is_http_only_host "$_fqdn"; then
      _csrf="${_csrf},http://${_fqdn}"
      export DJANGO_SECURE_SSL="${DJANGO_SECURE_SSL:-0}"
    else
      _csrf="${_csrf},https://${_fqdn}"
      export DJANGO_SECURE_SSL="${DJANGO_SECURE_SSL:-1}"
    fi
    export DJANGO_CSRF_TRUSTED_ORIGINS="$_csrf"
    echo "[gy-dashboard] CSRF otomatik (FQDN): ${_fqdn}"
  fi
fi

# sslip / traefik.me → HTTPS redirect kapalı (Traefik 404 önlenir)
if [[ -n "${DJANGO_ALLOWED_HOSTS:-}" ]]; then
  if [[ "${DJANGO_ALLOWED_HOSTS}" == *".sslip.io"* || "${DJANGO_ALLOWED_HOSTS}" == *".traefik.me"* ]]; then
    export DJANGO_SECURE_SSL=0
  fi
fi

# sslip / traefik.me test domainleri — üretimde kapalı (DJANGO_ALLOW_SSLIP_HOSTS=0)
export DJANGO_ALLOW_SSLIP_HOSTS="${DJANGO_ALLOW_SSLIP_HOSTS:-0}"

# İlk kurulum: süper admin yalnızca yoksa oluşturulur (şifre sıfırlama için DJANGO_ENSURE_SUPERADMIN=1)
export DJANGO_ENSURE_SUPERADMIN="${DJANGO_ENSURE_SUPERADMIN:-0}"

# WhatsApp köprü Bearer token (paylaşımlı volume: kobiops_secrets)
_secrets_dir="${KOBIOPS_SECRETS_DIR:-/run/kobiops-secrets}"
export KOBIOPS_SECRETS_DIR="$_secrets_dir"
mkdir -p "$_secrets_dir" 2>/dev/null || true
_bridge_token_file="${_secrets_dir}/whatsapp_bridge_token"
if [[ -z "${WHATSAPP_BRIDGE_TOKEN:-}" ]]; then
  if [[ -f "$_bridge_token_file" ]]; then
    WHATSAPP_BRIDGE_TOKEN="$(tr -d '\r\n' < "$_bridge_token_file")"
    export WHATSAPP_BRIDGE_TOKEN
  else
    WHATSAPP_BRIDGE_TOKEN="$(_gen_secret)"
    export WHATSAPP_BRIDGE_TOKEN
    if mkdir -p "$_secrets_dir" 2>/dev/null; then
      printf '%s' "$WHATSAPP_BRIDGE_TOKEN" > "$_bridge_token_file"
      chmod 600 "$_bridge_token_file" 2>/dev/null || true
      chmod 700 "$_secrets_dir" 2>/dev/null || true
      echo "[gy-dashboard] WHATSAPP_BRIDGE_TOKEN otomatik üretildi → ${_bridge_token_file}"
    else
      echo "[gy-dashboard] UYARI: köprü token kalıcı kaydedilemedi (${_secrets_dir})."
    fi
  fi
fi

# WhatsApp köprü varsayılanları (compose servis adı: whatsapp_bridge)
export WHATSAPP_BRIDGE_URL="${WHATSAPP_BRIDGE_URL:-http://whatsapp_bridge:3939}"
export DJANGO_WHATSAPP_BRIDGE_CAN_SPAWN="${DJANGO_WHATSAPP_BRIDGE_CAN_SPAWN:-0}"
export DJANGO_WHATSAPP_BRIDGE_AUTO_START="${DJANGO_WHATSAPP_BRIDGE_AUTO_START:-0}"
export DJANGO_WHATSAPP_BRIDGE_WAIT_ON_START="${DJANGO_WHATSAPP_BRIDGE_WAIT_ON_START:-1}"

export DATA_DIR="${DATA_DIR:-/data}"
export DJANGO_DB_PATH="${DJANGO_DB_PATH:-${DATA_DIR}/db.sqlite3}"
export DJANGO_MEDIA_ROOT="${DJANGO_MEDIA_ROOT:-${DATA_DIR}/media}"
export DJANGO_SERVE_MEDIA="${DJANGO_SERVE_MEDIA:-1}"
export GY_REQUIRE_PERSISTENT_VOLUME="${GY_REQUIRE_PERSISTENT_VOLUME:-1}"
export DJANGO_DEBUG="${DJANGO_DEBUG:-0}"

_app_port="${PORT:-8080}"
if _fqdn="$(_detect_fqdn 2>/dev/null || true)" && [[ -n "$_fqdn" ]]; then
  echo "[gy-dashboard] Coolify domain (port zorunlu): https://${_fqdn}:${_app_port}"
  echo "[gy-dashboard] Not: Coolify paneli sunucuda :8000 — uygulama konteyneri :${_app_port} (farklı, çakışmaz)."
fi