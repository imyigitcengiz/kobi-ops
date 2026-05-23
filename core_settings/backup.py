import gzip
import json
import os
import shutil
import sqlite3
from datetime import datetime
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile

import django
from django.conf import settings
from django.core import management
from django.db import connections, transaction
from django.http import FileResponse, HttpResponse
from django.utils import timezone

from common.security_limits import MAX_BACKUP_UPLOAD_BYTES

SQLITE_MAGIC = b'SQLite format 3\x00'

BACKUP_FORMAT_V2 = 'gy-dashboard-backup-v2'


def _applied_migrations():
    """Veritabanındaki uygulanmış migration kayıtları."""
    from django.db.migrations.recorder import MigrationRecorder

    rows = MigrationRecorder.Migration.objects.order_by('app', 'name')
    return [
        {
            'app': row.app,
            'name': row.name,
            'applied': row.applied.isoformat() if row.applied else None,
        }
        for row in rows
    ]


def _dump_fixture_json() -> list:
    """Tüm uygulama verisini fixture listesi olarak döndürür."""
    sio = StringIO()
    management.call_command(
        'dumpdata',
        stdout=sio,
        indent=2,
        natural_foreign=True,
        natural_primary=True,
        exclude=['contenttypes', 'auth.permission'],
    )
    sio.seek(0)
    return json.loads(sio.read())


def _build_backup_payload() -> dict:
    migrations = _applied_migrations()
    fixture = _dump_fixture_json()
    return {
        'format': BACKUP_FORMAT_V2,
        'created_at': timezone.now().isoformat(),
        'django_version': django.get_version(),
        'database': str(settings.DATABASES.get('default', {}).get('NAME', '')),
        'migration_count': len(migrations),
        'migrations': migrations,
        'record_count': len(fixture),
        'fixture': fixture,
    }


def export_backup_response() -> HttpResponse:
    payload = _build_backup_payload()
    raw_json = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    file_name = f'gy-dashboard-backup-{ts}.json.gz'
    response = HttpResponse(gzip.compress(raw_json), content_type='application/gzip')
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'
    return response


def _parse_backup_file(path: str, *, is_gzip: bool) -> tuple[dict | None, list]:
    """(meta, fixture) — meta None ise eski düz fixture listesi."""
    if is_gzip:
        with gzip.open(path, 'rt', encoding='utf-8') as handle:
            data = json.load(handle)
    else:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)

    if isinstance(data, list):
        return None, data
    if isinstance(data, dict) and data.get('format') == BACKUP_FORMAT_V2:
        fixture = data.get('fixture')
        if not isinstance(fixture, list):
            raise ValueError('Yedek dosyasında fixture verisi bulunamadı.')
        return data, fixture
    if isinstance(data, dict) and 'fixture' in data:
        fixture = data.get('fixture')
        if isinstance(fixture, list):
            return data, fixture
    raise ValueError('Tanınmayan yedek dosyası formatı.')


def _write_fixture_temp(fixture: list) -> str:
    tmp = NamedTemporaryFile(delete=False, suffix='.json', mode='w', encoding='utf-8')
    json.dump(fixture, tmp, ensure_ascii=False, indent=2)
    tmp.flush()
    tmp.close()
    return tmp.name


def _run_migrations():
    management.call_command('migrate', '--noinput', verbosity=0)


def _prepare_database_for_fixture_load():
    """
    migrate sonrası migration/seed ile oluşan izinleri kaldırır.
    loaddata yedekteki Permission kayıtlarını UNIQUE codename hatası olmadan yükler.
    """
    from users.models import Permission

    Permission.objects.all().delete()


def _flush_database_for_full_restore():
    """JSON yedeği mevcut verinin üzerine karıştırmadan tam yüklemek için tabloları boşaltır."""
    _close_db_connections()
    management.call_command('flush', '--noinput', verbosity=0)


def _data_counts_summary() -> str:
    from customers.models import Customer, CustomerMedia
    from services.models import ServiceRecord, ServiceImage
    from sales_leads.models import SalesLead

    parts = [
        f'{Customer.objects.count()} müşteri',
        f'{ServiceRecord.objects.count()} servis',
        f'{SalesLead.objects.count()} satış',
        f'{CustomerMedia.objects.count()} medya kaydı',
        f'{ServiceImage.objects.count()} servis görseli',
    ]
    return ', '.join(parts)


def _sync_permissions_after_restore():
    try:
        management.call_command('sync_permissions', verbosity=0)
    except Exception:
        pass


def _upload_too_large(uploaded) -> bool:
    size = getattr(uploaded, 'size', None)
    if size is not None and size > MAX_BACKUP_UPLOAD_BYTES:
        return True
    return False


def import_backup_file(uploaded) -> tuple[bool, str]:
    if not uploaded:
        return False, 'Lütfen bir dosya seçin.'
    if _upload_too_large(uploaded):
        limit_mb = MAX_BACKUP_UPLOAD_BYTES // (1024 * 1024)
        return False, f'Dosya çok büyük (en fazla {limit_mb} MB).'

    filename = (uploaded.name or '').lower()
    if not (filename.endswith('.json') or filename.endswith('.json.gz')):
        return False, 'Sadece .json veya .json.gz dosyaları içe aktarılabilir.'

    tmp_input = None
    tmp_json = None
    tmp_fixture = None
    try:
        is_gzip = filename.endswith('.json.gz')
        tmp_suffix = '.json.gz' if is_gzip else '.json'
        tmp_input = NamedTemporaryFile(delete=False, suffix=tmp_suffix)
        for chunk in uploaded.chunks():
            tmp_input.write(chunk)
        tmp_input.flush()
        tmp_input.close()

        parse_path = tmp_input.name
        if is_gzip:
            tmp_json = NamedTemporaryFile(delete=False, suffix='.json')
            with gzip.open(tmp_input.name, 'rb') as gz_file, open(tmp_json.name, 'wb') as out_file:
                shutil.copyfileobj(gz_file, out_file)
            parse_path = tmp_json.name
        else:
            tmp_json = None

        meta, fixture = _parse_backup_file(parse_path, is_gzip=False)
        tmp_fixture = _write_fixture_temp(fixture)

        # migrate transaction dışında (SQLite ve PostgreSQL uyumluluğu)
        _run_migrations()
        _flush_database_for_full_restore()
        _prepare_database_for_fixture_load()
        with transaction.atomic():
            management.call_command('loaddata', tmp_fixture, verbosity=0)

        _sync_permissions_after_restore()
        counts = _data_counts_summary()
        media_note = (
            ' Yüklenen dosyalar (resim/belge) media/ klasöründe — '
            'sunucuda /data/media kopyalanmadıysa medya kırık görünür.'
        )

        if meta:
            mig_count = meta.get('migration_count', len(meta.get('migrations', [])))
            rec_count = meta.get('record_count', len(fixture))
            created = meta.get('created_at', '')
            return True, (
                f'JSON yedek tam yüklendi (fixture: {rec_count} kayıt; DB: {counts}). '
                f'Migration senkronu tamamlandı ({mig_count} migration kaydı yedekte). '
                f'{f"Yedek tarihi: {created[:19]}." if created else ""}'
                f'{media_note}'
            ).strip()

        return True, (
            f'JSON yedek yüklendi (fixture: {len(fixture)} kayıt; DB: {counts}).'
            f'{media_note}'
        )
    except Exception as exc:
        return False, f'İçe aktarma sırasında hata oluştu: {exc}'
    finally:
        if tmp_input and os.path.exists(tmp_input.name):
            os.unlink(tmp_input.name)
        if tmp_json and os.path.exists(tmp_json.name):
            os.unlink(tmp_json.name)
        if tmp_fixture and os.path.exists(tmp_fixture):
            os.unlink(tmp_fixture)


def database_path() -> Path:
    return Path(settings.DATABASES['default']['NAME']).resolve()


def _close_db_connections():
    connections.close_all()


def _validate_sqlite_file(path: str | Path) -> None:
    path = Path(path)
    if path.stat().st_size < 100:
        raise ValueError('Dosya çok küçük veya boş.')
    with open(path, 'rb') as handle:
        if handle.read(16) != SQLITE_MAGIC:
            raise ValueError('Geçerli bir SQLite veritabanı dosyası değil (db.sqlite3 bekleniyor).')
    try:
        conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
        conn.execute('PRAGMA schema_version')
        conn.close()
    except sqlite3.DatabaseError as exc:
        raise ValueError(f'SQLite dosyası okunamadı: {exc}') from exc


def _remove_sqlite_sidecars(db_path: Path) -> None:
    for suffix in ('-wal', '-journal', '-shm'):
        sidecar = Path(f'{db_path}{suffix}')
        if sidecar.exists():
            sidecar.unlink()


def _backup_existing_db(db_path: Path) -> str | None:
    if not db_path.is_file():
        return None
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_path = db_path.with_name(f'{db_path.name}.bak-{ts}')
    shutil.copy2(db_path, backup_path)
    return str(backup_path)


def export_sqlite_response() -> HttpResponse:
    db_path = database_path()
    if not db_path.is_file():
        raise FileNotFoundError('Veritabanı dosyası bulunamadı.')

    _close_db_connections()
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    filename = f'gy-dashboard-{ts}.sqlite3'
    response = FileResponse(
        open(db_path, 'rb'),
        as_attachment=True,
        filename=filename,
        content_type='application/x-sqlite3',
    )
    response['Content-Length'] = db_path.stat().st_size
    return response


def import_sqlite_file(uploaded) -> tuple[bool, str]:
    if not uploaded:
        return False, 'Lütfen bir db.sqlite3 dosyası seçin.'
    if _upload_too_large(uploaded):
        limit_mb = MAX_BACKUP_UPLOAD_BYTES // (1024 * 1024)
        return False, f'Dosya çok büyük (en fazla {limit_mb} MB).'

    name = (uploaded.name or '').lower()
    if not (name.endswith('.sqlite3') or name.endswith('.db')):
        return False, 'Sadece .sqlite3 veya .db dosyası yüklenebilir.'

    db_path = database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = None
    try:
        tmp = NamedTemporaryFile(delete=False, suffix='.sqlite3')
        tmp_path = tmp.name
        for chunk in uploaded.chunks():
            tmp.write(chunk)
        tmp.flush()
        tmp.close()

        _validate_sqlite_file(tmp_path)

        _close_db_connections()
        prev_backup = _backup_existing_db(db_path)
        _remove_sqlite_sidecars(db_path)

        shutil.copy2(tmp_path, db_path)
        try:
            os.chmod(db_path, 0o644)
        except OSError:
            pass
        _remove_sqlite_sidecars(db_path)
        _close_db_connections()

        _run_migrations()
        _sync_permissions_after_restore()

        size_mb = db_path.stat().st_size / (1024 * 1024)
        counts = _data_counts_summary()
        msg = (
            f'SQLite yüklendi ({size_mb:.1f} MB → {db_path}). '
            f'Veritabanı: {counts}. Migration kontrolü tamamlandı.'
        )
        if prev_backup:
            msg += f' Önceki DB yedeklendi: {prev_backup}'
        msg += (
            ' ÖNEMLİ: Resim/belgeler db.sqlite3 içinde değil; lokal media/ klasörünü '
            'sunucuda /data/media (volume) içine kopyalamazsan dosyalar açılmaz.'
        )
        return True, msg
    except Exception as exc:
        return False, f'SQLite içe aktarma hatası: {exc}'
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        _close_db_connections()


def backup_status_summary() -> dict:
    migrations = _applied_migrations()
    db_path = database_path()
    db_size = db_path.stat().st_size if db_path.is_file() else 0
    return {
        'migration_count': len(migrations),
        'migrations': migrations[-8:],  # son 8 satır önizleme
        'format_version': BACKUP_FORMAT_V2,
        'database_path': str(db_path),
        'database_size': db_size,
        'database_size_display': (
            f'{db_size / (1024 * 1024):.1f} MB' if db_size >= 1024 * 1024
            else f'{db_size / 1024:.1f} KB' if db_size else '—'
        ),
        'database_exists': db_path.is_file(),
    }
