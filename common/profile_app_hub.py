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
    """Uygulama slug'ına göre alt sayfa kısayolları."""
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
            ('Firma bul', 'contact_firma_bul', 'search'),
        ],
        'app.kobi.field_teams': [
            ('Ekipler', 'team_network', 'users-round'),
        ],
        'app.kobi.personnel': [
            ('Personel', 'accounting_personnel', 'id-card'),
        ],
        'app.kobi.payroll': [
            ('Maaş döngüsü', 'accounting_payroll', 'wallet'),
            ('Raporlar', 'accounting_reports', 'bar-chart-3'),
        ],
        'app.kobi.finance': [
            ('Gelir & gider', 'accounting_finance', 'receipt'),
            ('Muhasebe özeti', 'accounting_hub', 'layout-grid'),
        ],
        'app.kobi.sales': [
            ('Satış özeti', 'sales_lead_dashboard', 'badge-dollar-sign'),
            ('Kayıtlar', 'sales_lead_list', 'list'),
        ],
        'app.kobi.campaigns': [
            ('Kampanyalar', 'outreach_campaigns', 'megaphone'),
            ('İletişim merkezi', 'outreach_hub', 'messages-square'),
        ],
        'app.agency.retainer_studio': [
            ('Retainer stüdyosu', 'agency_hub', 'palette'),
        ],
        'app.agency.clients': [
            ('Müşteriler', 'customers', 'sparkles'),
        ],
        'app.agency.freelancers': [
            ('Freelancer ağı', 'solution_network', 'user-plus'),
        ],
        'app.agency.firms': [
            ('Firmalar', 'contact_firmalar', 'building-2'),
        ],
        'app.agency.project_sales': [
            ('Pipeline', 'sales_lead_dashboard', 'trending-up'),
            ('Kayıtlar', 'sales_lead_list', 'list'),
        ],
        'app.agency.finance': [
            ('Finans', 'accounting_finance', 'receipt'),
        ],
        'app.agency.campaigns': [
            ('Kampanyalar', 'outreach_campaigns', 'megaphone'),
        ],
        'int.whatsapp_bridge': [
            ('QR bağlantı', 'tools_whatsapp_baglan', 'message-circle'),
        ],
        'int.whatsapp_api': [
            ('API ayarları', 'tools_whatsapp_api_settings', 'cloud'),
        ],
        'int.media': [
            ('Medya kütüphanesi', 'tools_media_library', 'images'),
        ],
    }

    for label, url_name, icon in mapping.get(slug, ()):
        item = _quick_link(label, url_name, icon=icon)
        if item:
            links.append(item)

    hub = _url(app.get('hub_url_name'))
    if hub and (not links or links[0]['url'] != hub):
        primary = {'label': 'Ana ekran', 'url': hub, 'icon': app.get('icon', 'layout-grid')}
        if not any(l['url'] == hub for l in links):
            links.insert(0, primary)

    return links[:5]


def build_profile_app_hub_metrics(user, app: dict) -> list[dict]:
    """Mini hub üst KPI kartları."""
    slug = app['slug']
    metrics: list[dict] = []

    try:
        if slug in ('app.kobi.service_desk',):
            from services.models import ServiceRecord
            open_count = ServiceRecord.objects.exclude(
                status__name__icontains='tamam'
            ).count()
            metrics.append({'label': 'Açık iş emri', 'value': open_count, 'icon': 'clipboard-list'})
        elif slug in ('app.kobi.customers', 'app.agency.clients'):
            from customers.models import Customer
            metrics.append({'label': 'Kayıtlı müşteri', 'value': Customer.objects.count(), 'icon': 'users'})
        elif slug == 'app.agency.retainer_studio':
            from analytics.agency_summary import build_agency_panel_context
            ctx = build_agency_panel_context(user)
            metrics.append({'label': 'Proje', 'value': ctx.get('agency_project_count', 0), 'icon': 'folder'})
            metrics.append({'label': 'Aktif retainer', 'value': ctx.get('agency_active_count', 0), 'icon': 'palette'})
            monthly = ctx.get('agency_retainer_monthly')
            if monthly is not None:
                metrics.append({'label': 'Aylık MRR', 'value': f'₺{monthly:,.0f}', 'icon': 'wallet'})
        elif slug in ('app.kobi.personnel',):
            from core_settings.models import ServicePersonnel
            metrics.append({'label': 'Personel', 'value': ServicePersonnel.objects.count(), 'icon': 'id-card'})
        elif slug in ('app.kobi.finance', 'app.agency.finance'):
            from core_settings.models import FinanceRecord
            metrics.append({'label': 'Finans kaydı', 'value': FinanceRecord.objects.count(), 'icon': 'receipt'})
        elif slug in ('app.kobi.sales', 'app.agency.project_sales'):
            from sales_leads.models import SalesLead
            metrics.append({'label': 'Satış kaydı', 'value': SalesLead.objects.count(), 'icon': 'badge-dollar-sign'})
    except Exception:
        pass

    if not metrics:
        metrics.append({'label': 'Durum', 'value': 'Aktif', 'icon': 'check-circle'})

    return metrics[:4]
