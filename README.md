# KobiOps

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

**[DEPLOY.md](DEPLOY.md)** — Docker Compose, Coolify, 1Panel, ortam değişkenleri, WhatsApp köprüsü.

```bash
git clone https://github.com/imyigitcengiz/kobi-ops.git
cd kobi-ops
docker compose up -d --build
```

- Kalıcı veri: volume `/data`
- WhatsApp: `whatsapp-bridge` servisi (panel ile birlikte `compose.yaml`)

Coolify notları: [deploy/coolify/README.md](deploy/coolify/README.md)

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
