# Coolify kurulumu

## Kaynak

- Repo: `https://github.com/imyigitcengiz/gy-dashboard-py.git`
- Build: **Dockerfile** (repo kökünde)
- Port: **8000** (veya Coolify’ın verdiği `PORT` — entrypoint otomatik kullanır)

## Persistent storage (zorunlu)

| Container path | İçerik |
|----------------|--------|
| `/data` | `db.sqlite3` + `media/` |

Environment:

```
DATA_DIR=/data
DJANGO_DB_PATH=/data/db.sqlite3
DJANGO_MEDIA_ROOT=/data/media
```

## Ortam değişkenleri

`deploy/coolify/.env.example` dosyasındaki değerleri Coolify UI → Environment’a ekleyin.

Domain örneği:

```
DJANGO_ALLOWED_HOSTS=crm.sizin.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://crm.sizin.com
DJANGO_SECURE_SSL=1
```

## Veri taşıma

1. Lokal: `/tools/yedekler/` → `.json.gz` indir  
2. Sunucu ayağa kalkınca aynı sayfadan import  
3. `media/` klasörünü `/data/media` volume’e kopyalayın  

## Medya sıkıştırma

Yüklenen dosyalar sunucuda türüne göre işlenir: resimler yeniden boyutlandırılır (JPEG/WebP), video ve ses `ffmpeg` ile sıkıştırılır (Docker imajında kurulu). Arşiv ve belgeler olduğu gibi saklanır.

## Sorun giderme

| Belirti | Çözüm |
|---------|--------|
| Container hemen kapanıyor | Loglara bakın; `PORT` ve `0.0.0.0` bind — Dockerfile/entrypoint kullanın |
| 400 Bad Request (DisallowedHost) | `DJANGO_ALLOWED_HOSTS` domain ekleyin |
| CSRF hatası | `DJANGO_CSRF_TRUSTED_ORIGINS` https URL |
| Statik dosya yok | `collectstatic` entrypoint’te çalışır; redeploy |
| DB sıfırlanıyor | `/data` volume bağlı mı kontrol edin |

## WhatsApp köprüsü

Ayrı Node servisi olarak çalıştırın; `WHATSAPP_BRIDGE_URL` o servisin iç URL’si olsun.
