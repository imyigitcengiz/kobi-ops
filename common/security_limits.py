"""Ortak güvenlik sınırları (yedek yükleme, vb.)."""

import os

# JSON/SQLite yedek içe aktarma üst sınırı (varsayılan 500 MB)
MAX_BACKUP_UPLOAD_BYTES = int(os.environ.get('GY_BACKUP_MAX_UPLOAD_BYTES', 500 * 1024 * 1024))
