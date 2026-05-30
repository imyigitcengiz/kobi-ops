"""Profil uygulama mini hub — KPI ve hızlı bağlantılar."""

from __future__ import annotations

from django.urls import NoReverseMatch, reverse


def _url(name: str | None) -> str | None:
    if not name:
        return None
    try:
        return reverse(name)
    except NoReverseMatch:
        return None


def _quick_link(label: str, url_name: str, *, icon: str = 'arrow-right') -> dict | None:
    url = _url(url_name)
    if not url:
        return None
    return {'label': label, 'url': url, 'icon': icon}


def profile_app_quick_links(app: dict, user) -> list[dict]:
    slug = app['slug']
    links: list[dict] = []

    mapping: dict[str, list[tuple[str, str, str]]] = {
        'app.kobi.service_desk': [
            ('İş emirleri', 'services', 'clipboard-list'),
            ('Özet', 'dashboard', 'layout-dashboard'),
        ],
        'app.kobi.customers': [
            ('Müşteri listesi', 'customers', 'users'),
            ('Rehber özeti', 'contact_hub', 'book-user'),
        ],
        'app.kobi.firms': [
            ('Firmalar', 'contact_firmalar', 'building-2'),
        ],
        'app.kobi.field_teams': [('Ekipler', 'team_network', 'users-round')],
        'app.kobi.personnel': [('Personel', 'accounting_personnel', 'id-card')],
        'app.kobi.payroll': [
            ('Maaş döngüsü', 'accounting_payroll', 'wallet'),
        ],
        'app.kobi.finance': [('Gelir & gider', 'accounting_finance', 'receipt')],
        'app.kobi.sales': [
            ('Satış özeti', 'sales_lead_dashboard', 'badge-dollar-sign'),
            ('Kayıtlar', 'sales_lead_list', 'list'),
        ],
        'app.kobi.campaigns': [
            ('Kampanyalar', 'outreach_campaigns', 'megaphone'),
        ],
        'app.agency.retainer_studio': [('Retainer stüdyosu', 'agency_hub', 'palette')],
        'app.agency.clients': [('Müşteriler', 'agency_clients', 'sparkles')],
        'app.agency.freelancers': [('Freelancer ağı', 'agency_freelancers', 'user-plus')],
        'app.agency.firms': [('Firmalar', 'agency_firms', 'building-2')],
        'app.agency.project_sales': [('Pipeline', 'agency_pipeline', 'trending-up')],
        'app.agency.finance': [('Finans', 'agency_finance', 'receipt')],
        'app.agency.campaigns': [('Kampanyalar', 'agency_campaigns', 'megaphone')],
        'int.whatsapp_bridge': [('QR bağlantı', 'tools_whatsapp_baglan', 'message-circle')],
        'int.whatsapp_api': [('API ayarları', 'tools_whatsapp_api_settings', 'cloud')],
        'int.media': [('Medya kütüphanesi', 'tools_media_library', 'images')],
    }

    for label, url_name, icon in mapping.get(slug, ()):
        item = _quick_link(label, url_name, icon=icon)
        if item:
            links.append(item)

    hub = _url(app.get('hub_url_name'))
    if hub and not any(l['url'] == hub for l in links):
        links.insert(0, {'label': 'Ana ekran', 'url': hub, 'icon': app.get('icon', 'layout-grid')})

    return links[:5]


def build_profile_app_hub_metrics(user, app: dict) -> list[dict]:
    slug = app['slug']
    metrics: list[dict] = []

    try:
        if slug == 'app.kobi.service_desk':
            from services.models import ServiceRecord
            metrics.append({
                'label': 'Açık iş emri',
                'value': ServiceRecord.objects.count(),
                'icon': 'clipboard-list',
            })
        elif slug in ('app.kobi.customers', 'app.agency.clients'):
            if slug.startswith('app.agency.'):
                from agency.models import AgencyClient
                metrics.append({'label': 'Ajans müşterisi', 'value': AgencyClient.objects.count(), 'icon': 'users'})
            else:
                from customers.models import Customer
                metrics.append({'label': 'Kayıtlı müşteri', 'value': Customer.objects.count(), 'icon': 'users'})
        elif slug == 'app.agency.retainer_studio':
            from agency.summary import build_agency_panel_context
            ctx = build_agency_panel_context(user)
            metrics.append({'label': 'Proje', 'value': ctx.get('agency_project_count', 0), 'icon': 'folder'})
            metrics.append({'label': 'Aktif retainer', 'value': ctx.get('agency_active_count', 0), 'icon': 'palette'})
        elif slug == 'app.agency.freelancers':
            from agency.models import AgencyFreelancer
            metrics.append({'label': 'Freelancer', 'value': AgencyFreelancer.objects.filter(is_active=True).count(), 'icon': 'user-plus'})
        elif slug == 'app.agency.project_sales':
            from agency.models import AgencyDeal
            metrics.append({'label': 'Pipeline', 'value': AgencyDeal.objects.count(), 'icon': 'trending-up'})
        elif slug == 'app.agency.finance':
            from agency.models import AgencyFinanceEntry
            metrics.append({'label': 'Kayıt', 'value': AgencyFinanceEntry.objects.count(), 'icon': 'receipt'})
        elif slug == 'app.kobi.personnel':
            from core_settings.models import ServicePersonnel
            metrics.append({'label': 'Personel', 'value': ServicePersonnel.objects.count(), 'icon': 'id-card'})
    except Exception:
        pass

    if not metrics:
        metrics.append({'label': 'Durum', 'value': 'Aktif', 'icon': 'check-circle'})

    return metrics[:4]
