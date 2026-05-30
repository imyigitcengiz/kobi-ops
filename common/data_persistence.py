"""Üretimde SQLite verisinin kalıcı volume üzerinde olduğunu doğrular; otomatik yedek alır."""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

MARKER_FILENAME = '.gy_persistence_marker.json'
AUTO_BACKUP_SUBDIR = Path('backups') / 'auto'
MAX_AUTO_BACKUPS = 10
MIN_MEANINGFUL_DB_BYTES = 8192


class DataPersistenceError(Exception):
    """Kalıcı veri güvenliği ihlali — konteyner başlatmayı durdurur."""


def _truthy(name: str, default: str = '0') -> bool:
    return os.environ.get(name, default).strip().lower() in ('1', 'true', 'yes')


def is_containerized_production() -> bool:
    return bool(os.environ.get('DATA_DIR', '').strip() or os.environ.get('DJANGO_DB_PATH', '').strip())


def db_path() -> Path:
    return Path(settings.DATABASES['default']['NAME'])


def data_root() -> Path:
    env = os.environ.get('DATA_DIR', '').strip()
    if env:
        return Path(env)
    db = db_path()
    if db.parent.name == 'data' or str(db).startswith('/data'):
        return db.parent
    return db.parent


def marker_path(root: Path | None = None) -> Path:
    return (root or data_root()) / MARKER_FILENAME


def require_persistent_volume() -> bool:
    if not is_containerized_production():
        return False
    if _truthy('GY_ALLOW_EPHEMERAL_DATA'):
        return False
    default = '1' if os.environ.get('DATA_DIR', '').strip() else '0'
    return _truthy('GY_REQUIRE_PERSISTENT_VOLUME', default)


def _normalize_mount_path(path: str) -> str:
    p = path.rstrip('/') or '/'
    return p


def _is_mount_point(path: Path) -> bool:
    """Docker named volume veya bind mount — parent'tan farklı cihaz."""
    try:
        path = path.resolve()
        parent = path.parent
        if parent == path:
            return True
        return os.lstat(path).st_dev != os.lstat(parent).st_dev
    except OSError:
        return False


def _is_listed_in_mountinfo(path: Path) -> bool:
    """/proc/self/mountinfo — Coolify bind mount edge case'leri."""
    target = _normalize_mount_path(str(path.resolve()))
    try:
        with open('/proc/self/mountinfo', encoding='utf-8') as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 5:
                    mountpoint = _normalize_mount_path(parts[4])
                    if mountpoint == target:
                        return True
    except OSError:
        return False
    return False


def _is_listed_in_mounts(path: Path) -> bool:
    """/proc/mounts — ek doğrulama (overlay / named volume)."""
    target = _normalize_mount_path(str(path.resolve()))
    try:
        with open('/proc/mounts', encoding='utf-8') as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2:
                    mountpoint = _normalize_mount_path(parts[1])
                    if mountpoint == target:
                        return True
    except OSError:
        return False
    return False


def data_dir_is_persistent(root: Path) -> bool:
    """True when /data is a real mount (compose named volume, panel bind mount, vb.)."""
    root = root.resolve()
    if _is_mount_point(root):
        return True
    if _is_listed_in_mountinfo(root):
        return True
    if _is_listed_in_mounts(root):
        return True
    return False


def data_dir_looks_ephemeral(root: Path) -> bool:
    """True yalnızca /data konteyner katmanında düz klasörse (volume yok)."""
    return not data_dir_is_persistent(root)


def _persistence_error_message(root: Path) -> str:
    in_coolify = bool(
        os.environ.get('COOLIFY_RESOURCE_UUID')
        or os.environ.get('COOLIFY_FQDN')
        or os.environ.get('SERVICE_FQDN_APP')
    )
    in_dokploy = bool(os.environ.get('DOKPLOY_DEPLOY_URL') or os.environ.get('DOKPLOY_IS_PREVIEW'))

    base = (
        'KRİTİK: /data kalıcı volume olarak bağlı değil — rebuild/deploy tüm kayıtları siler.\n'
        f'  Algılanan yol: {root}\n'
    )
    if in_coolify:
        return base + (
            '  Coolify çözümü: Build Pack = Docker Compose (Dockerfile değil).\n'
            '  Compose path: docker-compose.yaml (repo kökü).\n'
            '  Named volume compose içinde tanımlıdır; Persistent Storage UI gerekmez.\n'
            '  Redeploy sonrası hâlâ hata: Logs → compose volume gy_data:/data uygulandı mı?'
        )
    if in_dokploy:
        return base + (
            '  Dokploy çözümü: Docker Compose modu, compose path docker-compose.yaml.\n'
            '  Named volume gy_data otomatik oluşur; deploy sırasında volume silmeyin.'
        )
    return base + (
        '  Çözüm: docker compose up ile gy_data:/data volume bağlayın.\n'
        '  Geçici test: GY_ALLOW_EPHEMERAL_DATA=1 (üretimde kullanmayın).'
    )


def _load_marker(root: Path) -> dict | None:
    path = marker_path(root)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None


def _db_record_count(path: Path) -> int | None:
    if not path.is_file() or path.stat().st_size < 512:
        return None
    try:
        conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
        try:
            cur = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            if cur.fetchone()[0] == 0:
                return 0
            cur = conn.execute('SELECT COUNT(*) FROM auth_user')
            return int(cur.fetchone()[0])
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def write_persistence_marker(root: Path | None = None) -> dict:
    root = root or data_root()
    db = db_path()
    payload = {
        'version': 1,
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'db_path': str(db),
        'db_bytes': db.stat().st_size if db.is_file() else 0,
        'auth_user_count': _db_record_count(db),
    }
    root.mkdir(parents=True, exist_ok=True)
    marker_path(root).write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return payload


def auto_backup_sqlite(root: Path | None = None) -> Path | None:
    """migrate öncesi mevcut db.sqlite3 kopyası (volume içinde)."""
    db = db_path()
    if not db.is_file() or db.stat().st_size < 512:
        return None

    root = root or data_root()
    backup_dir = root / AUTO_BACKUP_SUBDIR
    backup_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    dest = backup_dir / f'db-{ts}.sqlite3'
    shutil.copy2(db, dest)

    for side in ('-wal', '-shm'):
        side_src = Path(str(db) + side)
        if side_src.is_file():
            shutil.copy2(side_src, backup_dir / f'db-{ts}.sqlite3{side}')

    latest = backup_dir / 'latest.sqlite3'
    shutil.copy2(db, latest)

    backups = sorted(backup_dir.glob('db-*.sqlite3'), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[MAX_AUTO_BACKUPS:]:
        old.unlink(missing_ok=True)

    logger.info('SQLite otomatik yedek: %s (%s bayt)', dest, db.stat().st_size)
    return dest


def check_before_migrate() -> None:
    if not is_containerized_production():
        return

    root = data_root()
    db = db_path()
    marker = _load_marker(root)

    if require_persistent_volume() and data_dir_looks_ephemeral(root):
        raise DataPersistenceError(_persistence_error_message(root))

    if marker:
        prev_bytes = int(marker.get('db_bytes') or 0)
        prev_users = marker.get('auth_user_count')
        current_bytes = db.stat().st_size if db.is_file() else 0

        if prev_bytes >= MIN_MEANINGFUL_DB_BYTES and current_bytes < MIN_MEANINGFUL_DB_BYTES:
            backup_hint = root / AUTO_BACKUP_SUBDIR / 'latest.sqlite3'
            raise DataPersistenceError(
                'KRİTİK: Veri kaybı algılandı — önceki db.sqlite3 kayboldu veya boşaltıldı. '
                f'Önceki boyut: {prev_bytes} bayt, şimdi: {current_bytes}. '
                f'Volume /data silinmiş olabilir. '
                f'Yedek varsa geri yükleyin: {backup_hint} → {db}'
            )

        if prev_users and int(prev_users) > 1:
            current_users = _db_record_count(db)
            if current_users is not None and current_users == 0:
                raise DataPersistenceError(
                    'KRİTİK: Veritabanı boş görünüyor (kullanıcı kaydı yok). '
                    'Rebuild öncesi /data volume kaybolmuş olabilir.'
                )

    if db.is_file() and db.stat().st_size >= MIN_MEANINGFUL_DB_BYTES:
        auto_backup_sqlite(root)


def check_after_migrate() -> dict | None:
    if not is_containerized_production():
        return None
    return write_persistence_marker(data_root())
