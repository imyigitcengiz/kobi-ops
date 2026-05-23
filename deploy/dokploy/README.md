# KobiOps — Dokploy kurulumu

[Dokploy](https://dokploy.com) ile **Docker Compose** modunda deploy. Panel + WhatsApp köprüsü birlikte çalışır.

## Ön koşullar

- Dokploy kurulu sunucu (Traefik dahil)
- GitHub repo: `https://github.com/imyigitcengiz/kobi-ops`
- En az **2 GB RAM** (WhatsApp köprüsü Chromium kullanır)

## 1. Yeni Docker Compose projesi

1. Dokploy → **Project** → **Docker Compose** → **Create**
2. **Source:** GitHub → `imyigitcengiz/kobi-ops`, branch `main`
3. **Compose file path:** `docker-compose.yml` (repo kökü — varsayılan, boş bırakılabilir)  
   veya `deploy/dokploy/compose.yaml` (o zaman `.env` aynı klasörde olmalı)
4. **Build:** Compose modu (Stack değil — `build:` destekler)

## 2. Ortam değişkenleri

**Environment** sekmesinde `deploy/dokploy/.env.example` içeriğini yapıştırın veya düzenleyin.

Dokploy değişkenleri compose dosyasıyla **aynı dizinde** `.env` oluşturur. Container’a geçmesi için `docker-compose.yml` içinde zaten vardır:

```yaml
env_file:
  - .env
```

Zorunlu alanlar:

| Değişken | Örnek |
|----------|--------|
| `DJANGO_SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DJANGO_ALLOWED_HOSTS` | `panel.sizin-domain.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://panel.sizin-domain.com` |
| `DJANGO_SECURE_SSL` | `1` |
| `WHATSAPP_BRIDGE_URL` | `http://whatsapp-bridge:3939` |
| `DJANGO_WHATSAPP_BRIDGE_CAN_SPAWN` | `0` |

`DJANGO_SECRET_KEY` içinde `$` varsa **tek tırnak** kullanın:

```env
DJANGO_SECRET_KEY='abc$xyz!...'
```

## 3. Domain (HTTPS)

**Domains** sekmesi → **Add Domain**

- Service: `app`
- Container port: `8000`
- Domain: `panel.sizin-domain.com`
- HTTPS: Let's Encrypt

Manuel Traefik label yazmanız gerekmez; Dokploy otomatik ekler. **Preview Compose** ile doğrulayın.

DNS: domain için **A kaydı** → sunucu IP.

## 4. Kalıcı veri (volume)

Compose’taki **named volume** kullanın (`gy_data`, `whatsapp_session`):

- `gy_data` → `/data` (SQLite + medya)
- `whatsapp_session` → WhatsApp oturumları

Dokploy **Volume Backups** (S3) için named volume uygundur. Deploy sırasında volume’ları silmeyin.

## 5. Deploy

**Deploy** → logda `migrate`, `daphne` görünmeli.

- URL: `https://panel.sizin-domain.com/giris/`
- İlk giriş: `admin` / `admin` (`DJANGO_ENSURE_SUPERADMIN=1` ise)
- Sonra `DJANGO_ENSURE_SUPERADMIN=0` + şifre değiştir + yeniden deploy

## 6. GitHub otomatik deploy (Dokploy webhook)

Dokploy projesinde **Deployments** → **Webhook** URL’sini kopyalayın.

GitHub → repo → **Settings** → **Webhooks** → push event → Dokploy URL.

Push = Dokploy yeniden build/deploy (ayrı `sync.sh` gerekmez).

## 7. Servis kontrolü

- **Logs** → `app` ve `whatsapp-bridge` ayrı izlenir
- `whatsapp-bridge` **healthy** olmalı
- Tools → WhatsApp Bağlan → QR

## Sorun giderme

| Belirti | Çözüm |
|---------|--------|
| App **Restarting** / `DJANGO_SECRET_KEY zorunludur` | Compose → **Environment** → `DJANGO_SECRET_KEY` ekle → **Redeploy**. `KeyError: guard_persistent_data` aynı sebep (settings yüklenemedi). |
| `.env` container'a gitmiyor | `docker-compose.yml` içinde `env_file: - .env` olmalı; Environment sekmesindeki değişkenler deploy sonrası container'da görünmeli |
| DisallowedHost | `DJANGO_ALLOWED_HOSTS` domain ile aynı |
| **404** (sayfa yok) | `DJANGO_SECURE_SSL=0`, adres **http://** (https değil), Domain **HTTPS kapalı**, **Redeploy**. `/giris/` dene. |
| Panel geldi → **502** → **404** | `app` restart döngüsü: Logs kontrol, `whatsapp-bridge` RAM, **Redeploy**. `http://…/healthz/` → `ok` olmalı. `DJANGO_SECURE_SSL=0`. |
| CSRF | `DJANGO_CSRF_TRUSTED_ORIGINS` — sslip için `http://tam-host` |
| WhatsApp kapalı | `whatsapp-bridge` log; `WHATSAPP_BRIDGE_URL` servis adı |
| Veri sıfırlandı | Volume silinmiş; `gy_data` koru |

Genel deploy: [DEPLOY.md](../../DEPLOY.md)
