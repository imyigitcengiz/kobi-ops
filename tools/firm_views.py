"""Firma hafızası toplu işlemler, etiketler ve mesaj geçmişi API."""

from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from tools.collections import DEFAULT_TEMPLATE, add_firm_to_collection, serialize_collection
from tools.firm_memory import serialize_firm
from tools.firm_directory import create_manual_firm, sync_all_partners_to_directory, sync_partner_to_directory
from tools.models import FirmTag, MapsScrapedFirm, OutreachCollection, WhatsappOutboundMessage
from tools.outreach_memory import memory_stats
from tools.views import _json_body

TAG_COLORS = ('#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#3b82f6', '#ef4444', '#64748b')


def _serialize_tag(tag: FirmTag) -> dict:
    return {'id': tag.id, 'name': tag.name, 'color': tag.color, 'firm_count': tag.firms.count()}


def _parse_firm_ids(body) -> list[int]:
    ids = []
    for raw in body.get('firm_ids') or []:
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    return ids


def _get_or_create_tag(name: str) -> FirmTag:
    clean = name.strip()[:60]
    tag = FirmTag.objects.filter(name__iexact=clean).first()
    if tag:
        return tag
    return FirmTag.objects.create(
        name=clean,
        color=TAG_COLORS[FirmTag.objects.count() % len(TAG_COLORS)],
    )


@require_http_methods(['GET', 'POST'])
def tags_api(request):
    if request.method == 'GET':
        tags = [_serialize_tag(t) for t in FirmTag.objects.all()]
        return JsonResponse({'ok': True, 'tags': tags})

    body = _json_body(request) or {}
    name = (body.get('name') or '').strip()
    if not name:
        return JsonResponse({'ok': False, 'error': 'Etiket adı girin.'}, status=400)
    tag = _get_or_create_tag(name)
    if body.get('color'):
        tag.color = str(body['color'])[:7]
        tag.save(update_fields=['color'])
    return JsonResponse({'ok': True, 'tag': _serialize_tag(tag)})


@require_http_methods(['PATCH', 'DELETE'])
def tag_detail_api(request, pk):
    tag = get_object_or_404(FirmTag, pk=pk)
    if request.method == 'DELETE':
        tag.delete()
        return JsonResponse({'ok': True, 'deleted': pk})

    body = _json_body(request) or {}
    name = (body.get('name') or '').strip()
    if name:
        clash = FirmTag.objects.filter(name__iexact=name).exclude(pk=pk).first()
        if clash:
            return JsonResponse({'ok': False, 'error': 'Bu isimde başka etiket var.'}, status=400)
        tag.name = name[:60]
    if body.get('color'):
        tag.color = str(body['color'])[:7]
    tag.save(update_fields=['name', 'color'])
    return JsonResponse({'ok': True, 'tag': _serialize_tag(tag)})


@require_http_methods(['GET'])
def regions_api(request):
    regions = list(
        MapsScrapedFirm.objects.exclude(region='')
        .values_list('region', flat=True)
        .distinct()
        .order_by('region')
    )
    return JsonResponse({'ok': True, 'regions': regions})


@require_http_methods(['POST'])
def firms_bulk_api(request):
    body = _json_body(request) or {}
    action = (body.get('action') or '').strip()
    firm_ids = _parse_firm_ids(body)
    no_selection_actions = ('clear_all', 'sync_partners', 'add_firm', 'add_partner')
    if not firm_ids and action not in no_selection_actions:
        return JsonResponse({'ok': False, 'error': 'Firma seçin.'}, status=400)

    firms = MapsScrapedFirm.objects.filter(pk__in=firm_ids)

    if action == 'delete':
        deleted, _ = firms.delete()
        return JsonResponse({'ok': True, 'deleted': deleted, 'action': action})

    if action == 'add_tag':
        tag_name = (body.get('tag_name') or '').strip()
        tag_id = body.get('tag_id')
        if tag_id:
            tag = FirmTag.objects.filter(pk=int(tag_id)).first()
        elif tag_name:
            tag = _get_or_create_tag(tag_name)
        else:
            return JsonResponse({'ok': False, 'error': 'Etiket seçin veya ad girin.'}, status=400)
        if not tag:
            return JsonResponse({'ok': False, 'error': 'Etiket bulunamadı.'}, status=404)
        for firm in firms:
            firm.tags.add(tag)
        return JsonResponse({'ok': True, 'updated': firms.count(), 'tag': _serialize_tag(tag), 'action': action})

    if action == 'remove_tag':
        tag_id = body.get('tag_id')
        if not tag_id:
            return JsonResponse({'ok': False, 'error': 'Etiket seçin.'}, status=400)
        tag = FirmTag.objects.filter(pk=int(tag_id)).first()
        if not tag:
            return JsonResponse({'ok': False, 'error': 'Etiket bulunamadı.'}, status=404)
        for firm in firms:
            firm.tags.remove(tag)
        return JsonResponse({'ok': True, 'updated': firms.count(), 'action': action})

    if action == 'set_region':
        region = (body.get('region') or '').strip()[:80]
        if not region:
            return JsonResponse({'ok': False, 'error': 'Bölge adı girin.'}, status=400)
        updated = firms.update(region=region)
        return JsonResponse({'ok': True, 'updated': updated, 'region': region, 'action': action})

    if action == 'add_firm':
        name = (body.get('name') or '').strip()
        phone = (body.get('phone') or '').strip()
        kind = (body.get('firm_kind') or MapsScrapedFirm.KIND_BUSINESS).strip()
        if not name:
            return JsonResponse({'ok': False, 'error': 'Firma adı girin.'}, status=400)
        if kind == MapsScrapedFirm.KIND_PARTNER:
            from core_settings.models import SolutionPartner, SolutionPartnerType

            ptype = None
            raw_type = body.get('partner_type_id')
            if raw_type:
                ptype = SolutionPartnerType.objects.filter(pk=int(raw_type)).first()
            if not ptype:
                ptype = SolutionPartnerType.objects.filter(is_active=True).order_by('id').first()
            if not ptype:
                return JsonResponse(
                    {'ok': False, 'error': 'Önce ayarlardan çözüm ortağı türü tanımlayın.'},
                    status=400,
                )
            partner = SolutionPartner.objects.create(
                name=name[:255],
                phone=phone[:40],
                partner_type=ptype,
                notes=(body.get('notes') or '')[:500],
                is_active=bool(body.get('is_active', True)),
            )
            firm = sync_partner_to_directory(partner)
            return JsonResponse({
                'ok': True,
                'action': action,
                'partner_id': partner.id,
                'firm': serialize_firm(firm) if firm else None,
            })
        firm = create_manual_firm(
            name=name,
            phone=phone,
            firm_kind=kind,
            region=(body.get('region') or '').strip(),
            notes=(body.get('notes') or '').strip(),
        )
        return JsonResponse({'ok': True, 'action': action, 'firm': serialize_firm(firm)})

    if action == 'sync_partners':
        count = sync_all_partners_to_directory()
        return JsonResponse({'ok': True, 'action': action, 'synced': count, **memory_stats()})

    if action == 'add_partner':
        from core_settings.models import SolutionPartner, SolutionPartnerType

        name = (body.get('name') or '').strip()
        phone = (body.get('phone') or '').strip()
        if not name:
            return JsonResponse({'ok': False, 'error': 'Ortak adı girin.'}, status=400)
        ptype = None
        raw_type = body.get('partner_type_id')
        if raw_type:
            ptype = SolutionPartnerType.objects.filter(pk=int(raw_type)).first()
        if not ptype:
            ptype = SolutionPartnerType.objects.filter(is_active=True).order_by('id').first()
        if not ptype:
            return JsonResponse({'ok': False, 'error': 'Önce ayarlardan çözüm ortağı türü tanımlayın.'}, status=400)
        partner = SolutionPartner.objects.create(
            name=name[:255],
            phone=phone[:40],
            partner_type=ptype,
            notes=(body.get('notes') or '')[:500],
            is_active=bool(body.get('is_active', True)),
        )
        firm = sync_partner_to_directory(partner)
        return JsonResponse({
            'ok': True,
            'action': action,
            'partner_id': partner.id,
            'firm': serialize_firm(firm) if firm else None,
        })

    if action == 'send_message':
        message = (body.get('message') or '').strip()
        if not message:
            return JsonResponse({'ok': False, 'error': 'Mesaj metni girin.'}, status=400)
        connection_id = body.get('connection_id')
        from tools.whatsapp_send_views import _log_and_send

        sent = 0
        failed = 0
        errors = []
        for firm in firms:
            if not firm.phone_normalized:
                failed += 1
                continue
            try:
                _, outbound, err, _ = _log_and_send(
                    phone_raw=firm.phone,
                    phone_norm=firm.phone_normalized,
                    message=message,
                    connection_id=connection_id,
                    recipient_name=firm.name,
                    firm_id=firm.id,
                    source=WhatsappOutboundMessage.SOURCE_MANUAL,
                    send_type=WhatsappOutboundMessage.SEND_PRIVATE,
                )
                if err:
                    failed += 1
                    errors.append(f'{firm.name}: {err}')
                else:
                    sent += 1
            except Exception as exc:
                failed += 1
                errors.append(f'{firm.name}: {exc}')
        return JsonResponse({
            'ok': True,
            'action': action,
            'sent': sent,
            'failed': failed,
            'errors': errors[:10],
        })

    if action == 'create_collection':
        name = (body.get('collection_name') or body.get('name') or '').strip()
        if not name:
            return JsonResponse({'ok': False, 'error': 'Kampanya adı girin.'}, status=400)
        col = OutreachCollection.objects.create(
            name=name[:120],
            message_template=(body.get('message_template') or DEFAULT_TEMPLATE).strip(),
            skip_globally_messaged=bool(body.get('skip_globally_messaged', False)),
            allow_repeat_in_campaign=bool(body.get('allow_repeat_in_campaign', True)),
            delay_seconds=int(body.get('delay_seconds') or 4),
        )
        added = 0
        skipped = 0
        for firm in firms:
            member, _ = add_firm_to_collection(col, firm)
            if member:
                added += 1
            else:
                skipped += 1
        return JsonResponse({
            'ok': True,
            'action': action,
            'collection': serialize_collection(col, include_members=True),
            'added': added,
            'skipped': skipped,
        })

    return JsonResponse({'ok': False, 'error': 'Geçersiz işlem.'}, status=400)


@require_http_methods(['POST'])
def firms_memory_clear_api(request):
    body = _json_body(request) or {}
    mode = (body.get('mode') or 'selected').strip()
    confirm = (body.get('confirm') or '').strip()

    if mode == 'all':
        if confirm != 'TEMIZLE':
            return JsonResponse({'ok': False, 'error': 'Onay için confirm: "TEMIZLE" gönderin.'}, status=400)
        deleted, _ = MapsScrapedFirm.objects.all().delete()
        return JsonResponse({'ok': True, 'deleted': deleted, 'mode': 'all', **memory_stats()})

    firm_ids = _parse_firm_ids(body)
    if not firm_ids:
        return JsonResponse({'ok': False, 'error': 'Silinecek firma seçin.'}, status=400)
    deleted, _ = MapsScrapedFirm.objects.filter(pk__in=firm_ids).delete()
    return JsonResponse({'ok': True, 'deleted': deleted, 'mode': 'selected', **memory_stats()})


@require_http_methods(['GET'])
def sent_messages_api(request):
    q = (request.GET.get('q') or '').strip()
    status = (request.GET.get('status') or 'sent').strip()
    collection_id = request.GET.get('collection_id')
    firm_id = request.GET.get('firm_id')
    send_type = (request.GET.get('send_type') or '').strip()
    scope = (request.GET.get('scope') or 'firm').strip().lower()
    page = max(int(request.GET.get('page') or 1), 1)
    page_size = min(max(int(request.GET.get('page_size') or 50), 1), 200)

    qs = WhatsappOutboundMessage.objects.select_related('collection', 'firm', 'customer').order_by(
        '-sent_at', '-created_at',
    )
    if scope == 'customer':
        qs = qs.filter(send_type=WhatsappOutboundMessage.SEND_CUSTOMER)
    elif scope == 'firm':
        qs = qs.exclude(send_type=WhatsappOutboundMessage.SEND_CUSTOMER)
    if status and status != 'all':
        qs = qs.filter(status=status)
    if collection_id:
        try:
            qs = qs.filter(collection_id=int(collection_id))
        except (TypeError, ValueError):
            pass
    if send_type and send_type != 'all':
        qs = qs.filter(send_type=send_type)
    if firm_id:
        try:
            fid = int(firm_id)
            firm = MapsScrapedFirm.objects.filter(pk=fid).first()
            if firm and firm.phone_normalized:
                qs = qs.filter(Q(firm_id=fid) | Q(phone_normalized=firm.phone_normalized))
            else:
                qs = qs.filter(firm_id=fid)
        except (TypeError, ValueError):
            pass
    if q:
        qs = qs.filter(
            Q(recipient_name__icontains=q)
            | Q(phone_display__icontains=q)
            | Q(phone_normalized__icontains=q)
            | Q(message__icontains=q)
        )

    total = qs.count()
    start = (page - 1) * page_size
    items = []
    for m in qs[start:start + page_size]:
        items.append({
            'id': m.id,
            'recipient_name': m.recipient_name,
            'phone': m.phone_display or m.phone_normalized,
            'phone_normalized': m.phone_normalized,
            'message': m.message,
            'status': m.status,
            'status_label': m.get_status_display(),
            'collection_id': m.collection_id,
            'collection_name': m.collection.name if m.collection else '',
            'firm_id': m.firm_id,
            'customer_id': m.customer_id,
            'send_type': m.send_type or '',
            'send_type_label': m.get_send_type_display() if m.send_type else (m.get_source_display() if m.source else '—'),
            'error_message': m.error_message,
            'sent_at': m.sent_at.isoformat() if m.sent_at else None,
            'created_at': m.created_at.isoformat(),
        })

    return JsonResponse({
        'ok': True,
        'total': total,
        'page': page,
        'page_size': page_size,
        'results': items,
    })
