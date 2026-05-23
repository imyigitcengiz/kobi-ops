import requests
from django.conf import settings


class WhatsappBridgeError(Exception):
    pass


class WhatsappBridgeOffline(WhatsappBridgeError):
    pass


def _base_url():
    return getattr(settings, 'WHATSAPP_BRIDGE_URL', 'http://127.0.0.1:3939').rstrip('/')


def _request(method, path, *, json=None, timeout=8):
    url = f'{_base_url()}{path}'
    try:
        response = requests.request(method, url, json=json, timeout=timeout)
    except requests.RequestException as exc:
        raise WhatsappBridgeOffline(
            'WhatsApp köprüsü çalışmıyor. Birkaç saniye bekleyin veya Tools → WhatsApp’ta köprüyü başlatın.'
        ) from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise WhatsappBridgeError('Köprüden geçersiz yanıt alındı.') from exc
    if not response.ok:
        raise WhatsappBridgeError(data.get('error') or 'Köprü isteği başarısız.')
    return data


def bridge_connection_status(connection_id: int):
    return _request('GET', f'/api/connections/{connection_id}/status', timeout=5)


def bridge_connection_connect(connection_id: int):
    return _request('POST', f'/api/connections/{connection_id}/connect', timeout=30)


def bridge_connection_disconnect(connection_id: int):
    return _request('POST', f'/api/connections/{connection_id}/disconnect', timeout=10)


def bridge_send(connection_id: int, phone_normalized: str, message: str):
    return _request('POST', '/api/send', json={
        'connection_id': str(connection_id),
        'phone': phone_normalized,
        'message': message,
    }, timeout=45)
