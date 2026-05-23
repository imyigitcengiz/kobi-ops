from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods

from common.decorators import json_auth_required, permission_required
from core_settings.models import StatusOption, WhatsAppTemplate
from core_settings.status_defaults import ensure_default_statuses
from sales_leads.models import SalesLead
from tools.models import WhatsappConnection
from tools.whatsapp_scenarios import _normalize_trigger_value, _parse_trigger_tokens
from tools.views import _json_body

SCENARIO_HINTS = {
    WhatsAppTemplate.SCENARIO_SERVICE_CREATED: {
        'description': 'Servis kaydı ilk kez oluşturulduğunda çalışır. "Açılış durumu" = kayıt hangi durumla işaretlendi (ör. aktif, beklemede).',
        'show_from': False,
        'show_to': True,
        'from_label': '',
        'to_label': 'İlk açılış durumu (kayıt neyle işaretlendi)',
        'example': 'Açılış = aktif → sadece "aktif" ile açılan yeni servislerde mesaj gider.',
    },
    WhatsAppTemplate.SCENARIO_SERVICE_STATUS: {
        'description': 'Mevcut servisin durumu değiştiğinde çalışır. Eski ve yeni durumu birlikte tanımlayın.',
        'show_from': True,
        'show_to': True,
        'from_label': 'Eski durum (önce neydi)',
        'to_label': 'Yeni durum (sonra ne oldu)',
        'example': 'aktif → tamamlandı = tamamlanma anında mesaj gider. Birden fazla eski durum seçilebilir (veya mantığı).',
    },
    WhatsAppTemplate.SCENARIO_SALES_LEAD_CREATED: {
        'description': 'Satış kaydı ilk kez eklendiğinde çalışır.',
        'show_from': False,
        'show_to': True,
        'from_label': '',
        'to_label': 'İlk kayıt durumu',
        'example': 'Açılış = tamamlandı → satış tamamlanmış olarak açılan kayıtlarda.',
    },
    WhatsAppTemplate.SCENARIO_SALES_LEAD_STATUS: {
        'description': 'Satış kaydının durumu değiştiğinde çalışır.',
        'show_from': True,
        'show_to': True,
        'from_label': 'Eski durum',
        'to_label': 'Yeni durum',
        'example': 'beklemede → tamamlandı',
    },
    WhatsAppTemplate.SCENARIO_CUSTOMER_CREATED: {
        'description': 'Yeni müşteri kartı oluşturulduğunda çalışır. Durum koşulu yoktur.',
        'show_from': False,
        'show_to': False,
        'from_label': '',
        'to_label': '',
        'example': 'Her yeni müşteride tek sefer.',
    },
}

RULE_PRESETS = [
    {
        'id': 'service_first_aktif',
        'label': 'İlk açılış · aktif',
        'title': 'Servis ilk kayıt — aktif',
        'scenario': WhatsAppTemplate.SCENARIO_SERVICE_CREATED,
        'trigger_from': '',
        'trigger_to_name': 'aktif',
        'message': (
            'Merhaba [name],\n\n'
            '#[servis_no] servis kaydınız [yeni_durum] olarak açıldı.\n'
            'Arıza: [arıza]\n'
            'Öncelik: [oncelik]\n'
            'Bölge: [bölge]\n\n'
            'En kısa sürede dönüş yapılacaktır.'
        ),
    },
    {
        'id': 'service_first_beklemede',
        'label': 'İlk açılış · beklemede',
        'title': 'Servis ilk kayıt — beklemede',
        'scenario': WhatsAppTemplate.SCENARIO_SERVICE_CREATED,
        'trigger_from': '',
        'trigger_to_name': 'beklemede',
        'message': (
            'Merhaba [name],\n\n'
            '#[servis_no] kaydınız [yeni_durum] durumunda oluşturuldu.\n'
            'Arıza: [arıza]\n'
            'Sıraya alındığınızda bilgilendirileceksiniz.'
        ),
    },
    {
        'id': 'service_status_done',
        'label': 'aktif → tamamlandı',
        'title': 'Servis tamamlandı bildirimi',
        'scenario': WhatsAppTemplate.SCENARIO_SERVICE_STATUS,
        'trigger_from_name': 'aktif',
        'trigger_to_name': 'tamamlandı',
        'message': (
            'Merhaba [name],\n\n'
            '#[servis_no] servis kaydınız [eski_durum] durumundan [yeni_durum] durumuna alındı.\n'
            'Teşekkür ederiz.'
        ),
    },
    {
        'id': 'service_status_pending_active',
        'label': 'beklemede → aktif',
        'title': 'Servis işleme alındı',
        'scenario': WhatsAppTemplate.SCENARIO_SERVICE_STATUS,
        'trigger_from_name': 'beklemede',
        'trigger_to_name': 'aktif',
        'message': (
            'Merhaba [name],\n\n'
            '#[servis_no] servis kaydınız işleme alındı ([yeni_durum]).\n'
            'Arıza: [arıza]'
        ),
    },
    {
        'id': 'customer_welcome',
        'label': 'Yeni müşteri hoş geldin',
        'title': 'Müşteri ilk kayıt',
        'scenario': WhatsAppTemplate.SCENARIO_CUSTOMER_CREATED,
        'trigger_from': '',
        'trigger_to': '',
        'message': (
            'Merhaba [name],\n\n'
            'Kaydınız oluşturuldu. Sorularınız için bize [phone] üzerinden ulaşabilirsiniz.\n'
            'Bölge: [bölge]'
        ),
    },
    {
        'id': 'sales_completed',
        'label': 'Satış · tamamlandı',
        'title': 'Satış tamamlandı',
        'scenario': WhatsAppTemplate.SCENARIO_SALES_LEAD_STATUS,
        'trigger_from_name': 'pending',
        'trigger_to_name': 'completed',
        'message': (
            'Merhaba [name],\n\n'
            'Satış kaydınız [yeni_durum] olarak güncellendi.\n'
            'Teşekkür ederiz.'
        ),
    },
]


def _serialize_template(t: WhatsAppTemplate) -> dict:
    trigger_to_raw = t.trigger_to or t.trigger_value or ''
    return {
        'id': t.id,
        'title': t.title,
        'message': t.message,
        'scenario': t.scenario,
        'scenario_label': t.get_scenario_display(),
        'trigger_from': _parse_trigger_tokens(t.trigger_from or ''),
        'trigger_to': _parse_trigger_tokens(trigger_to_raw),
        'auto_send': t.auto_send,
        'is_active': t.is_active,
        'connection_id': t.connection_id,
        'sort_order': t.sort_order,
    }


@require_http_methods(['GET'])
@json_auth_required
@permission_required('tools.whatsapp_scenarios', 'tools.whatsapp', any_perm=True)
def whatsapp_scenario_meta_api(request):
    ensure_default_statuses()
    service_statuses = [
        {'value': str(s.id), 'label': s.name}
        for s in StatusOption.objects.order_by('sort_order', 'name')
    ]
    sales_statuses = [
        {'value': code, 'label': label}
        for code, label in SalesLead.STATUS_CHOICES
    ]
    scenarios = [
        {'value': code, 'label': label, 'hint': SCENARIO_HINTS.get(code, {})}
        for code, label in WhatsAppTemplate.SCENARIO_CHOICES
    ]
    connections = [
        {'id': c.id, 'name': c.name, 'phone': c.phone}
        for c in WhatsappConnection.objects.order_by('-last_connected_at', 'name')
    ]
    return JsonResponse({
        'ok': True,
        'scenarios': scenarios,
        'scenario_hints': SCENARIO_HINTS,
        'service_statuses': service_statuses,
        'sales_statuses': sales_statuses,
        'connections': connections,
        'placeholders': [
            '[name]', '[arıza]', '[status]', '[yeni_durum]', '[eski_durum]', '[onceki_durum]',
            '[oncelik]', '[servis_no]', '[not]', '[bölge]', '[phone]', '[tarih]',
            '[normal_fiyat]', '[indirimli_fiyat]', '[list_price]', '[discounted_price]',
        ],
        'rule_presets': RULE_PRESETS,
    })


@require_http_methods(['GET', 'POST'])
@json_auth_required
@permission_required('tools.whatsapp_scenarios', 'tools.whatsapp', any_perm=True)
def whatsapp_scenario_templates_api(request):
    if request.method == 'GET':
        items = [_serialize_template(t) for t in WhatsAppTemplate.objects.all()]
        return JsonResponse({'ok': True, 'templates': items})

    body = _json_body(request) or {}
    title = (body.get('title') or '').strip()
    message = (body.get('message') or '').strip()
    scenario = (body.get('scenario') or WhatsAppTemplate.SCENARIO_SERVICE_STATUS).strip()
    if not title or not message:
        return JsonResponse({'ok': False, 'error': 'Kural adı ve mesaj zorunludur.'}, status=400)
    valid_scenarios = {code for code, _ in WhatsAppTemplate.SCENARIO_CHOICES}
    if scenario not in valid_scenarios:
        return JsonResponse({'ok': False, 'error': 'Geçersiz senaryo.'}, status=400)

    connection_id = body.get('connection_id')
    conn = WhatsappConnection.objects.filter(pk=connection_id).first() if connection_id else None

    trigger_from = _normalize_trigger_value(body.get('trigger_from'))
    trigger_to = _normalize_trigger_value(body.get('trigger_to'))

    template = WhatsAppTemplate.objects.create(
        title=title,
        message=message,
        scenario=scenario,
        trigger_from=trigger_from,
        trigger_to=trigger_to,
        auto_send=bool(body.get('auto_send', True)),
        is_active=bool(body.get('is_active', True)),
        connection=conn,
        sort_order=int(body.get('sort_order') or 0),
    )
    return JsonResponse({'ok': True, 'template': _serialize_template(template)}, status=201)


@require_http_methods(['PATCH', 'DELETE'])
@json_auth_required
@permission_required('tools.whatsapp_scenarios', 'tools.whatsapp', any_perm=True)
def whatsapp_scenario_template_detail_api(request, pk):
    template = get_object_or_404(WhatsAppTemplate, pk=pk)
    if request.method == 'DELETE':
        template.delete()
        return JsonResponse({'ok': True})

    body = _json_body(request) or {}
    if 'title' in body:
        template.title = (body.get('title') or '').strip()
    if 'message' in body:
        template.message = (body.get('message') or '').strip()
    if 'scenario' in body:
        scenario = (body.get('scenario') or '').strip()
        valid = {code for code, _ in WhatsAppTemplate.SCENARIO_CHOICES}
        if scenario not in valid:
            return JsonResponse({'ok': False, 'error': 'Geçersiz senaryo.'}, status=400)
        template.scenario = scenario
    if 'trigger_from' in body:
        template.trigger_from = _normalize_trigger_value(body.get('trigger_from'))
    if 'trigger_to' in body:
        template.trigger_to = _normalize_trigger_value(body.get('trigger_to'))
    if 'auto_send' in body:
        template.auto_send = bool(body.get('auto_send'))
    if 'is_active' in body:
        template.is_active = bool(body.get('is_active'))
    if 'sort_order' in body:
        template.sort_order = int(body.get('sort_order') or 0)
    if 'connection_id' in body:
        cid = body.get('connection_id')
        template.connection = WhatsappConnection.objects.filter(pk=cid).first() if cid else None

    if not template.title or not template.message:
        return JsonResponse({'ok': False, 'error': 'Kural adı ve mesaj boş olamaz.'}, status=400)

    template.save()
    return JsonResponse({'ok': True, 'template': _serialize_template(template)})
