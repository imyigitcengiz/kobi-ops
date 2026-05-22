"""MEDIA_ROOT taraması + veritabanı kayıtlarını birleştiren medya kataloğu."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from common.media_files import classify_media_kind, kind_label

CATEGORY_LABELS = {
    'service': 'Servis / Arıza',
    'contract': 'Sözleşme & Belge',
    'customer': 'Müşteri dosyası',
    'scan': 'Tarama',
    'profile': 'Profil',
    'site': 'Site',
    'other': 'Diğer',
}

CONTRACT_HINTS = ('sozlesme', 'sözleşme', 'contract', 'belge', 'evrak', 'agreement')
SCAN_HINTS = ('tarama', 'scan', 'scanned', 'tarandi')


@dataclass
class MediaItem:
    relpath: str
    url: str
    name: str
    category: str
    kind: str  # image | video | audio | document | archive | other
    size: int
    modified_at: datetime | None
    source: str  # database | filesystem
    record_type: str | None
    record_id: int | None
    title: str
    subtitle: str
    customer_name: str | None
    service_id: int | None
    link_url: str | None
    can_delete: bool
    category_label: str = ''
    kind_label: str = ''
    size_display: str = ''


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _normalize_relpath(path: str) -> str:
    return path.replace('\\', '/').lstrip('/')


def _classify_category(relpath: str) -> str:
    lower = _normalize_relpath(relpath).lower()
    parts = lower.split('/')
    joined = '/'.join(parts)

    if joined.startswith('services/'):
        return 'service'
    if joined.startswith('profiles/'):
        return 'profile'
    if joined.startswith('site/'):
        return 'site'
    if joined.startswith('customers/'):
        if '/sozlesme/' in joined:
            return 'contract'
        if '/servis/' in joined:
            return 'service'
        return 'customer'
    if any(joined.startswith(p) for p in ('contracts/', 'sozlesme/', 'belgeler/', 'documents/')):
        return 'contract'

    blob = lower.replace('/', ' ')
    if any(h in blob for h in CONTRACT_HINTS):
        return 'contract'
    if any(h in blob for h in SCAN_HINTS):
        return 'scan'
    if joined.startswith(('scans/', 'tarama/', 'taramalar/')):
        return 'scan'
    return 'other'


def _format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f'{num_bytes} B'
    if num_bytes < 1024 * 1024:
        return f'{num_bytes / 1024:.1f} KB'
    return f'{num_bytes / (1024 * 1024):.1f} MB'


def _safe_resolve(relpath: str) -> Path | None:
    root = _media_root()
    if not root.exists():
        return None
    target = (root / _normalize_relpath(relpath)).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


def _build_db_index() -> dict[str, dict]:
    from core_settings.models import SiteSettings
    from customers.models import CustomerMedia
    from services.models import ServiceImage
    from users.models import UserProfile

    index: dict[str, dict] = {}

    scope_category = {
        CustomerMedia.SCOPE_SERVICE: 'service',
        CustomerMedia.SCOPE_CONTRACT: 'contract',
        CustomerMedia.SCOPE_CUSTOMER: 'customer',
    }
    scope_title = {
        CustomerMedia.SCOPE_SERVICE: 'Servis dosyası',
        CustomerMedia.SCOPE_CONTRACT: 'Sözleşme / belge',
        CustomerMedia.SCOPE_CUSTOMER: 'Müşteri dosyası',
    }

    for media in CustomerMedia.objects.select_related('customer', 'service'):
        if not media.file:
            continue
        rel = _normalize_relpath(media.file.name)
        size_note = ''
        if media.file_size_original and media.file_size_stored and media.compress_method:
            size_note = f' · {media.compress_method}'
        index[rel] = {
            'source': 'database',
            'record_type': 'customer_media',
            'record_id': media.pk,
            'title': media.title or scope_title.get(media.scope, 'Dosya'),
            'subtitle': f'{media.customer.name} · {media.scope_label}{size_note}',
            'customer_name': media.customer.name,
            'service_id': media.service_id,
            'link_url': (
                f'/services-dashboard/services/{media.service_id}/duzenle/'
                if media.service_id
                else f'/contact/musteriler/{media.customer_id}/duzenle/'
            ),
            'can_delete': True,
            'created_at': media.created_at,
            'forced_category': scope_category.get(media.scope),
        }

    for img in ServiceImage.objects.select_related(
        'service', 'service__customer', 'service__status',
    ):
        if not img.image:
            continue
        rel = _normalize_relpath(img.image.name)
        customer = img.service.customer
        index[rel] = {
            'source': 'database',
            'record_type': 'service_image',
            'record_id': img.pk,
            'title': f'Servis #{img.service_id}',
            'subtitle': customer.name if customer else '',
            'customer_name': customer.name if customer else None,
            'service_id': img.service_id,
            'link_url': f'/services-dashboard/services/{img.service_id}/duzenle/',
            'can_delete': True,
            'created_at': img.created_at,
        }

    settings_obj = SiteSettings.objects.exclude(logo='').exclude(logo__isnull=True).first()
    if settings_obj and settings_obj.logo:
        rel = _normalize_relpath(settings_obj.logo.name)
        index[rel] = {
            'source': 'database',
            'record_type': 'site_logo',
            'record_id': settings_obj.pk,
            'title': 'Site logosu',
            'subtitle': settings_obj.site_name,
            'customer_name': None,
            'service_id': None,
            'link_url': '/services-dashboard/settings/',
            'can_delete': True,
            'created_at': None,
        }

    for profile in UserProfile.objects.select_related('user').exclude(avatar='').exclude(avatar__isnull=True):
        rel = _normalize_relpath(profile.avatar.name)
        index[rel] = {
            'source': 'database',
            'record_type': 'user_avatar',
            'record_id': profile.pk,
            'title': profile.user.display_name if hasattr(profile.user, 'display_name') else profile.user.username,
            'subtitle': 'Profil fotoğrafı',
            'customer_name': None,
            'service_id': None,
            'link_url': '/profil/',
            'can_delete': True,
            'created_at': None,
        }

    return index


def scan_media_library(
    *,
    query: str = '',
    category: str = '',
    kind: str = '',
    page: int = 1,
    per_page: int = 48,
) -> dict:
    root = _media_root()
    db_index = _build_db_index()
    items: list[MediaItem] = []
    seen: set[str] = set()

    if root.exists():
        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                if filename.startswith('.'):
                    continue
                full = Path(dirpath) / filename
                try:
                    rel = _normalize_relpath(str(full.relative_to(root)))
                except ValueError:
                    continue
                if rel in seen:
                    continue
                seen.add(rel)

                stat = full.stat()
                meta = db_index.get(rel, {})
                item_category = meta.get('forced_category') or _classify_category(rel)
                if category and item_category != category:
                    continue

                file_kind = classify_media_kind(filename)
                if kind and file_kind != kind:
                    continue

                q = (query or '').strip().lower()
                if q:
                    hay = ' '.join([
                        rel.lower(),
                        filename.lower(),
                        (meta.get('title') or '').lower(),
                        (meta.get('subtitle') or '').lower(),
                        (meta.get('customer_name') or '').lower(),
                    ])
                    if q not in hay:
                        continue

                modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.get_current_timezone())
                items.append(
                    MediaItem(
                        relpath=rel,
                        url=f'{settings.MEDIA_URL}{rel}',
                        name=filename,
                        category=item_category,
                        kind=file_kind,
                        size=stat.st_size,
                        modified_at=modified,
                        source=meta.get('source', 'filesystem'),
                        record_type=meta.get('record_type'),
                        record_id=meta.get('record_id'),
                        title=meta.get('title') or filename,
                        subtitle=meta.get('subtitle') or rel,
                        customer_name=meta.get('customer_name'),
                        service_id=meta.get('service_id'),
                        link_url=meta.get('link_url'),
                        can_delete=meta.get('can_delete', True),
                        category_label=CATEGORY_LABELS.get(item_category, 'Diğer'),
                        kind_label=kind_label(file_kind),
                        size_display=_format_size(stat.st_size),
                    )
                )

    items.sort(key=lambda x: x.modified_at or datetime.min.replace(tzinfo=timezone.get_current_timezone()), reverse=True)

    total = len(items)
    page = max(1, page)
    per_page = max(12, min(per_page, 96))
    start = (page - 1) * per_page
    page_items = items[start:start + per_page]

    counts_by_category: dict[str, int] = {}
    counts_by_kind: dict[str, int] = {}
    total_size = 0
    for it in items:
        counts_by_category[it.category] = counts_by_category.get(it.category, 0) + 1
        counts_by_kind[it.kind] = counts_by_kind.get(it.kind, 0) + 1
        total_size += it.size

    category_stats = [
        {
            'key': key,
            'label': label,
            'count': counts_by_category.get(key, 0),
        }
        for key, label in CATEGORY_LABELS.items()
    ]

    return {
        'items': page_items,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': max(1, (total + per_page - 1) // per_page),
        'counts_by_category': counts_by_category,
        'counts_by_kind': counts_by_kind,
        'category_stats': category_stats,
        'total_size': total_size,
        'total_size_display': _format_size(total_size),
        'category_labels': CATEGORY_LABELS,
        'has_media_root': root.exists(),
    }


def delete_media_item(*, record_type: str | None, record_id: int | None, relpath: str) -> tuple[bool, str]:
    rel = _normalize_relpath(relpath)
    path = _safe_resolve(rel)
    if not path or not path.is_file():
        return False, 'Dosya bulunamadı.'

    if record_type == 'service_image' and record_id:
        from services.models import ServiceImage

        obj = ServiceImage.objects.filter(pk=record_id).first()
        if obj:
            if obj.image:
                obj.image.delete(save=False)
            obj.delete()
            return True, 'Servis görseli silindi.'

    if record_type == 'customer_media' and record_id:
        from customers.models import CustomerMedia

        obj = CustomerMedia.objects.filter(pk=record_id).first()
        if obj:
            if obj.file:
                obj.file.delete(save=False)
            obj.delete()
            return True, 'Müşteri medyası silindi.'

    if record_type == 'site_logo' and record_id:
        from core_settings.models import SiteSettings

        obj = SiteSettings.objects.filter(pk=record_id).first()
        if obj and obj.logo:
            obj.logo.delete(save=True)
            return True, 'Site logosu kaldırıldı.'

    if record_type == 'user_avatar' and record_id:
        from users.models import UserProfile

        obj = UserProfile.objects.filter(pk=record_id).first()
        if obj and obj.avatar:
            obj.avatar.delete(save=True)
            return True, 'Profil fotoğrafı kaldırıldı.'

    if record_type is None:
        os.remove(path)
        return True, 'Dosya silindi.'

    return False, 'Bu kayıt silinemiyor.'
