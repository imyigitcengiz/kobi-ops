# KobiOps — üretim kurulumu

Bu ürün **müşteri başına ayrı kurulum** içindir (her müşteri kendi VPS / panelinde). Tek kod tabanı; Coolify, 1Panel, Portainer, Railway veya `docker compose` ile dağıtılabilir.

## Bileşenler

| Bileşen | Açıklama |
|--------|----------|
| **app** | Django + Daphne (port 8000), SQLite + medya `/data` altında |
| **whatsapp-bridge** | Node + Chromium, WhatsApp Web QR (port 3939, iç ağ) |

Panel konteynerinde Node/Puppeteer **yoktur**. Köprü ayrı servistir.

## Hızlı başlangıç (önerilen)

```bash
git clone https://github.com/imyigitcengiz/kobi-ops.git
cd kobi-ops
cp deploy/coolify/.env.example .env
# .env içinde DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, DJANGO_CSRF_TRUSTED_ORIGINS doldurun

docker compose up -d --build
```

- Panel: `http://sunucu:8000/giris/`
- İlk giriş: `DJANGO_ENSURE_SUPERADMIN=1` ise `admin` / `admin` (sonra kapatın)

## Ortam değişkenleri (app)

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `DJANGO_SECRET_KEY` | Evet | Uzun rastgele anahtar |
| `DJANGO_ALLOWED_HOSTS` | Evet | `panel.ornek.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | HTTPS ise | `https://panel.ornek.com` |
| `DATA_DIR` | Docker’da otomatik | `/data` — kalıcı volume bağlayın |
| `WHATSAPP_BRIDGE_URL` | WhatsApp için | Compose’ta: `http://whatsapp-bridge:3939` |
| `DJANGO_WHATSAPP_BRIDGE_CAN_SPAWN` | Docker’da `0` | Panel içinden Node başlatmayı kapatır |
| `GY_REQUIRE_PERSISTENT_VOLUME` | Docker’da `1` (varsayılan) | `/data` volume yoksa konteyner başlamaz |
| `GY_ALLOW_EPHEMERAL_DATA` | `0` | `1` = volume zorunluluğunu kapat (sadece test) |

## Kalıcı veri

Volume **`/data`**:

- `/data/db.sqlite3` — veritabanı
- `/data/media/` — yüklenen dosyalar
- `/data/backups/auto/` — her deploy öncesi otomatik SQLite yedeği (son 10)

**Volume yoksa veya Coolify rebuild sırasında volume silindiyse tüm kayıtlar gider.**

Panel, `/data` gerçekten kalıcı volume değilse **başlamaz** (`GY_REQUIRE_PERSISTENT_VOLUME=1`). Coolify → **Persistent Storage** → mount path: **`/data`**.

İlk kurulumda volume henüz yoksa (sadece test): `GY_ALLOW_EPHEMERAL_DATA=1` — üretimde kullanmayın; volume ekledikten sonra kaldırın.

Deploy logu:

```text
[gy-dashboard] kalıcı veri kontrolü...
Kalıcı veri kontrolü OK (migrate öncesi).
```

Volume hatası örneği:

```text
KRİTİK: /data kalıcı volume olarak bağlı değil...
```

## Coolify

1. **Docker Compose** veya iki uygulama:
   - Uygulama 1: repo kökü, `Dockerfile`, port **8000**, volume `/data`
   - Uygulama 2 (isteğe bağlı ayrı): `deploy/whatsapp-bridge/Dockerfile`, port 3939 (dışarı açmayın)
2. Aynı Docker ağında: `WHATSAPP_BRIDGE_URL=http://<köprü-servis-adı>:3939`
3. `DJANGO_WHATSAPP_BRIDGE_CAN_SPAWN=0`
4. Tek Dockerfile ile sadece panel kurulursa WhatsApp **çalışmaz** — köprü servisi şart.

Detay: [deploy/coolify/README.md](deploy/coolify/README.md)

## 1Panel / Portainer

`compose.yaml` dosyasını **Compose Stack** olarak içe aktarın (repo kökü); `.env` doldurun; reverse proxy ile **443 → 8000** yönlendirin.

Adım adım (1Panel): **[deploy/1panel/README.md](deploy/1panel/README.md)**

## Yerel geliştirme (Windows)

1. Yerel geliştirmede Node.js yoksa Django `npm install` dener; Windows’ta [Node.js LTS](https://nodejs.org) kurmanız yeterli. Linux sunucuda (root) apt ile nodejs kurmayı da dener.
2. Bir kez köprü bağımlılıkları:

```bash
cd tools/whatsapp_bridge
# npm install — Django otomatik çalıştırır; elle gerekmez
```

3. Panel:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

`DATA_DIR` yokken Django **otomatik** Node köprüsünü başlatır (`DJANGO_WHATSAPP_BRIDGE_AUTO_START` varsayılan açık). Kapatmak için: `set DJANGO_WHATSAPP_BRIDGE_AUTO_START=0`.

Köprüyü elle (gerekirse): `cd tools/whatsapp_bridge && npm start` → http://127.0.0.1:3939 — normalde Django açar.

`WHATSAPP_BRIDGE_URL=http://127.0.0.1:3939` — isteğe bağlı `WHATSAPP_BRIDGE_NODE=C:\Program Files\nodejs\node.exe`

## Sorun giderme — “Köprü çalışmıyor”

**Docker / Coolify (üretim)**

1. `docker compose ps` — `whatsapp-bridge` **healthy** mi?
2. App ortamında `WHATSAPP_BRIDGE_URL=http://whatsapp-bridge:3939` ve `DJANGO_WHATSAPP_BRIDGE_CAN_SPAWN=0`
3. Köprü logları: `docker compose logs whatsapp-bridge` (Chromium / QR hataları burada)
4. Sadece `app` konteyneri kurulduysa WhatsApp **çalışmaz** — `whatsapp-bridge` servisini ekleyin (`deploy/coolify/compose.yaml`).
5. Panel açılışında entrypoint köprüyü bekler; hazır değilse logda uyarı görünür.

**Yerel Windows**

1. `node -v` çalışıyor mu? Log: `tools/whatsapp_bridge/bridge_ui.log` (Django npm install dener)
2. `http://127.0.0.1:3939/health` tarayıcıda `{"ok":true}` dönmeli.
3. Araçlar → WhatsApp bağlan → “Köprüyü başlat” veya sunucuyu yeniden başlatın (otomatik spawn).
4. Port 3939 meşgulse Görev Yöneticisi’nden eski `node.exe` sürecini kapatın.

Manuel test: `python manage.py wait_whatsapp_bridge --timeout 30 --spawn`

## Ekip sohbeti

Deploy sonrası otomatik: `migrate` + `ensure_chat` (entrypoint).

Reverse proxy (Coolify / Traefik / Nginx) WebSocket için:

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

WebSocket kapalı olsa bile sohbet **HTTP ile** çalışır (4 sn polling). Sohbet açılmıyorsa panelde kırmızı hata metni görünür; çoğunlukla `python manage.py migrate chat` eksiktir.
