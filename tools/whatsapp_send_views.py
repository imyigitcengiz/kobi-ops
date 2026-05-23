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
    )

    conn_id, _, conn_err = pick_ready_connection(connection_id, strict=bool(connection_id))
    if conn_err:
        outbound.status = WhatsappOutboundMessage.STATUS_FAILED
        outbound.error_message = conn_err
        outbound.save(update_fields=['status', 'error_message'])
        return connection_id, outbound, conn_err, None
    if not conn_id:
        outbound.status = WhatsappOutboundMessage.STATUS_FAILED
        outbound.error_message = 'Bağlı WhatsApp hattı yok. Tools → WhatsApp Bağlan sayfasından QR ile bağlanın.'
        outbound.save(update_fields=['status', 'error_message'])
        return None, outbound, 'Bağlı WhatsApp hattı yok. Tools → WhatsApp Bağlan sayfasından QR ile bağlanın.', None

    try:
        result = bridge_send(conn_id, phone_norm, message)
    except WhatsappBridgeOffline as exc:
        outbound.status = WhatsappOutboundMessage.STATUS_FAILED
        outbound.error_message = str(exc)
        outbound.save(update_fields=['status', 'error_message'])
        raise
    except WhatsappBridgeError as exc:
        outbound.status = WhatsappOutboundMessage.STATUS_FAILED
        outbound.error_message = str(exc)
        outbound.save(update_fields=['status', 'error_message'])
        return conn_id, outbound, str(exc), None

    outbound.status = WhatsappOutboundMessage.STATUS_SENT
    outbound.sent_at = timezone.now()
    outbound.error_message = ''
    outbound.save(update_fields=['status', 'sent_at', 'error_message'])
    if firm:
        sync_firm_message_stats(firm)
    return conn_id, outbound, None, result


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
    })
