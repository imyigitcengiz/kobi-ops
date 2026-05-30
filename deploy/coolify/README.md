# Coolify kurulumu (Ghost tarzı — kutudan çıkar çıkmaz)

## ÖNEMLİ: Docker Compose build pack

Coolify'da **Dockerfile** build pack ile kurarsanız volume bağlanmaz ve uygulama durur.

| Ayar | Doğru değer |
|------|-------------|
| Build Pack | **Docker Compose** |
| Compose path | `docker-compose.yaml` veya `docker-compose.yml` |
| Domain servisi | **`app`** (whatsapp_bridge değil) |
| Persistent Storage UI | **Gerekmez** — `gy_data` named volume compose'ta |

## Port: 8000 ≠ uygulama portu

| Ne | Port | Açıklama |
|----|------|----------|
| Coolify paneli | **8000** (sunucu) | `http://sunucu-ip:8000` — yönetim arayüzü |
| KobiOps `app` | **8080** (konteyner içi) | Traefik domain ile buraya yönlendirir |

Bunlar **çakışmaz** — biri sunucuda, diğeri Docker ağında. Node.js'teki 3000→3001 gibi otomatik port yok; Coolify'da domain alanına port **elle** yazılır.

## Domain — 404'ün #1 sebebi

Compose çok servisli stack'te Traefik hangi porta gideceğini domain satırından alır.

**Doğru** (port dahil):

```text
https://panel.firma.com:8080
```

**Yanlış** (404 page not found):

```text
https://panel.firma.com
```

Coolify → **Domains** → servis **`app`** → yukarıdaki formatta kaydedin → **Redeploy**.

## 3 adımda deploy

1. **New Resource** → GitHub → `imyigitcengiz/kobi-ops`
2. Build Pack: **Docker Compose** → path: `docker-compose.yaml`
3. **Domains** → servis **`app`** → `https://SIZIN-DOMAIN.com:8080` → HTTPS → **Deploy**

`.env` yazmanız gerekmez. İlk admin şifresi: container log veya `/data/.initial_admin_password`.

## Exited / unhealthy

Logs'ta şunları arayın:

| Log | Anlam |
|-----|--------|
| `Kalıcı veri kontrolü OK` | Volume tamam |
| `daphne 0.0.0.0:8080` | Uygulama dinliyor |
| `DJANGO_SECRET_KEY otomatik üretildi` | Secret tamam |
| `KRİTİK: /data kalıcı volume` | Build Pack Dockerfile — Compose'a geçin |

Container durumu: Coolify → Logs veya sunucuda `docker ps` (healthy olmalı).

## Volume (otomatik)

```yaml
volumes:
  - gy_data:/data
```

Coolify named volume `kobiops_gy_data` oluşturur. Rebuild'de **volume silmeyin**.

## WhatsApp

`whatsapp_bridge` servisine **domain bağlamayın**. Sadece `app` servisi dışarı açılır; köprü iç ağda `3939`.

Genel: [DEPLOY.md](../../DEPLOY.md)
