# CoolOPS

**KOBİ’ler için müşteri, satış ve saha servis operasyon paneli.**

Django tabanlı hafif CRM: müşteri rehberi, satış kayıtları, servis / iş emri takibi, WhatsApp entegrasyonu ve ekip araçları. Her kurulum kendi sunucusunda bağımsız çalışır (tek kiracı).

## Modüller

| Modül | Açıklama |
|--------|----------|
| **Rehber** | Müşteriler, firmalar, ekip ve personel |
| **Satış Birimi** | Proje bazlı satış kayıtları ve raporlar |
| **Yardım Masası** | Servis kayıtları, durum, öncelik, saha yazdırma |
| **Tools** | WhatsApp köprüsü, AI paneli, yedekleme, medya |

## Üretim

**[DEPLOY.md](DEPLOY.md)** — Coolify / Dokploy / 1Panel tak-çalıştır Docker Compose.

```bash
git clone https://github.com/imyigitcengiz/kobi-ops.git /opt/kobi-ops
cd /opt/kobi-ops
./deploy/install.sh          # secret + host otomatik
# ./deploy/install.sh panel.firma.com   # domain ile HTTPS ayarları
```

- Kalıcı veri: volume `/data`
- WhatsApp: `whatsapp_bridge` servisi (`docker-compose.yaml` ile otomatik)

| Platform | Rehber |
|----------|--------|
| Dokploy | [deploy/dokploy/README.md](deploy/dokploy/README.md) |
| Coolify | [deploy/coolify/README.md](deploy/coolify/README.md) |
| 1Panel | [deploy/1panel/README.md](deploy/1panel/README.md) |

## Yerel geliştirme

```bash
git clone https://github.com/imyigitcengiz/kobi-ops.git
cd kobi-ops
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

WhatsApp (yerel): `runserver` / `daphne` açılınca Django köprüyü otomatik başlatır (`npm install` dahil).  
Kapatmak: `DJANGO_WHATSAPP_BRIDGE_AUTO_START=0`. Docker’da ayrı `whatsapp-bridge` servisi kullanın.

## Lisans

Lisans dosyası eklendiğinde bu bölüm güncellenecektir.
