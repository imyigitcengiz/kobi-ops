import gzip
import json
import os
import shutil
from datetime import datetime
from io import StringIO
from tempfile import NamedTemporaryFile

import django
from django.conf import settings
from django.core import management
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone

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


def _sync_permissions_after_restore():
    try:
        management.call_command('sync_permissions', verbosity=0)
    except Exception:
        pass


def import_backup_file(uploaded) -> tuple[bool, str]:
    if not uploaded:
        return False, 'Lütfen bir dosya seçin.'

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
        with transaction.atomic():
            management.call_command('loaddata', tmp_fixture, verbosity=0)

        _sync_permissions_after_restore()

        if meta:
            mig_count = meta.get('migration_count', len(meta.get('migrations', [])))
            rec_count = meta.get('record_count', len(fixture))
            created = meta.get('created_at', '')
            return True, (
                f'Yedek geri yüklendi ({rec_count} kayıt). '
                f'Migration senkronu tamamlandı ({mig_count} migration kaydı yedekte). '
                f'{f"Yedek tarihi: {created[:19]}" if created else ""}'
            ).strip()

        return True, (
            f'Eski format yedek içe aktarıldı ({len(fixture)} kayıt). '
            'Önce migrate, ardından veri yükleme uygulandı.'
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


def backup_status_summary() -> dict:
    migrations = _applied_migrations()
    return {
        'migration_count': len(migrations),
        'migrations': migrations[-8:],  # son 8 satır önizleme
        'format_version': BACKUP_FORMAT_V2,
    }
