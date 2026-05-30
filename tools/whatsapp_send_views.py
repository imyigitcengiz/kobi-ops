from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from common.decorators import json_auth_required, permission_required

from customers.models import Customer
from tools.models import MapsScrapedFirm, WhatsappConnection, WhatsappOutboundMessage
from tools.outreach_memory import sync_firm_message_stats
from tools.phone_utils import is_whatsapp_eligible, normalize_phone
from tools.views import _json_body
from tools.whatsapp_client import (
    WhatsappBridgeError,
    WhatsappBridgeOffline,
    bridge_connection_status,
    bridge_send,
)
from tools.whatsapp_cloud_client import (
    WhatsappCloudError,
    WhatsappCloudNotConfigured,
    cloud_api_configured,
    cloud_api_status,
    cloud_send,
)


def _list_connection_candidates(preferred_id=None) -> list[int]:
    ids = []
    if preferred_id:
        try:
            ids.append(int(preferred_id))
        except (TypeError, ValueError):
            pass
    for conn in WhatsappConnection.objects.order_by('-last_connected_at', 'name'):
        if conn.id not in ids:
            ids.append(conn.id)
    return ids


def pick_ready_connection(preferred_id=None, *, strict=False) -> tuple[int | None, dict | None, str | None]:
    last_offline = None
    candidates = _list_connection_candidates(preferred_id)
    if strict and preferred_id:
        try:
            candidates = [int(preferred_id)]
        except (TypeError, ValueError):
            return None, None, 'Geçersiz WhatsApp hattı seçimi.'
    for cid in candidates:
        try:
            status = bridge_connection_status(cid)
        except WhatsappBridgeOffline as exc:
            last_offline = exc
            raise
        except WhatsappBridgeError:
            if strict:
                return None, None, 'Seçilen WhatsApp hattına ulaşılamadı.'
            continue
        if status.get('status') == 'ready':
            return cid, status, None
        if strict:
            conn = WhatsappConnection.objects.filter(pk=cid).first()
            label = conn.name if conn else f'Hat #{cid}'
            return None, status, f'"{label}" şu an bağlı değil. Başka hat seçin veya QR ile bağlanın.'
    if last_offline:
        raise last_offline
    return None, None, None


def _resolve_send_type(*, customer_id=None, firm=None, collection_id=None, source: str = '', explicit: str = '') -> str:
    if explicit:
        return explicit
    if customer_id:
        return WhatsappOutboundMessage.SEND_CUSTOMER
    if collection_id:
        return WhatsappOutboundMessage.SEND_CAMPAIGN
    if source == WhatsappOutboundMessage.SOURCE_AUTO:
        return WhatsappOutboundMessage.SEND_AUTO
    if firm:
        kind_map = {
            MapsScrapedFirm.KIND_PARTNER: WhatsappOutboundMessage.SEND_PARTNER,
            MapsScrapedFirm.KIND_DEALER: WhatsappOutboundMessage.SEND_DEALER,
            MapsScrapedFirm.KIND_BUSINESS: WhatsappOutboundMessage.SEND_BUSINESS,
            MapsScrapedFirm.KIND_SCRAPED: WhatsappOutboundMessage.SEND_SCRAPED,
        }
        return kind_map.get(firm.firm_kind, WhatsappOutboundMessage.SEND_PRIVATE)
    if source == WhatsappOutboundMessage.SOURCE_SCRAPED:
        return WhatsappOutboundMessage.SEND_SCRAPED
    return WhatsappOutboundMessage.SEND_PRIVATE


CLOUD_SEND_TYPES = frozenset({
    WhatsappOutboundMessage.SEND_CAMPAIGN,
    WhatsappOutboundMessage.SEND_PRIVATE,
    WhatsappOutboundMessage.SEND_SCRAPED,
    WhatsappOutboundMessage.SEND_PARTNER,
    WhatsappOutboundMessage.SEND_DEALER,
    WhatsappOutboundMessage.SEND_BUSINESS,
})

SALES_LEAD_SCENARIOS = frozenset({
    'sales_lead_created',
    'sales_lead_status',
})


def resolve_whatsapp_transport(*, send_type: str = '', scenario: str = '', explicit: str = '') -> str:
    if explicit in ('bridge', 'cloud'):
        return explicit
    if scenario in SALES_LEAD_SCENARIOS:
        return 'cloud'
    if send_type == WhatsappOutboundMessage.SEND_CUSTOMER:
        return 'bridge'
    if send_type == WhatsappOutboundMessage.SEND_AUTO:
        return 'bridge'
    if send_type in CLOUD_SEND_TYPES:
        return 'cloud'
    return 'bridge'


def _dispatch_send(
    *,
    transport: str,
    phone_norm: str,
    message: str,
    connection_id: int | None,
    outbound: WhatsappOutboundMessage,
):
    if transport == 'cloud':
        if not cloud_api_configured():
            return None, 'WhatsApp Business API yapılandırılmamış. Site ayarlarından API bilgilerini girin.', None
        try:
            result = cloud_send(phone_norm, message)
        except WhatsappCloudNotConfigured as exc:
            return None, str(exc), None
        except WhatsappCloudError as exc:
            return None, str(exc), None
        return None, None, result

    conn_id, _, conn_err = pick_ready_connection(connection_id, strict=bool(connection_id))
    if conn_err:
        return conn_id, conn_err, None
    if not conn_id:
        err = 'Bağlı WhatsApp hattı yok. Yardım Masası → WhatsApp Bağlan sayfasından QR ile bağlanın.'
        return None, err, None
    try:
        result = bridge_send(conn_id, phone_norm, message)
    except WhatsappBridgeOffline as exc:
        raise
    except WhatsappBridgeError as exc:
        return conn_id, str(exc), None
    return conn_id, None, result


def _log_and_send(
    *,
    phone_raw: str,
    phone_norm: str,
    message: str,
    connection_id: int | None,
    recipient_name: str = '',
    customer_id=None,
    firm_id=None,
    collection_id=None,
    source: str = WhatsappOutboundMessage.SOURCE_MANUAL,
    send_type: str = '',
    scenario: str = '',
    transport: str = '',
):
    firm = None
    customer = None
    if firm_id:
        firm = MapsScrapedFirm.objects.filter(pk=firm_id).first()
    elif customer_id:
        customer = Customer.objects.filter(pk=customer_id).first()
    elif phone_norm:
        firm = MapsScrapedFirm.objects.filter(phone_normalized=phone_norm).exclude(
            notes='Müşteri mesajı',
        ).first()

    resolved_send_type = _resolve_send_type(
        customer_id=customer_id,
        firm=firm,
        collection_id=collection_id,
        source=source,
        explicit=send_type,
    )
    if resolved_send_type == WhatsappOutboundMessage.SEND_CUSTOMER:
        firm = None
    recipient_label = recipient_name
    if not recipient_label and customer:
        recipient_label = customer.name
    elif not recipient_label and firm:
        recipient_label = firm.name
    elif not recipient_label:
        recipient_label = 'Alıcı'

    outbound = WhatsappOutboundMessage.objects.create(
        firm=firm,
        customer=customer,
        recipient_name=recipient_label,
        phone_normalized=phone_norm,
        phone_display=phone_raw or phone_norm,
        message=message,
        status=WhatsappOutboundMessage.STATUS_SENDING,
        source=source,
        send_type=resolved_send_type,
        collection_id=collection_id,
    )

    resolved_transport = resolve_whatsapp_transport(
        send_type=resolved_send_type,
        scenario=scenario,
        explicit=transport,
    )

    try:
        conn_id, err, result = _dispatch_send(
            transport=resolved_transport,
            phone_norm=phone_norm,
            message=message,
            connection_id=connection_id,
            outbound=outbound,
        )
    except WhatsappBridgeOffline as exc:
        outbound.status = WhatsappOutboundMessage.STATUS_FAILED
        outbound.error_message = str(exc)
        outbound.save(update_fields=['status', 'error_message'])
        raise

    if err:
        outbound.status = WhatsappOutboundMessage.STATUS_FAILED
        outbound.error_message = err
        outbound.save(update_fields=['status', 'error_message'])
        return conn_id, outbound, err, None

    outbound.status = WhatsappOutboundMessage.STATUS_SENT
    outbound.sent_at = timezone.now()
    outbound.error_message = ''
    outbound.save(update_fields=['status', 'sent_at', 'error_message'])
    if firm:
        sync_firm_message_stats(firm)
    return conn_id, outbound, None, result


def send_pending_outbound(outbound: WhatsappOutboundMessage):
    """Kuyruktaki bekleyen mesajı uygun kanaldan gönder."""
    transport = resolve_whatsapp_transport(send_type=outbound.send_type or '')
    outbound.status = WhatsappOutboundMessage.STATUS_SENDING
    outbound.error_message = ''
    outbound.save(update_fields=['status', 'error_message'])

    try:
        conn_id, err, result = _dispatch_send(
            transport=transport,
            phone_norm=outbound.phone_normalized,
            message=outbound.message,
            connection_id=None,
            outbound=outbound,
        )
    except WhatsappBridgeOffline as exc:
        outbound.status = WhatsappOutboundMessage.STATUS_FAILED
        outbound.error_message = str(exc)
        outbound.save(update_fields=['status', 'error_message'])
        return {
            'ok': False,
            'offline': True,
            'error': str(exc),
            'recipient_name': outbound.recipient_name,
            'message_id': outbound.id,
        }

    if err:
        outbound.status = WhatsappOutboundMessage.STATUS_FAILED
        outbound.error_message = err
        outbound.save(update_fields=['status', 'error_message'])
        return {
            'ok': False,
            'error': err,
            'skipped': False,
            'recipient_name': outbound.recipient_name,
            'message_id': outbound.id,
            'offline': transport == 'bridge' and 'köprü' in err.lower(),
        }

    outbound.status = WhatsappOutboundMessage.STATUS_SENT
    outbound.sent_at = timezone.now()
    outbound.error_message = ''
    outbound.save(update_fields=['status', 'sent_at', 'error_message'])
    if outbound.firm_id:
        sync_firm_message_stats(outbound.firm)
    return {
        'ok': True,
        'recipient_name': outbound.recipient_name,
        'message_id': outbound.id,
        'bridge_message_id': (result or {}).get('messageId'),
    }


@require_http_methods(['GET'])
@json_auth_required
@permission_required('tools.whatsapp')
def whatsapp_ready_connections_api(request):
    try:
        items = []
        for conn in WhatsappConnection.objects.order_by('-last_connected_at', 'name'):
            try:
                bridge = bridge_connection_status(conn.id)
            except WhatsappBridgeOffline:
                return JsonResponse({
                    'ok': True,
                    'connections': items,
                    'bridge_offline': True,
                })
            except WhatsappBridgeError:
                bridge = {'status': 'disconnected'}
            items.append({
                'id': conn.id,
                'name': conn.name,
                'phone': bridge.get('phone') or conn.phone,
                'pushname': bridge.get('pushname') or conn.pushname,
                'status': bridge.get('status') or 'disconnected',
                'ready': bridge.get('status') == 'ready',
            })
        ready = [c for c in items if c['ready']]
        return JsonResponse({
            'ok': True,
            'connections': items,
            'ready_count': len(ready),
            'default_connection_id': ready[0]['id'] if len(ready) == 1 else (ready[0]['id'] if ready else None),
            'bridge_offline': False,
        })
    except WhatsappBridgeOffline as exc:
        return JsonResponse({'ok': False, 'offline': True, 'error': str(exc), 'connections': []}, status=503)


@require_http_methods(['POST'])
@json_auth_required
@permission_required('tools.whatsapp')
def whatsapp_send_api(request):
    body = _json_body(request) or {}
    phone_raw = (body.get('phone') or '').strip()
    message = (body.get('message') or '').strip()
    allow_empty = bool(body.get('allow_empty'))
    connection_id = body.get('connection_id')
    recipient_name = (body.get('recipient_name') or '').strip()
    customer_id = body.get('customer_id')
    firm_id = body.get('firm_id')
    collection_id = body.get('collection_id')
    source = (body.get('source') or WhatsappOutboundMessage.SOURCE_MANUAL).strip()
    send_type = (body.get('send_type') or '').strip()
    scenario = (body.get('scenario') or '').strip()
    transport = (body.get('transport') or '').strip()

    phone_norm = normalize_phone(phone_raw)
    if not is_whatsapp_eligible(phone_raw, phone_norm):
        return JsonResponse({'ok': False, 'error': 'Geçersiz numara veya sabit hat — WhatsApp ile gönderilemez.'}, status=400)
    if not message and not allow_empty:
        return JsonResponse({'ok': False, 'error': 'Mesaj boş olamaz.'}, status=400)
    if not message:
        message = 'Merhaba'

    try:
        conn_id, outbound, err, result = _log_and_send(
            phone_raw=phone_raw,
            phone_norm=phone_norm,
            message=message,
            connection_id=connection_id,
            recipient_name=recipient_name,
            customer_id=customer_id,
            firm_id=firm_id,
            collection_id=collection_id,
            source=source,
            send_type=send_type,
            scenario=scenario,
            transport=transport,
        )
    except WhatsappBridgeOffline as exc:
        return JsonResponse({'ok': False, 'offline': True, 'error': str(exc)}, status=503)

    if err:
        return JsonResponse({
            'ok': False,
            'error': err,
            'offline': 'köprü' in err.lower() or 'bağlı whatsapp' in err.lower(),
            'message_id': outbound.id if outbound else None,
        }, status=502 if conn_id else 503)

    return JsonResponse({
        'ok': True,
        'connection_id': conn_id,
        'message_id': outbound.id,
        'bridge_message_id': (result or {}).get('messageId'),
        'recipient_name': outbound.recipient_name,
        'transport': resolve_whatsapp_transport(
            send_type=outbound.send_type,
            scenario=scenario,
            explicit=transport,
        ),
    })


@require_http_methods(['GET'])
@json_auth_required
@permission_required('access.outreach')
def whatsapp_cloud_status_api(request):
    status = cloud_api_status()
    return JsonResponse({'ok': True, **status})


@require_http_methods(['POST'])
@json_auth_required
@permission_required('access.outreach')
def campaign_send_next_api(request):
    body = _json_body(request) or {}
    batch_id = (body.get('batch_id') or '').strip()
    if not batch_id:
        return JsonResponse({'ok': False, 'error': 'batch_id gerekli.'}, status=400)

    outbound = (
        WhatsappOutboundMessage.objects.filter(
            batch_id=batch_id,
            status=WhatsappOutboundMessage.STATUS_PENDING,
        )
        .order_by('id')
        .first()
    )
    if not outbound:
        return JsonResponse({'ok': True, 'done': True})

    result = send_pending_outbound(outbound)
    if result.get('done'):
        return JsonResponse(result)
    if not result.get('ok'):
        status_code = 503 if result.get('offline') else 502
        return JsonResponse(result, status=status_code)
    return JsonResponse(result)


@require_http_methods(['GET'])
@json_auth_required
@permission_required('access.outreach')
def campaign_queue_status_api(request):
    batch_id = (request.GET.get('batch_id') or '').strip()
    if not batch_id:
        return JsonResponse({'ok': False, 'error': 'batch_id gerekli.'}, status=400)
    qs = WhatsappOutboundMessage.objects.filter(batch_id=batch_id)
    return JsonResponse({
        'ok': True,
        'sent': qs.filter(status=WhatsappOutboundMessage.STATUS_SENT).count(),
        'failed': qs.filter(status=WhatsappOutboundMessage.STATUS_FAILED).count(),
        'skipped': qs.filter(status=WhatsappOutboundMessage.STATUS_SKIPPED).count(),
        'pending': qs.filter(status=WhatsappOutboundMessage.STATUS_PENDING).count(),
    })
