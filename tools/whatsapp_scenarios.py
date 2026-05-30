from __future__ import annotations

import logging
import re
import unicodedata

from django.db import transaction

from core_settings.models import WhatsAppTemplate
from tools.models import WhatsappOutboundMessage
from tools.phone_utils import is_whatsapp_eligible, normalize_phone
from tools.whatsapp_send_views import _log_and_send

logger = logging.getLogger(__name__)

CHANGE_SCENARIOS = {
    WhatsAppTemplate.SCENARIO_SERVICE_STATUS,
    WhatsAppTemplate.SCENARIO_SALES_LEAD_STATUS,
}
CREATE_SCENARIOS = {
    WhatsAppTemplate.SCENARIO_SERVICE_CREATED,
    WhatsAppTemplate.SCENARIO_SALES_LEAD_CREATED,
    WhatsAppTemplate.SCENARIO_CUSTOMER_CREATED,
}


def normalize_template_key(raw: str) -> str:
    text = unicodedata.normalize('NFKD', (raw or '').lower().strip())
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return (
        text.replace('ş', 's')
        .replace('ı', 'i')
        .replace('ç', 'c')
        .replace('ö', 'o')
        .replace('ü', 'u')
        .replace('ğ', 'g')
        .replace(' ', '')
    )


def apply_template_variables(template_text: str, context: dict) -> str:
    if not template_text:
        return ''
    value_map = {
        'name': context.get('name') or '-',
        'musteri': context.get('name') or '-',
        'customer': context.get('name') or '-',
        'ariza': context.get('ariza') or '-',
        'servis': context.get('ariza') or '-',
        'servicetype': context.get('ariza') or '-',
        'status': context.get('status') or '-',
        'durum': context.get('status') or context.get('durum') or '-',
        'yeni_durum': context.get('yeni_durum') or context.get('status') or '-',
        'eski_durum': context.get('eski_durum') or '-',
        'onceki_durum': context.get('onceki_durum') or context.get('eski_durum') or '-',
        'oncelik': context.get('oncelik') or '-',
        'priority': context.get('oncelik') or '-',
        'servis_id': context.get('servis_id') or '-',
        'servis_no': context.get('servis_no') or context.get('servis_id') or '-',
        'note': context.get('note') or '-',
        'not': context.get('note') or '-',
        'phone': context.get('phone') or '-',
        'telefon': context.get('phone') or '-',
        'bolge': context.get('region') or '-',
        'region': context.get('region') or '-',
        'tarih': context.get('date') or '-',
        'date': context.get('date') or '-',
    }

    def replacer(match):
        token = normalize_template_key(match.group(1))
        return value_map.get(token, match.group(0))

    return re.sub(r'\[([^\]]+)\]', replacer, template_text)


def build_service_context(service, *, old_status_name: str | None = None) -> dict:
    service_types = ', '.join(st.name for st in service.service_types.all()) or '-'
    customer = service.customer
    current_status = service.status.name if service.status_id else '-'
    priority = service.priority.name if service.priority_id else '-'
    return {
        'name': customer.name,
        'ariza': service_types,
        'status': current_status,
        'durum': current_status,
        'yeni_durum': current_status,
        'eski_durum': old_status_name or '-',
        'onceki_durum': old_status_name or '-',
        'oncelik': priority,
        'servis_id': str(service.id),
        'servis_no': str(service.id),
        'note': (service.notes or '').strip() or '-',
        'region': customer.region or '-',
        'phone': customer.phone or '-',
        'date': service.updated_at.strftime('%d.%m.%Y') if service.updated_at else '-',
        'list_price': _format_price(getattr(service, 'list_price', None)),
        'discounted_price': _format_price(getattr(service, 'discounted_price', None)),
        'normal_fiyat': _format_price(getattr(service, 'list_price', None)),
        'indirimli_fiyat': _format_price(getattr(service, 'discounted_price', None)),
    }


def _format_price(value) -> str:
    if value is None or value == '':
        return '-'
    try:
        return f'{float(value):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    except (TypeError, ValueError):
        return str(value)


def build_sales_lead_context(lead, *, old_status_code: str | None = None) -> dict:
    customer = lead.customer
    status_choices = dict(lead.STATUS_CHOICES)
    new_label = status_choices.get(lead.status, lead.status)
    old_label = status_choices.get(old_status_code, old_status_code) if old_status_code else '-'
    return {
        'name': customer.name,
        'ariza': '-',
        'status': new_label,
        'durum': new_label,
        'yeni_durum': new_label,
        'eski_durum': old_label,
        'onceki_durum': old_label,
        'oncelik': '-',
        'note': (lead.notes or '').strip() or '-',
        'region': customer.region or '-',
        'phone': customer.phone or '-',
        'date': lead.sale_date.strftime('%d.%m.%Y') if lead.sale_date else '-',
    }


def build_customer_context(customer) -> dict:
    contract = customer.contract_date.strftime('%d.%m.%Y') if customer.contract_date else '-'
    return {
        'name': customer.name,
        'ariza': '-',
        'status': '-',
        'durum': '-',
        'yeni_durum': '-',
        'eski_durum': '-',
        'onceki_durum': '-',
        'oncelik': '-',
        'note': '-',
        'region': customer.region or '-',
        'phone': customer.phone or '-',
        'date': contract,
    }


def _parse_trigger_tokens(configured: str) -> list[str]:
    configured = (configured or '').strip()
    if not configured or configured == '*':
        return []
    return [t.strip() for t in configured.split(',') if t.strip()]


def _normalize_trigger_value(value) -> str:
    if value is None:
        return ''
    if isinstance(value, list):
        tokens = []
        for item in value:
            part = str(item).strip()
            if part and part not in tokens:
                tokens.append(part)
        return ','.join(tokens)
    return str(value).strip()


def _effective_trigger_to(template: WhatsAppTemplate) -> str:
    configured = (template.trigger_to or '').strip()
    if configured:
        return configured
    return (template.trigger_value or '').strip()


def _configured_matches(configured: str, actual_values: list[str] | None) -> bool:
    configured = (configured or '').strip()
    if not configured or configured == '*':
        return True
    tokens = _parse_trigger_tokens(configured)
    if not tokens:
        return True
    values = [str(v).strip() for v in (actual_values or []) if v is not None and str(v).strip()]
    if not values:
        return False
    for token in tokens:
        for actual in values:
            if token == actual:
                return True
            if normalize_template_key(token) == normalize_template_key(actual):
                return True
    return False


def template_matches_event(
    template: WhatsAppTemplate,
    *,
    event_from_values: list[str] | None = None,
    event_to_values: list[str] | None = None,
) -> bool:
    trigger_from = (template.trigger_from or '').strip()
    trigger_to = _effective_trigger_to(template)

    if template.scenario in CREATE_SCENARIOS:
        if trigger_from:
            return False
        return _configured_matches(trigger_to, event_to_values)

    if template.scenario in CHANGE_SCENARIOS:
        return (
            _configured_matches(trigger_from, event_from_values)
            and _configured_matches(trigger_to, event_to_values)
        )

    return True


def matching_templates_for_event(
    scenario: str,
    *,
    event_from_values: list[str] | None = None,
    event_to_values: list[str] | None = None,
):
    qs = WhatsAppTemplate.objects.filter(
        scenario=scenario,
        is_active=True,
        auto_send=True,
    ).order_by('sort_order', 'id')
    return [
        tpl for tpl in qs
        if template_matches_event(
            tpl,
            event_from_values=event_from_values,
            event_to_values=event_to_values,
        )
    ]


def matching_active_templates_for_event(
    scenario: str,
    *,
    event_from_values: list[str] | None = None,
    event_to_values: list[str] | None = None,
):
    qs = WhatsAppTemplate.objects.filter(
        scenario=scenario,
        is_active=True,
    ).order_by('sort_order', 'id')
    return [
        tpl for tpl in qs
        if template_matches_event(
            tpl,
            event_from_values=event_from_values,
            event_to_values=event_to_values,
        )
    ]


def _send_template(template: WhatsAppTemplate, *, phone_raw: str, context: dict, customer_id=None):
    phone_norm = normalize_phone(phone_raw)
    if not is_whatsapp_eligible(phone_raw, phone_norm):
        return None, 'Geçersiz numara veya sabit hat.'

    message = apply_template_variables(template.message, context)
    if not message.strip():
        return None, 'Mesaj boş.'

    try:
        _, outbound, err, _ = _log_and_send(
            phone_raw=phone_raw,
            phone_norm=phone_norm,
            message=message,
            connection_id=template.connection_id,
            recipient_name=context.get('name') or '',
            customer_id=customer_id,
            source=WhatsappOutboundMessage.SOURCE_AUTO,
            send_type=WhatsappOutboundMessage.SEND_AUTO,
            scenario=template.scenario,
        )
    except Exception as exc:
        logger.exception('Scenario WhatsApp send failed')
        return None, str(exc)

    if err:
        return outbound, err
    return outbound, None


def dispatch_scenario_whatsapp(
    scenario: str,
    *,
    event_from_values: list[str] | None = None,
    event_to_values: list[str] | None = None,
    phone_raw: str = '',
    context: dict | None = None,
    customer_id=None,
):
    templates = matching_templates_for_event(
        scenario,
        event_from_values=event_from_values,
        event_to_values=event_to_values,
    )
    if not templates:
        return []

    results = []
    ctx = context or {}
    for template in templates:
        outbound, err = _send_template(
            template,
            phone_raw=phone_raw,
            context=ctx,
            customer_id=customer_id,
        )
        results.append({
            'template_id': template.id,
            'title': template.title,
            'ok': err is None,
            'error': err,
            'message_id': outbound.id if outbound else None,
        })
    return results


def schedule_scenario_whatsapp(scenario=None, **kwargs):
    if scenario is not None:
        kwargs['scenario'] = scenario

    def _run():
        try:
            dispatch_scenario_whatsapp(**kwargs)
        except Exception:
            logger.exception('Otomatik WhatsApp senaryosu çalıştırılamadı')

    transaction.on_commit(_run)
