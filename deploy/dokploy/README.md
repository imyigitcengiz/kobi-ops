# KobiOps — Dokploy kurulumu (tak-çalıştır)

[Dokploy](https://dokploy.com) ile Docker Compose modunda panel + WhatsApp köprüsü birlikte çalışır.

## 3 adımda deploy

1. **Project** → **Docker Compose** → **Create**
2. **Source:** GitHub → `imyigitcengiz/kobi-ops`, branch `main`  
   **Compose file path:** `docker-compose.yaml`
3. **Domains** → servis **`app`**, port **`8000`**, Let's Encrypt → **Deploy**

Environment sekmesine `.env` yazmanız **gerekmez** — `bootstrap-env.sh` secret, host ve CSRF'yi otomatik tamamlar.

- URL: `https://panel.sizin-domain.com/giris/`
- İlk giriş: **admin** / **admin**
- Sonra `DJANGO_ENSURE_SUPERADMIN=0` + redeploy

## Ön koşullar

- En az **2 GB RAM** (WhatsApp köprüsü Chromium kullanır)
- DNS A kaydı → sunucu IP

## Kalıcı veri

Named volume `kobiops_gy_data` → `/data` (SQLite + medya). Deploy sırasında volume silmeyin.

## Environment (isteğe bağlı)

Manuel override: repo kökündeki [`.env.example`](../../.env.example)

Dokploy UI'daki değişkenler `.env` dosyasına yazılır; compose'ta `env_file` opsiyonel tanımlı.

`DJANGO_SECRET_KEY` içinde `$` varsa tek tırnak: `DJANGO_SECRET_KEY='abc$xyz'`

## GitHub otomatik deploy

Dokploy → **Deployments** → **Webhook** → GitHub push event.

## Sorun giderme

| Belirti | Çözüm |
|---------|--------|
| App Restarting / SECRET_KEY | Logs; `/data` volume var mı? Redeploy |
| DisallowedHost | Domain `app` servisine bağlı mı? |
| 404 / sslip | `DJANGO_SECURE_SSL` otomatik 0; http:// kullanın |
| CSRF | Domain ile CSRF otomatik; redeploy |
| WhatsApp kapalı | `whatsapp_bridge` logs; RAM kontrol |
| Veri sıfırlandı | `kobiops_gy_data` volume koruyun |

Genel: [DEPLOY.md](../../DEPLOY.md)
