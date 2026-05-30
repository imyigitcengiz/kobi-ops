"""Meta WhatsApp Business Cloud API — kampanya, firma ve lead mesajları."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from core_settings.models import SiteSettings


class WhatsappCloudError(Exception):
    pass


class WhatsappCloudNotConfigured(WhatsappCloudError):
    pass


def get_cloud_credentials() -> tuple[str, str]:
    settings = SiteSettings.objects.first()
    token = ''
    phone_id = ''
    if settings:
        token = (getattr(settings, 'whatsapp_cloud_token', None) or '').strip()
        phone_id = (getattr(settings, 'whatsapp_cloud_phone_id', None) or '').strip()
    if not token:
        token = (os.environ.get('WHATSAPP_CLOUD_TOKEN') or '').strip()
    if not phone_id:
        phone_id = (os.environ.get('WHATSAPP_CLOUD_PHONE_ID') or '').strip()
    return token, phone_id


def cloud_api_configured() -> bool:
    token, phone_id = get_cloud_credentials()
    return bool(token and phone_id)


def cloud_api_status() -> dict:
    token, phone_id = get_cloud_credentials()
    configured = bool(token and phone_id)
    masked = ''
    if token:
        masked = f'…{token[-6:]}' if len(token) > 6 else '***'
    return {
        'configured': configured,
        'ready': configured,
        'phone_id': phone_id or '',
        'token_hint': masked,
    }


def cloud_send(phone_norm: str, message: str) -> dict:
    token, phone_id = get_cloud_credentials()
    if not token or not phone_id:
        raise WhatsappCloudNotConfigured(
            'WhatsApp Business API yapılandırılmamış. Site ayarları → Genel bölümünden '
            'API token ve telefon numarası ID girin.'
        )

    digits = (phone_norm or '').lstrip('+').replace(' ', '')
    if not digits:
        raise WhatsappCloudError('Geçersiz telefon numarası.')

    url = f'https://graph.facebook.com/v21.0/{phone_id}/messages'
    payload = {
        'messaging_product': 'whatsapp',
        'to': digits,
        'type': 'text',
        'text': {'body': message or 'Merhaba'},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        try:
            parsed = json.loads(detail)
            err = parsed.get('error', {})
            msg = err.get('message') or detail[:300]
        except json.JSONDecodeError:
            msg = detail[:300] or f'HTTP {exc.code}'
        raise WhatsappCloudError(msg) from exc
    except urllib.error.URLError as exc:
        raise WhatsappCloudError(f'WhatsApp API bağlantı hatası: {exc.reason}') from exc

    messages = body.get('messages') or []
    return {
        'messageId': messages[0].get('id') if messages else None,
        'raw': body,
    }
