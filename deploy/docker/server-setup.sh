#!/usr/bin/env bash
# Linux sunucuda: gy-dashboard-py-image.tar + docker-compose.yml + .env.docker ile
set -euo pipefail

cd "$(dirname "$0")/../.."
if [[ ! -f gy-dashboard-py-image.tar ]]; then
  echo "gy-dashboard-py-image.tar bulunamadi. Once Windows'ta export-image.ps1 calistirin."
  exit 1
fi
if [[ ! -f .env.docker ]]; then
  cp deploy/docker/.env.example .env.docker
  echo "Duzenleyin: .env.docker (SECRET_KEY, domain)"
  exit 1
fi

docker load -i gy-dashboard-py-image.tar
docker compose up -d
echo "http://$(hostname -I | awk '{print $1}'):8000/giris/"
