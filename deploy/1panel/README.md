# KobiOps — 1Panel kurulumu (tak-çalıştır)

1Panel **Docker Compose Stack** ile panel + WhatsApp köprüsü birlikte çalışır.

## Hızlı kurulum (SSH)

```bash
cd /opt
git clone https://github.com/imyigitcengiz/kobi-ops.git
cd kobi-ops
chmod +x deploy/install.sh
./deploy/install.sh panel.sizin-domain.com
```

`install.sh` `.env` üretir, secret/host/CSRF ayarlar, `docker compose up -d --build` çalıştırır.

Domain yoksa: `./deploy/install.sh` → `http://SUNUCU_IP:8000/giris/`

## 1Panel arayüzü ile

1. **Konteyner** → **Compose** → **Oluştur**
2. **Kaynak:** `/opt/kobi-ops`
3. **Compose dosyası:** `docker-compose.yaml`
4. **Başlat** — `.env` zorunlu değil (bootstrap otomatik)

İsteğe bağlı `.env`: `cp .env.example .env`

## Reverse proxy (HTTPS)

1Panel **Web sitesi** / OpenResty:

- Domain → proxy `http://127.0.0.1:8000`
- WebSocket açık (ekip sohbeti)

Domain ekledikten sonra redeploy veya `./deploy/install.sh panel.sizin-domain.com --force`

## Kalıcı veri

| Volume | Mount | İçerik |
|--------|--------|--------|
| `kobiops_gy_data` | `/data` | SQLite, medya, yedekler |
| `kobiops_whatsapp_session` | köprü oturumu | WhatsApp QR |

Stack silinirken **volume silmeyin**.

## İlk giriş

- `https://panel.sizin-domain.com/giris/`
- **admin** / **admin** → sonra `DJANGO_ENSURE_SUPERADMIN=0`

## Güncelleme

```bash
cd /opt/kobi-ops
git pull
docker compose up -d --build
```

## Sorun giderme

| Belirti | Çözüm |
|---------|--------|
| 502 | `docker compose logs app` |
| CSRF | `./deploy/install.sh domain --force` |
| WhatsApp | `docker compose logs whatsapp_bridge` |
| Veri kaybı | Volume korundu mu? |

Detay: [DEPLOY.md](../../DEPLOY.md)
