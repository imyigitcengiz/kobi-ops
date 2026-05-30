"""Toplu yazdırma raporu — konum QR veya WhatsApp konum isteği."""

from __future__ import annotations

from urllib.parse import quote

from core_settings.whatsapp_print import render_whatsapp_location_request_message
from tools.phone_utils import whatsapp_url

QR_API = 'https://api.qrserver.com/v1/create-qr-code/?size={size}x{size}&data={data}'


def _qr_image_url(target: str, *, size: int = 120) -> str:
    return QR_API.format(size=size, data=quote(target, safe=''))


def _service_type_label(service) -> str:
    names = [st.name for st in service.service_types.all()]
    return ', '.join(names) if names else 'servis'


def build_bulk_print_qr(service, *, site_name: str = 'CoolOPS') -> dict:
    """
    kind: location | whatsapp | none
    location → müşteri konum linki QR
    whatsapp → wa.me ile konum isteme mesajı QR
    """
    customer = service.customer
    location = (customer.location_link or '').strip()
    if location:
        return {
            'kind': 'location',
            'target_url': location,
            'qr_image_url': _qr_image_url(location),
            'caption': 'Konum',
            'hint': '',
        }

    wa_base = whatsapp_url(customer.phone or '')
    if wa_base == '-':
        return {
            'kind': 'none',
            'target_url': '',
            'qr_image_url': '',
            'caption': '—',
            'hint': 'Telefon / konum yok',
        }

    ariza = _service_type_label(service)
    message = render_whatsapp_location_request_message(site_name=site_name, ariza=ariza)
    wa_link = f'{wa_base}?text={quote(message)}'
    return {
        'kind': 'whatsapp',
        'target_url': wa_link,
        'qr_image_url': _qr_image_url(wa_link),
        'caption': 'WA konum iste',
        'hint': message,
    }
