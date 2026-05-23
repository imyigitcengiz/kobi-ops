"""Servis yazdırma — WhatsApp konum isteme mesajı şablonu."""

from __future__ import annotations

from core_settings.models import SiteSettings

DEFAULT_WHATSAPP_LOCATION_REQUEST_TEMPLATE = (
    'Merhabalar, {site_name} firmasından {ariza} servis kaydınızla ilgili '
    'sizleri rahatsız ediyorum. Rica etsek tamamlanacak servis kaydınız için '
    'bizlere konum gönderebilir misiniz?'
)


def get_whatsapp_location_request_template() -> str:
    settings = SiteSettings.objects.first()
    raw = getattr(settings, 'whatsapp_location_request_template', None) if settings else None
    if raw and str(raw).strip():
        return str(raw).strip()
    return DEFAULT_WHATSAPP_LOCATION_REQUEST_TEMPLATE


def render_whatsapp_location_request_message(*, site_name: str, ariza: str) -> str:
    template = get_whatsapp_location_request_template()
    try:
        return template.format(site_name=site_name, ariza=ariza)
    except (KeyError, ValueError):
        return DEFAULT_WHATSAPP_LOCATION_REQUEST_TEMPLATE.format(
            site_name=site_name,
            ariza=ariza,
        )
