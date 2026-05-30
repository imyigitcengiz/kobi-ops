from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from pathlib import Path

from common.decorators import json_auth_required, permission_required
from core_settings.models import SiteSettings
from core_settings.whatsapp_print import (
    DEFAULT_WHATSAPP_LOCATION_REQUEST_TEMPLATE,
    get_whatsapp_location_request_template,
    render_whatsapp_location_request_message,
)
from tools.models import WhatsappConnection
from tools.views import _json_body
from tools.whatsapp_bridge_runner import bridge_reachable, probe_bridge, try_spawn_bridge_process
from tools.whatsapp_client import (
    WhatsappBridgeError,
    WhatsappBridgeOffline,
    bridge_connection_connect,
    bridge_connection_disconnect,
    bridge_connection_status,
)


def _sync_connection_from_bridge(conn: WhatsappConnection, bridge_data: dict) -> WhatsappConnection:
    status = bridge_data.get('status') or 'disconnected'
    phone = (bridge_data.get('phone') or '').strip()
    pushname = (bridge_data.get('pushname') or '').strip()
    updates = []
    if phone and conn.phone != phone:
        conn.phone = phone
        updates.append('phone')
    if pushname and conn.pushname != pushname:
        conn.pushname = pushname
        updates.append('pushname')
    if status == 'ready' and not conn.last_connected_at:
        conn.last_connected_at = timezone.now()
        updates.append('last_connected_at')
    if updates:
        conn.save(update_fields=updates + ['updated_at'])
    return conn


def serialize_connection(conn: WhatsappConnection, bridge_data: dict | None = None) -> dict:
    data = {
        'id': conn.id,
        'name': conn.name,
        'phone': conn.phone or (bridge_data or {}).get('phone') or '',
        'pushname': conn.pushname or (bridge_data or {}).get('pushname') or '',
        'last_connected_at': conn.last_connected_at.isoformat() if conn.last_connected_at else None,
        'created_at': conn.created_at.isoformat(),
    }
    if bridge_data:
        data.update({
            'status': bridge_data.get('status') or 'disconnected',
            'qrDataUrl': bridge_data.get('qrDataUrl'),
            'initializing': bool(bridge_data.get('initializing')),
            'lastError': bridge_data.get('lastError'),
        })
    else:
        data['status'] = 'disconnected'
        data['qrDataUrl'] = None
        data['initializing'] = False
        data['lastError'] = None
    return data


def _bridge_status_for(conn: WhatsappConnection) -> dict | None:
    try:
        return bridge_connection_status(conn.id)
    except WhatsappBridgeOffline:
        return None
    except WhatsappBridgeError:
        return None


@require_http_methods(['POST'])
@json_auth_required
@permission_required('tools.whatsapp')
def whatsapp_bridge_auto_start_api(request):
    """Köprü kapalıysa yerel olarak başlatır (eski süreç varsa kapatıp yeniden açar)."""
    from tools.whatsapp_bridge_runner import bridge_spawn_allowed

    if not bridge_spawn_allowed():
        return JsonResponse({
            'ok': False,
            'reason': 'spawn_disabled',
            'error': 'Bu ortamda köprü panelden başlatılamaz; whatsapp_bridge servisini kullanın.',
        }, status=403)

    body = _json_body(request) or {}
    force = bool(body.get('force'))
    as_admin = body.get('as_admin')
    if as_admin is not None:
        as_admin = bool(as_admin)

    probe = probe_bridge()
    if probe.get('modern'):
        return JsonResponse({'ok': True, 'already_running': True, 'probe': probe})

    out = try_spawn_bridge_process(force=force, as_admin=as_admin)

    if out.get('spawned'):
        msg = 'Köprü başlatıldı.'
        if out.get('deps_installed'):
            msg = 'Bağımlılıklar kuruldu, köprü başlatıldı.'
        if out.get('as_admin'):
            msg += ' UAC penceresinde Evet deyin.'
        if out.get('killed_pid'):
            msg += f' Eski süreç kapatıldı (PID {out["killed_pid"]}).'
        return JsonResponse({
            'ok': True,
            'started': True,
            'probe': out.get('probe'),
            'killed_pid': out.get('killed_pid'),
            'as_admin': out.get('as_admin'),
            'node': out.get('node'),
            'deps_installed': bool(out.get('deps_installed')),
            'message': msg,
        })

    reason = out.get('reason')

    if reason == 'recent':
        return JsonResponse({'ok': True, 'pending': True, 'message': out.get('message'), 'probe': probe})

    if reason == 'already_running':
        return JsonResponse({'ok': True, 'already_running': True, 'probe': probe})

    return JsonResponse({
        'ok': False,
        'reason': reason,
        'error': out.get('message') or 'Köprü başlatılamadı.',
        'probe': out.get('probe') or probe,
        'pid': out.get('pid'),
    })


@require_http_methods(['GET'])
@json_auth_required
@permission_required('tools.whatsapp')
def whatsapp_bridge_ui_log_api(request):
    """Köprünün yazdığı mirror log (sayfadaki konsol kutusu için)."""
    p = Path(settings.BASE_DIR) / 'tools' / 'whatsapp_bridge' / 'bridge_ui.log'
    if not p.is_file():
        hint = (
            'Henüz log yok. Windows’ta Tekrar deneyince köprü ayrı CMD penceresinde açılır; ilk satırlar burada güncellenir.\n'
            'Köprü hiç başlamıyorsa CMD penceresindeki kırmızı mesajları okuyun.'
        )
        return JsonResponse({'ok': True, 'content': hint})
    raw = p.read_text(encoding='utf-8', errors='replace')
    if len(raw) > 48000:
        raw = raw[-48000:]
    return JsonResponse({'ok': True, 'content': raw})


def _maybe_auto_reconnect(conn: WhatsappConnection, bridge_data: dict | None) -> dict | None:
    if not bridge_data:
        return bridge_data
    if bridge_data.get('status') not in (None, 'disconnected'):
        return bridge_data
    if bridge_data.get('initializing'):
        return bridge_data
    if not (conn.last_connected_at or conn.phone):
        return bridge_data
    try:
        return bridge_connection_connect(conn.id)
    except (WhatsappBridgeOffline, WhatsappBridgeError):
        return bridge_data


@require_http_methods(['GET', 'POST'])
@json_auth_required
@permission_required('tools.whatsapp')
def whatsapp_connections_api(request):
    if request.method == 'GET':
        probe = probe_bridge()
        bridge_offline = not probe.get('modern')
        items = []
        for conn in WhatsappConnection.objects.all():
            bridge = _bridge_status_for(conn) if not bridge_offline else None
            if bridge and not bridge_offline:
                bridge = _maybe_auto_reconnect(conn, bridge)
            if bridge:
                _sync_connection_from_bridge(conn, bridge)
            items.append(serialize_connection(conn, bridge))
        return JsonResponse({
            'ok': True,
            'connections': items,
            'bridge_offline': bridge_offline,
            'bridge_probe': probe,
        })

    body = _json_body(request) or {}
    name = (body.get('name') or '').strip()
    if not name:
        return JsonResponse({'ok': False, 'error': 'Bağlantı adı girin.'}, status=400)
    conn = WhatsappConnection.objects.create(name=name[:80])
    return JsonResponse({'ok': True, 'connection': serialize_connection(conn)})


@require_http_methods(['PATCH', 'DELETE'])
@json_auth_required
@permission_required('tools.whatsapp')
def whatsapp_connection_detail_api(request, pk):
    conn = get_object_or_404(WhatsappConnection, pk=pk)
    if request.method == 'PATCH':
        body = _json_body(request) or {}
        name = (body.get('name') or '').strip()
        if not name:
            return JsonResponse({'ok': False, 'error': 'Bağlantı adı girin.'}, status=400)
        conn.name = name[:80]
        conn.save(update_fields=['name', 'updated_at'])
        bridge = _bridge_status_for(conn)
        return JsonResponse({'ok': True, 'connection': serialize_connection(conn, bridge)})

    try:
        bridge_connection_disconnect(conn.id)
    except (WhatsappBridgeOffline, WhatsappBridgeError):
        pass
    conn.delete()
    return JsonResponse({'ok': True, 'deleted': pk})


@require_http_methods(['GET'])
@json_auth_required
@permission_required('tools.whatsapp')
def whatsapp_connection_status_api(request, pk):
    conn = get_object_or_404(WhatsappConnection, pk=pk)
    try:
        bridge = bridge_connection_status(conn.id)
    except WhatsappBridgeOffline as exc:
        return JsonResponse({'ok': False, 'offline': True, 'error': str(exc), 'connection': serialize_connection(conn)})
    except WhatsappBridgeError as exc:
        return JsonResponse({'ok': False, 'error': str(exc), 'connection': serialize_connection(conn)}, status=502)
    _sync_connection_from_bridge(conn, bridge)
    return JsonResponse({'ok': True, 'connection': serialize_connection(conn, bridge)})


@require_http_methods(['POST'])
@json_auth_required
@permission_required('tools.whatsapp')
def whatsapp_connection_connect_api(request, pk):
    conn = get_object_or_404(WhatsappConnection, pk=pk)
    try:
        bridge = bridge_connection_connect(conn.id)
    except WhatsappBridgeOffline as exc:
        return JsonResponse({'ok': False, 'offline': True, 'error': str(exc)}, status=503)
    except WhatsappBridgeError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=502)
    _sync_connection_from_bridge(conn, bridge)
    return JsonResponse({'ok': True, 'connection': serialize_connection(conn, bridge)})


@require_http_methods(['POST'])
@json_auth_required
@permission_required('tools.whatsapp')
def whatsapp_connection_disconnect_api(request, pk):
    conn = get_object_or_404(WhatsappConnection, pk=pk)
    try:
        bridge = bridge_connection_disconnect(conn.id)
    except WhatsappBridgeOffline as exc:
        return JsonResponse({'ok': False, 'offline': True, 'error': str(exc)}, status=503)
    except WhatsappBridgeError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=502)
    conn.phone = ''
    conn.pushname = ''
    conn.save(update_fields=['phone', 'pushname', 'updated_at'])
    return JsonResponse({'ok': True, 'connection': serialize_connection(conn, bridge)})


def _site_settings_row() -> SiteSettings:
    row = SiteSettings.objects.first()
    if row:
        return row
    return SiteSettings.objects.create()


@require_http_methods(['GET', 'POST'])
@json_auth_required
@permission_required('tools.whatsapp')
def whatsapp_location_request_template_api(request):
    if request.method == 'GET':
        template = get_whatsapp_location_request_template()
        site_name = _site_settings_row().site_name or 'CoolOPS'
        return JsonResponse({
            'ok': True,
            'template': template,
            'default_template': DEFAULT_WHATSAPP_LOCATION_REQUEST_TEMPLATE,
            'preview': render_whatsapp_location_request_message(
                site_name=site_name,
                ariza='klima arızası',
            ),
        })

    body = _json_body(request)
    if body is None:
        return JsonResponse({'ok': False, 'error': 'Geçersiz istek.'}, status=400)
    template = (body.get('template') or '').strip()
    if not template:
        return JsonResponse({'ok': False, 'error': 'Mesaj metni boş olamaz.'}, status=400)
    if '{site_name}' not in template or '{ariza}' not in template:
        return JsonResponse(
            {'ok': False, 'error': 'Mesajda {site_name} ve {ariza} değişkenleri bulunmalı.'},
            status=400,
        )

    row = _site_settings_row()
    row.whatsapp_location_request_template = template
    row.save(update_fields=['whatsapp_location_request_template'])

    site_name = row.site_name or 'CoolOPS'
    return JsonResponse({
        'ok': True,
        'template': template,
        'preview': render_whatsapp_location_request_message(
            site_name=site_name,
            ariza='klima arızası',
        ),
    })
