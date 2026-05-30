# Coolify kurulumu (Ghost tarzı — kutudan çıkar çıkmaz)

## ÖNEMLİ: `:8000` tarayıcıda Coolify panelidir

| Adres | Ne açılır |
|-------|-----------|
| `http://SUNUCU-IP:8000` | **Coolify yönetim paneli** |
| `http://xxx.sslip.io` | **KobiOps uygulaması** (Traefik üzerinden) |

Tarayıcıda **asla `:8000` veya `:8080` yazmayın** — sunucunun 8000 portu Coolify'a aittir.

## Build Pack

| Ayar | Değer |
|------|--------|
| Build Pack | **Docker Compose** |
| Compose path | `docker-compose.yaml` |
| Domain servisi | **`app`** |

## Domain kurulumu (404 çözümü)

1. Coolify → servis **`app`** → **Generate Domain** (sslip.io URL üretir)
2. Domain satırında port **80** olmalı, örnek:
   ```text
   http://app-xxxxx.sslip.io:80
   ```
3. **Save** → **Force Rebuild** → **Deploy**
4. Tarayıcıda açın (**port yok**):
   ```text
   http://app-xxxxx.sslip.io/
   ```

`whatsapp_bridge` servisine domain **bağlamayın**.

## Log kontrolü

Deploy sonrası Logs'ta:
```text
daphne 0.0.0.0:80
```
görmelisiniz. `8000` görürseniz eski image — Force Rebuild yapın.

## Exited / volume

Build Pack Dockerfile ise volume bağlanmaz → Compose'a geçin.

Genel: [DEPLOY.md](../../DEPLOY.md)
