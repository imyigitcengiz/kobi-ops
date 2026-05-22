from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from common.decorators import permission_required
from common.permissions import (
    CUSTOMERS_EDIT_PERM,
    CUSTOMERS_VIEW_PERM,
    SERVICES_MANAGE_PERM,
)
from services.models import ServiceRecord

from common.media_files import classify_media_kind, is_allowed_upload, kind_label

from .models import Customer, CustomerMedia


def _format_bytes(num: int) -> str:
    if num < 1024:
        return f'{num} B'
    if num < 1024 * 1024:
        return f'{num / 1024:.1f} KB'
    return f'{num / (1024 * 1024):.1f} MB'


def _can_view_media(user):
    return user.is_superuser or user.has_any_perm_codename(
        CUSTOMERS_VIEW_PERM, CUSTOMERS_EDIT_PERM, SERVICES_MANAGE_PERM,
    )


def _can_upload_media(user, scope, service=None):
    if user.is_superuser:
        return True
    if scope == CustomerMedia.SCOPE_SERVICE:
        return user.has_perm_codename(SERVICES_MANAGE_PERM)
    return user.has_perm_codename(CUSTOMERS_EDIT_PERM)


def _serialize_media(obj: CustomerMedia) -> dict:
    name = obj.file.name.rsplit('/', 1)[-1] if obj.file else ''
    kind = classify_media_kind(name)
    stored = obj.file_size_stored or 0
    original = obj.file_size_original or stored
    if not stored and obj.file:
        try:
            stored = obj.file.size
        except (OSError, ValueError):
            stored = 0
    if not original:
        original = stored
    saved_pct = None
    if original and stored and original > stored:
        saved_pct = round(100 - (stored / original * 100), 1)

    return {
        'id': obj.pk,
        'scope': obj.scope,
        'scope_label': obj.scope_label,
        'title': obj.title or name,
        'name': name,
        'url': obj.file.url if obj.file else '',
        'kind': kind,
        'kind_label': kind_label(kind),
        'file_size_original': original,
        'file_size_stored': stored,
        'compress_method': obj.compress_method or '',
        'saved_percent': saved_pct,
        'note': obj.note or '',
        'service_id': obj.service_id,
        'customer_id': obj.customer_id,
        'created_at': obj.created_at.strftime('%d.%m.%Y %H:%M'),
        'link_url': (
            f'/services-dashboard/services/{obj.service_id}/duzenle/'
            if obj.service_id else f'/contact/musteriler/{obj.customer_id}/duzenle/'
        ),
    }


@require_http_methods(['GET'])
@permission_required(CUSTOMERS_VIEW_PERM, CUSTOMERS_EDIT_PERM, SERVICES_MANAGE_PERM, any_perm=True)
def customer_media_list_api(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    scope = (request.GET.get('scope') or '').strip()
    service_id = request.GET.get('service_id', '').strip()

    qs = customer.media_files.select_related('service').order_by('-created_at')
    if scope in dict(CustomerMedia.SCOPE_CHOICES):
        qs = qs.filter(scope=scope)
    if service_id.isdigit():
        qs = qs.filter(service_id=int(service_id))

    return JsonResponse({
        'ok': True,
        'items': [_serialize_media(m) for m in qs if m.file],
        'customer': {'id': customer.pk, 'name': customer.name},
    })


@require_http_methods(['POST'])
@permission_required(CUSTOMERS_EDIT_PERM, SERVICES_MANAGE_PERM, any_perm=True)
def customer_media_upload_api(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    scope = (request.POST.get('scope') or CustomerMedia.SCOPE_CUSTOMER).strip()
    if scope not in dict(CustomerMedia.SCOPE_CHOICES):
        return JsonResponse({'ok': False, 'error': 'Geçersiz medya kategorisi.'}, status=400)

    service = None
    service_id = (request.POST.get('service_id') or '').strip()
    if scope == CustomerMedia.SCOPE_SERVICE:
        if not service_id.isdigit():
            return JsonResponse({'ok': False, 'error': 'Servis dosyası için kayıtlı servis gerekli.'}, status=400)
        service = get_object_or_404(ServiceRecord, pk=int(service_id), customer_id=customer.pk)
    elif service_id.isdigit():
        service = ServiceRecord.objects.filter(pk=int(service_id), customer_id=customer.pk).first()

    if not _can_upload_media(request.user, scope, service):
        return JsonResponse({'ok': False, 'error': 'Yükleme yetkiniz yok.'}, status=403)

    files = request.FILES.getlist('files') or request.FILES.getlist('file')
    if not files:
        single = request.FILES.get('files') or request.FILES.get('file')
        if single:
            files = [single]
    if not files:
        return JsonResponse({'ok': False, 'error': 'Dosya seçilmedi.'}, status=400)

    title = (request.POST.get('title') or '').strip()
    note = (request.POST.get('note') or '').strip()
    created = []
    rejected = []
    for uploaded in files:
        if not is_allowed_upload(uploaded.name):
            rejected.append(uploaded.name)
            continue
        media = CustomerMedia.objects.create(
            customer=customer,
            service=service if scope == CustomerMedia.SCOPE_SERVICE else None,
            scope=scope,
            file=uploaded,
            title=title or uploaded.name,
            note=note,
            uploaded_by=request.user,
        )
        item = _serialize_media(media)
        if media.compress_method and media.file_size_original and media.file_size_stored:
            if media.file_size_stored < media.file_size_original:
                item['compress_note'] = (
                    f"Sunucuda sıkıştırıldı ({media.compress_method}): "
                    f"{_format_bytes(media.file_size_original)} → {_format_bytes(media.file_size_stored)}"
                )
        created.append(item)

    if not created and rejected:
        return JsonResponse({
            'ok': False,
            'error': 'Bu dosya türü desteklenmiyor (çalıştırılabilir dosyalar yasak).',
        }, status=400)
    payload = {'ok': True, 'items': created, 'count': len(created)}
    if rejected:
        payload['skipped'] = rejected
        payload['warning'] = f'{len(rejected)} dosya atlandı (desteklenmeyen tür).'
    return JsonResponse(payload)


@require_http_methods(['POST', 'DELETE'])
@permission_required(CUSTOMERS_EDIT_PERM, SERVICES_MANAGE_PERM, 'tools.media_delete', any_perm=True)
def customer_media_delete_api(request, pk):
    media = get_object_or_404(CustomerMedia.objects.select_related('customer', 'service'), pk=pk)
    if not _can_upload_media(request.user, media.scope, media.service):
        return JsonResponse({'ok': False, 'error': 'Silme yetkiniz yok.'}, status=403)

    if media.file:
        media.file.delete(save=False)
    media.delete()
    return JsonResponse({'ok': True, 'message': 'Dosya silindi.'})
