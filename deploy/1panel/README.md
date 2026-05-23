# KobiOps — 1Panel kurulumu

1Panel’de **Docker Compose Stack** ile panel + WhatsApp köprüsünü birlikte çalıştırın. Tek konteyner (sadece `app`) kurarsanız WhatsApp **çalışmaz**.

## Ön koşullar

- 1Panel kurulu VPS (en az 2 GB RAM önerilir; WhatsApp köprüsü Chromium kullanır)
- Alan adı (isteğe bağlı ama HTTPS için önerilir)
- GitHub’dan repo erişimi veya `git clone`

## 1. Projeyi sunucuya alın

SSH ile sunucuda:

```bash
cd /opt
git clone https://github.com/imyigitcengiz/kobi-ops.git
cd kobi-ops
```

1Panel **Terminal** veya **Dosya** ile de aynı klasöre kopyalayabilirsiniz.

## 2. Ortam dosyası (.env)

```bash
cp deploy/coolify/.env.example .env
nano .env
```

Örnek (kendi domaininizle değiştirin):

```env
DJANGO_SECRET_KEY=uzun-rastgele-50-karakter-veya-daha-fazla
DJANGO_ALLOWED_HOSTS=panel.sizin-domain.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://panel.sizin-domain.com
DJANGO_SECURE_SSL=1
DJANGO_DEBUG=0

DJANGO_ENSURE_SUPERADMIN=1

WHATSAPP_BRIDGE_URL=http://whatsapp-bridge:3939
DJANGO_WHATSAPP_BRIDGE_CAN_SPAWN=0
DJANGO_WHATSAPP_BRIDGE_AUTO_START=0
```

`DJANGO_SECRET_KEY` üretmek için:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 3. 1Panel’de Compose Stack oluşturma

1. **Konteyner** → **Compose** → **Oluştur** (veya **Stack oluştur**)
2. **Kaynak**: Yerel yol → `/opt/kobi-ops` (clone ettiğiniz dizin)
3. **Compose dosyası**: `compose.yaml` (repo kökündeki)
4. **Ortam dosyası**: `.env` dosyasını seçin veya değişkenleri 1Panel arayüzüne tek tek yapıştırın
5. **Ağ**: Varsayılan bridge yeterli; iki servis aynı stack içinde birbirini görür
6. **Başlat** / **Deploy**

İlk build 5–15 dakika sürebilir (Python + Node/Chromium imajları).

## 4. Kalıcı veri (çok önemli)

Stack volume’ları `compose.yaml` içinde tanımlıdır:

| Volume | Mount | İçerik |
|--------|--------|--------|
| `gy_data` | `/data` (app) | `db.sqlite3`, `media/`, otomatik yedekler |
| `whatsapp_session` | `/app/session` (köprü) | WhatsApp oturumları |

1Panel’de stack’i **silip yeniden oluştururken volume’ları silmeyin**; aksi halde tüm müşteri/servis verisi gider.

Yedek: **Site Ayarları** → **Sistem Yedekleri** → `db.sqlite3` indir + sunucuda volume içindeki `media/` klasörünü kopyalayın.

## 5. Reverse proxy (HTTPS)

1Panel **Web sitesi** veya **OpenResty/Nginx** ile:

- Domain: `panel.sizin-domain.com`
- **Proxy** → hedef: `http://127.0.0.1:8000` (compose `8000:8000` map ise)
- **WebSocket** desteği açık olsun (ekip sohbeti için)

Örnek proxy başlıkları (Nginx):

```nginx
proxy_http_version 1.1;
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

`.env` içinde `DJANGO_CSRF_TRUSTED_ORIGINS` ve `DJANGO_ALLOWED_HOSTS` domain ile **birebir** eşleşmeli.

## 6. İlk giriş

- URL: `https://panel.sizin-domain.com/giris/`
- `DJANGO_ENSURE_SUPERADMIN=1` ise: kullanıcı **admin**, şifre **admin**
- Giriş yaptıktan sonra `.env` içinde `DJANGO_ENSURE_SUPERADMIN=0` yapıp stack’i yeniden başlatın ve admin şifresini değiştirin

## 7. WhatsApp

1. **Tools** → **WhatsApp Bağlan**
2. Köprü yeşil değilse: `docker compose logs whatsapp-bridge` (stack dizininde)
3. QR ile telefon eşleştirin

Köprü sağlık kontrolü (sunucuda):

```bash
docker compose exec whatsapp-bridge wget -qO- http://127.0.0.1:3939/health
```

## 8. Güncelleme

```bash
cd /opt/kobi-ops
git pull
docker compose up -d --build
```

## Sorun giderme

| Belirti | Çözüm |
|---------|--------|
| 502 / site açılmıyor | `docker compose ps` — `app` ayakta mı? `docker compose logs app` |
| CSRF hatası | `DJANGO_CSRF_TRUSTED_ORIGINS` https:// ile domain |
| Veri sıfırlandı | Volume silinmiş; `/data` mount kontrol edin |
| WhatsApp köprü kapalı | `whatsapp-bridge` servisi var mı, `healthy` mi? |
| DisallowedHost | `DJANGO_ALLOWED_HOSTS` domaini içeriyor mu? |

Daha fazla detay: repo kökündeki [DEPLOY.md](../../DEPLOY.md).
