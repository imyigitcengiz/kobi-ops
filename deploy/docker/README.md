# Docker ile kurulum (GitHub gerekmez)

Projeyi kendi bilgisayarınızda imaj olarak üretip sunucunuza **dosya olarak** taşıyabilirsiniz.

## Gereksinimler

- Docker Desktop (Windows) veya Docker Engine (Linux)
- Proje klasörünün tamamı (bu repo veya zip)

## 1) Yerelde imaj oluşturma (Windows)

PowerShell, proje kökünde:

```powershell
copy deploy\docker\.env.example .env.docker
# .env.docker içinde DJANGO_SECRET_KEY ve DJANGO_ALLOWED_HOSTS düzenleyin
.\deploy\docker\build.ps1
```

Tarayıcı: http://localhost:8000/giris/ — ilk giriş `admin` / `admin` (DJANGO_ENSURE_SUPERADMIN=1 ise).

## 2) İmajı sunucuya taşıma (GitHub yok)

```powershell
.\deploy\docker\export-image.ps1
```

Oluşan `gy-dashboard-py-image.tar` dosyasını USB, SCP veya panel ile sunucuya kopyalayın.

Linux sunucuda:

```bash
docker load -i gy-dashboard-py-image.tar
mkdir -p /opt/gy-dashboard && cd /opt/gy-dashboard
# .env.docker ve docker-compose.yml dosyalarını buraya koyun
docker compose up -d
```

`docker-compose.yml` ve `.env.docker` proje kökünden sunucuya kopyalanmalıdır (sadece tar yetmez).

## 3) Sunucuda sıfırdan build (alternatif)

Sunucuda proje klasörü varsa GitHub şart değil; `scp` / zip ile klasörü atın:

```bash
cp deploy/docker/.env.example .env.docker
nano .env.docker   # SECRET_KEY, domain, ALLOWED_HOSTS
docker compose build --no-cache
docker compose up -d
```

## Kalıcı veri

| Volume | İçerik |
|--------|--------|
| `gy_dashboard_data` → `/data` | `db.sqlite3`, `media/` |

Yedek: `/tools/yedekler/` → `.json.gz` indir; `media/` klasörünü volume içine kopyala.

## Ortam değişkenleri

Örnek: `deploy/docker/.env.example` → kökte `.env.docker`.

| Değişken | Açıklama |
|----------|----------|
| `DJANGO_SECRET_KEY` | Zorunlu, uzun rastgele |
| `DJANGO_ALLOWED_HOSTS` | Domain ve IP, virgülle |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://domain` |
| `DATA_DIR` | `/data` (volume) |
| `DJANGO_ENSURE_SUPERADMIN` | İlk kurulumda `1`, sonra `0` |

## WhatsApp köprüsü

Django imajı WhatsApp’ı **içermez**. Köprüyü host’ta veya ayrı container’da çalıştırın; `WHATSAPP_BRIDGE_URL` ile bağlayın. Windows Docker’da host: `host.docker.internal`.

## Sorun giderme

| Sorun | Çözüm |
|-------|--------|
| `exec ... no such file` | Entrypoint CRLF — imajı yeniden build edin |
| 400 DisallowedHost | `DJANGO_ALLOWED_HOSTS` |
| CSRF | `DJANGO_CSRF_TRUSTED_ORIGINS` tam URL |
| Statik yok | `docker compose logs web` → collectstatic |
| Veri kaybı | Volume mount `/data` kontrol |

## Komutlar

```bash
docker compose logs -f web
docker compose exec web python manage.py ensure_superadmin --reset-password
docker compose exec web python manage.py migrate
docker compose down
docker compose up -d --build
```
