# CoolOPS

**Montaj, teknik servis ve B2B satış yapan KOBİ’ler için operasyon paneli.**

Django tabanlı, self-host edilebilir hafif ERP/CRM: müşteri rehberi, yardım masası (servis), muhasebe (maaş/avans, gelir-gider), satış kayıtları, WhatsApp kampanyaları ve rol bazlı erişim — tek veri merkezinde. Her kurulum kendi sunucusunda bağımsız çalışır (tek kiracı, SQLite).

## Kimler için?

- Montaj ve saha teknik servis ekipleri  
- Bayi / çözüm ortağı ağları  
- B2B satış yapan küçük ve orta ölçekli işletmeler  
- WhatsApp ile saha ve müşteri iletişimi yürüten firmalar  

## Modüller

| Modül | Açıklama |
|--------|----------|
| **Panel** (`/panel`) | Rehber, muhasebe, yardım masası ve iletişim merkezi kısayolları; dönem özeti ve KPI kartları |
| **Rehber** | Müşteriler, firma rehberi, Maps kazıma, ekipler |
| **Muhasebe** | Personel yönetimi, maaş & avans (döngü işlem, net = brüt − avans), gelir-gider, satış kayıtları, raporlar |
| **Yardım Masası** | Servis kayıtları, durum/öncelik, toplu işlem, yazdırma, WhatsApp dağıtım |
| **İletişim Merkezi** | Kampanyalar, toplu WhatsApp, mesaj geçmişi |
| **Tools** | WhatsApp köprüsü, medya kütüphanesi, AI ayarları, yedekleme |
| **Modül Merkezi** (`/panel/moduller/`) | Sektör profili (KOBİ, ajans, …), modül kur/kapat, URL kilidi |
| **Ajans Çalışma Alanı** (`/panel/ajans/`) | Retainer/proje panosu — ajans paketi ile (beta) |

### Öne çıkan özellikler

- **Personel & maaş:** `/muhasebe/personel/` — kayıt, ekip, maaş tarihi; `/muhasebe/maas-avans/` — avans mahsubu ve aylık net ödeme  
- **RBAC:** Muhasebe, satış, servis, operasyon rolleri; `python manage.py test_rbac` ile senaryo testleri  
- **WhatsApp:** Ayrı `whatsapp_bridge` servisi (Docker) veya yerel otomatik köprü  
- **Deploy:** Coolify, Dokploy, 1Panel — tak-çalıştır Compose, kalıcı volume `/data`  

## Hızlı başlangıç (Docker — önerilen)

```bash
git clone https://github.com/imyigitcengiz/kobi-ops.git /opt/kobi-ops
cd /opt/kobi-ops
./deploy/install.sh
# veya domain ile:
# ./deploy/install.sh panel.firma.com
```

Detaylı üretim rehberi: **[DEPLOY.md](DEPLOY.md)**

| Platform | Rehber |
|----------|--------|
| Dokploy | [deploy/dokploy/README.md](deploy/dokploy/README.md) |
| Coolify | [deploy/coolify/README.md](deploy/coolify/README.md) |
| 1Panel | [deploy/1panel/README.md](deploy/1panel/README.md) |

İlk giriş (varsayılan üretim): `admin` / `admin` — hemen değiştirin.

## Yerel geliştirme

```bash
git clone https://github.com/imyigitcengiz/kobi-ops.git
cd kobi-ops
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py sync_permissions --reset-system-roles
python manage.py runserver
```

Tarayıcı: `http://127.0.0.1:8000/`

### Faydalı komutlar

```bash
python manage.py test_rbac              # rol bazlı URL erişim testleri
python manage.py sync_permissions --reset-system-roles
python manage.py check
```

### WhatsApp (yerel)

`runserver` açılınca Django köprüyü otomatik başlatabilir (`npm install` dahil).  
Kapatmak: `DJANGO_WHATSAPP_BRIDGE_AUTO_START=0`.  
Üretimde ayrı `whatsapp_bridge` servisi kullanın (`docker-compose.yaml`).

## URL yapısı (özet)

| Yol | İçerik |
|-----|--------|
| `/panel/` | Ana panel (modül kısayolları) |
| `/contact/` | Rehber |
| `/muhasebe/` | Muhasebe modülü |
| `/muhasebe/personel/` | Personel yönetimi |
| `/muhasebe/maas-avans/` | Maaş & avans |
| `/services-dashboard/` | Yardım masası |
| `/iletisim/` | İletişim merkezi |
| `/tools/` | Araçlar |

## Teknoloji

- Python 3 / Django 5  
- SQLite (tek kiracı), medya `/data/media`  
- Tailwind (CDN), Docker Compose  
- Node.js WhatsApp köprüsü (Chromium)  

## Katkı ve lisans

Katkılar issue ve pull request ile welcome. Lisans dosyası eklendiğinde bu bölüm güncellenecektir.

## Depo

[github.com/imyigitcengiz/kobi-ops](https://github.com/imyigitcengiz/kobi-ops)
