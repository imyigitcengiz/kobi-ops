# Coolify kurulumu

Tek üretim yolu: **GitHub + Dockerfile + `/data` volume**.

## 1. Coolify uygulaması

| Ayar | Değer |
|------|--------|
| Kaynak | `https://github.com/imyigitcengiz/gy-dashboard-py` |
| Branch | `main` |
| Build | **Dockerfile** (kök) |
| Port (container) | `8000` |
| Health check | `/giris/` (Dockerfile’da tanımlı) |

## 2. Kalıcı depolama (zorunlu)

**Persistent Storage** ekleyin:

- **Mount path:** `/data`
- İçerik: `db.sqlite3`, `media/`

Volume yoksa her deploy’da veritabanı sıfırlanır.

## 3. Ortam değişkenleri

`deploy/coolify/.env.example` dosyasını Coolify **Environment** alanına kopyalayın.

Minimum:

```env
DJANGO_SECRET_KEY=...
DJANGO_ALLOWED_HOSTS=panel.sizin.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://panel.sizin.com
DJANGO_SECURE_SSL=1
DJANGO_ENSURE_SUPERADMIN=1
```

İlk girişten sonra `DJANGO_ENSURE_SUPERADMIN=0` yapıp redeploy edin.

`DATA_DIR`, `DJANGO_DB_PATH`, `DJANGO_MEDIA_ROOT` Dockerfile’da hazır; Coolify’da tekrar yazmanız gerekmez.

## 4. Domain

- Domain ekleyin, HTTPS açın
- `ALLOWED_HOSTS` ve `CSRF_TRUSTED_ORIGINS` tam domain ile eşleşmeli

## 5. Deploy

Logda beklenen:

```text
[gy-dashboard] migrate + collectstatic...
[gy-dashboard] daphne 0.0.0.0:8000
```

## Veri taşıma (önerilen: SQLite)

1. Lokal: `/tools/yedekler/` → **db.sqlite3 İndir**
2. Sunucu: aynı sayfa → **SQLite İçe Aktar** → dosya `/data/db.sqlite3` olur
3. Lokal `media/` → `docker cp ./media/. <container>:/data/media/`

Alternatif: JSON.gz (aynı sayfada).

## Sorun giderme

| Belirti | Çözüm |
|---------|--------|
| Container kapanıyor | Logs; `PORT` ve entrypoint `0.0.0.0` |
| 400 DisallowedHost | `DJANGO_ALLOWED_HOSTS` |
| CSRF | `DJANGO_CSRF_TRUSTED_ORIGINS` https URL |
| DB sıfırlanıyor | Volume `/data` |
| WhatsApp | Ayrı servis; `WHATSAPP_BRIDGE_URL` |

## Yerel Docker test (isteğe bağlı)

```bash
docker build -t gy-dashboard .
docker run --rm -p 8000:8000 -v gy_data:/data \
  -e DJANGO_SECRET_KEY=test -e DJANGO_ALLOWED_HOSTS=localhost \
  -e DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:8000 \
  -e DJANGO_ENSURE_SUPERADMIN=1 \
  gy-dashboard
```
