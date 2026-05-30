# Coolify kurulumu (Ghost tarzı — kutudan çıkar çıkmaz)

## ÖNEMLİ: Docker Compose build pack

Coolify'da **Dockerfile** build pack ile kurarsanız volume bağlanmaz ve uygulama bilinçli olarak durur.

| Ayar | Doğru değer |
|------|-------------|
| Build Pack | **Docker Compose** |
| Compose path | `docker-compose.yaml` |
| Persistent Storage UI | **Gerekmez** — `gy_data` named volume compose'ta |

## 3 adımda deploy

1. **New Resource** → GitHub → `imyigitcengiz/kobi-ops`
2. Build Pack: **Docker Compose** → path: `docker-compose.yaml` (boş bırakılırsa Coolify bunu arar)
3. **Domains** → servis **`app`**, port **8000**, HTTPS → **Deploy**

`.env` yazmanız gerekmez. İlk giriş: **admin** / **admin**.

## Volume (otomatik)

Compose tanımı:

```yaml
volumes:
  - gy_data:/data
```

Coolify named volume `kobiops_gy_data` oluşturur. Rebuild'de **volume silmeyin**.

## Sorun: `/data kalıcı volume olarak bağlı değil`

1. Build Pack **Docker Compose** mi? (Dockerfile değil)
2. Compose path repo kökündeki `docker-compose.yaml` mi?
3. Redeploy → Logs'ta `Kalıcı veri kontrolü OK` görünmeli

Hâlâ hata: Coolify → Preview Compose → `gy_data:/data` satırı var mı?

## İsteğe bağlı Environment

İsteğe bağlı override: repo kökündeki [`.env.example`](../../.env.example)

Genel: [DEPLOY.md](../../DEPLOY.md)
