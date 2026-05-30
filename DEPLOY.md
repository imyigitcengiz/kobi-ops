# KobiOps — üretim kurulumu

Her müşteri kendi VPS / panelinde bağımsız kurulum. **Coolify, Dokploy, 1Panel, Portainer** veya `docker compose` ile dağıtılır.

## Tak-çalıştır (Ghost gibi)

Panelde 3 adım — `.env` ve Persistent Storage UI **gerekmez**:

1. GitHub: `imyigitcengiz/kobi-ops`
2. **Docker Compose** build pack (`docker-compose.yaml` — Coolify varsayılan) — **Dockerfile tek başına değil**
3. Domain → servis **`app`**, port **8080**, URL: `https://domain.com:8080` → Deploy

Named volume `kobiops_gy_data` compose ile otomatik oluşur; veri rebuild'lerde kalır.

`deploy/bootstrap-env.sh` otomatik ayarlar:

| Ne | Nasıl |
|----|--------|
| `DJANGO_SECRET_KEY` | `/data/.django_secret_key` (kalıcı) |
| `DJANGO_ALLOWED_HOSTS` | Coolify `SERVICE_FQDN_APP` / panel domain |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `SERVICE_URL_APP` / https URL |
| `DJANGO_SECURE_SSL` | HTTPS domain → 1, sslip.io → 0 |
| Admin hesabı | İlk deploy: admin/admin (`DJANGO_ENSURE_SUPERADMIN=1`) |

## Bileşenler

| Bileşen | Açıklama |
|--------|----------|
| **app** | Django + Daphne (8080), SQLite + medya `/data` |
| **whatsapp_bridge** | Node + Chromium, WhatsApp QR (3939, iç ağ) |

## VPS tek komut

```bash
git clone https://github.com/imyigitcengiz/kobi-ops.git /opt/kobi-ops
cd /opt/kobi-ops && ./deploy/install.sh panel.firma.com
```

## Platform rehberleri

| Platform | Rehber |
|----------|--------|
| Coolify | [deploy/coolify/README.md](deploy/coolify/README.md) |
| Dokploy | [deploy/dokploy/README.md](deploy/dokploy/README.md) |
| 1Panel | [deploy/1panel/README.md](deploy/1panel/README.md) |

## Ortam değişkenleri

**Tak-çalıştır:** Panel Environment sekmesine bir şey yazmanız gerekmez.

| Kaynak | Ne sağlar |
|--------|-----------|
| `docker-compose.yaml` | Üretim varsayılanları (port, /data, WhatsApp URL, volume) |
| `bootstrap-env.sh` | Secret, ALLOWED_HOSTS, CSRF (domain'den otomatik) |
| Coolify `SERVICE_FQDN_APP` / `SERVICE_URL_APP` | Domain tanımlayınca otomatik enjekte |

**Referans şablon** (isteğe bağlı override için): [.env.example](.env.example)

Tüm değişkenler 4 grupta:
- **A) Otomatik** — boş bırakın
- **B) Compose'ta hazır** — zaten yazılı
- **C) İsteğe bağlı override** — sadece değiştirmek istediğinizde
- **D) Yerel geliştirme** — Docker dışı

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `DJANGO_SECRET_KEY` | Otomatik | Boş bırakılırsa `/data` içinde üretilir |
| `DJANGO_ALLOWED_HOSTS` | Otomatik | Panel domain'den |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Otomatik | HTTPS URL'den |
| `DATA_DIR` | Docker varsayılan | `/data` |
| `WHATSAPP_BRIDGE_URL` | Compose varsayılan | `http://whatsapp_bridge:3939` |
| `GY_REQUIRE_PERSISTENT_VOLUME` | `1` | Volume yoksa başlamaz |
| `GY_ALLOW_EPHEMERAL_DATA` | `0` | `1` = sadece test |

## Kalıcı veri

Named volume **`kobiops_gy_data`** → `/data`:

- `db.sqlite3`, `media/`, `backups/auto/`

Coolify ekstra: Persistent Storage → `/data`. Rebuild'de volume **silinmesin**.

## Sorun giderme

**Container kapanıyor — `/data kalıcı volume`**

Bu hata = `/data` mount edilmemiş. Coolify'da **Build Pack Dockerfile ise** volume bağlanmaz.

→ Build Pack'i **Docker Compose** yapın, compose path: `docker-compose.yaml` (veya boş bırakın), redeploy.

Logda beklenen: `Kalıcı veri kontrolü OK (migrate öncesi).`

**WhatsApp**

1. `docker compose ps` — `whatsapp_bridge` ayakta mı?
2. `docker compose logs whatsapp_bridge`
3. RAM ≥ 2 GB, `shm_size: 512mb` compose'ta tanımlı

**CSRF / DisallowedHost**

Domain panelde `app` servisine bağlı olmalı; redeploy.

**WebSocket** (sohbet): reverse proxy Upgrade header — HTTP polling yedek olarak çalışır.

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```
