"""Kurulum profiline özel uygulamalar — kullanıcının gördüğü katman.

Monolitik backend modülleri (contact, accounting…) burada listelenmez;
her profil kendi uygulama setini görür (KOBİ ≠ Ajans).
"""

from __future__ import annotations

APP_CATEGORY_LABELS: dict[str, tuple[str, str]] = {
    'operasyon': ('Operasyon & saha', 'wrench'),
    'iliskiler': ('Müşteri & ilişkiler', 'users'),
    'finans': ('Finans', 'wallet'),
    'proje': ('Proje & retainer', 'palette'),
    'iletisim': ('İletişim', 'messages-square'),
    'entegrasyon': ('Entegrasyonlar', 'plug'),
}

# vertical → varsayılan açık uygulama slug'ları (profil paketi)
VERTICAL_PROFILE_PRESETS: dict[str, tuple[str, ...]] = {
    'kobi': (
        'app.kobi.service_desk',
        'app.kobi.customers',
        'app.kobi.firms',
        'app.kobi.field_teams',
        'app.kobi.personnel',
        'app.kobi.payroll',
        'app.kobi.finance',
        'app.kobi.sales',
        'app.kobi.campaigns',
        'int.whatsapp_bridge',
        'int.whatsapp_api',
        'int.media',
    ),
    'agency': (
        'app.agency.retainer_studio',
        'app.agency.clients',
        'app.agency.freelancers',
        'app.agency.firms',
        'app.agency.project_sales',
        'app.agency.finance',
        'app.agency.campaigns',
        'int.whatsapp_bridge',
        'int.whatsapp_api',
        'int.media',
    ),
}

PROFILE_APPS: tuple[dict, ...] = (
    # --- KOBİ & saha servis ---
    {
        'slug': 'app.kobi.service_desk',
        'vertical': 'kobi',
        'category': 'operasyon',
        'name': 'Yardım Masası',
        'summary': 'Saha servis iş emirleri, durum ve saha bildirimleri.',
        'icon': 'headphones',
        'hub_url_name': 'dashboard',
        'access_perm': 'access.services',
        'platform_modules': ('services',),
        'platform_particles': (),
        'sort': 10,
    },
    {
        'slug': 'app.kobi.customers',
        'vertical': 'kobi',
        'category': 'iliskiler',
        'name': 'Müşteri Rehberi',
        'summary': 'Montaj ve servis müşteri kartları.',
        'icon': 'users',
        'hub_url_name': 'customers',
        'access_perm': 'access.contact',
        'platform_modules': ('contact',),
        'platform_particles': ('p.contact.customers',),
        'sort': 20,
    },
    {
        'slug': 'app.kobi.firms',
        'vertical': 'kobi',
        'category': 'iliskiler',
        'name': 'Firma & Maps',
        'summary': 'Bayi, tedarikçi ve Maps firma araması.',
        'icon': 'building-2',
        'hub_url_name': 'contact_firmalar',
        'access_perm': 'access.contact',
        'platform_modules': ('contact',),
        'platform_particles': ('p.contact.firms',),
        'sort': 30,
    },
    {
        'slug': 'app.kobi.field_teams',
        'vertical': 'kobi',
        'category': 'operasyon',
        'name': 'Saha Ekipleri',
        'summary': 'Montaj/servis ekipleri ve ürün yetkinlikleri.',
        'icon': 'users-round',
        'hub_url_name': 'team_network',
        'access_perm': 'access.contact',
        'platform_modules': ('contact',),
        'platform_particles': ('p.contact.teams',),
        'sort': 40,
    },
    {
        'slug': 'app.kobi.personnel',
        'vertical': 'kobi',
        'category': 'operasyon',
        'name': 'Personel Yönetimi',
        'summary': 'Sigortalı personel, ekip ataması, saha yetkinlikleri.',
        'icon': 'id-card',
        'hub_url_name': 'accounting_personnel',
        'access_perm': 'access.accounting',
        'platform_modules': ('accounting',),
        'platform_particles': ('p.accounting.personnel',),
        'sort': 50,
    },
    {
        'slug': 'app.kobi.payroll',
        'vertical': 'kobi',
        'category': 'finans',
        'name': 'Maaş & Avans',
        'summary': 'Aylık maaş döngüsü — brüt − avans = net.',
        'icon': 'wallet',
        'hub_url_name': 'accounting_payroll',
        'access_perm': 'access.accounting',
        'platform_modules': ('accounting',),
        'platform_particles': ('p.accounting.payroll', 'p.accounting.personnel'),
        'sort': 60,
    },
    {
        'slug': 'app.kobi.finance',
        'vertical': 'kobi',
        'category': 'finans',
        'name': 'Gelir & Gider',
        'summary': 'Kasa hareketleri ve dönem özeti.',
        'icon': 'receipt',
        'hub_url_name': 'accounting_finance',
        'access_perm': 'access.accounting',
        'platform_modules': ('accounting',),
        'platform_particles': ('p.accounting.finance',),
        'sort': 70,
    },
    {
        'slug': 'app.kobi.sales',
        'vertical': 'kobi',
        'category': 'finans',
        'name': 'Satış Kayıtları',
        'summary': 'B2B proje satışları ve tahsilat.',
        'icon': 'badge-dollar-sign',
        'hub_url_name': 'sales_lead_dashboard',
        'access_perm': 'access.accounting',
        'platform_modules': ('accounting',),
        'platform_particles': ('p.accounting.sales',),
        'sort': 80,
    },
    {
        'slug': 'app.kobi.campaigns',
        'vertical': 'kobi',
        'category': 'iletisim',
        'name': 'WhatsApp Kampanyaları',
        'summary': 'Toplu mesaj ve müşteri iletişimi.',
        'icon': 'megaphone',
        'hub_url_name': 'outreach_hub',
        'access_perm': 'access.outreach',
        'platform_modules': ('outreach',),
        'platform_particles': ('p.outreach.campaigns',),
        'sort': 90,
    },
    # --- Ajans — özel modüller (/ajans/) ---
    {
        'slug': 'app.agency.retainer_studio',
        'vertical': 'agency',
        'category': 'proje',
        'name': 'Retainer Stüdyosu',
        'summary': 'Aylık retainer projeleri ve MRR özeti.',
        'icon': 'palette',
        'hub_url_name': 'agency_hub',
        'access_perm': 'access.agency',
        'platform_modules': ('agency_retainer',),
        'platform_particles': ('p.agency.retainer',),
        'sort': 10,
    },
    {
        'slug': 'app.agency.clients',
        'vertical': 'agency',
        'category': 'iliskiler',
        'name': 'Müşteri & Marka',
        'summary': 'Ajans müşteri ve marka kartları.',
        'icon': 'sparkles',
        'hub_url_name': 'agency_clients',
        'access_perm': 'access.agency',
        'platform_modules': ('agency_clients',),
        'platform_particles': (),
        'sort': 20,
    },
    {
        'slug': 'app.agency.freelancers',
        'vertical': 'agency',
        'category': 'proje',
        'name': 'Freelancer Ağı',
        'summary': 'Taşeron ve tasarımcı kadrosu.',
        'icon': 'user-plus',
        'hub_url_name': 'agency_freelancers',
        'access_perm': 'access.agency',
        'platform_modules': ('agency_freelancers',),
        'platform_particles': (),
        'sort': 30,
    },
    {
        'slug': 'app.agency.firms',
        'vertical': 'agency',
        'category': 'iliskiler',
        'name': 'Firma Rehberi',
        'summary': 'Potansiyel müşteri firmaları.',
        'icon': 'building-2',
        'hub_url_name': 'agency_firms',
        'access_perm': 'access.agency',
        'platform_modules': ('agency_firms',),
        'platform_particles': (),
        'sort': 40,
    },
    {
        'slug': 'app.agency.project_sales',
        'vertical': 'agency',
        'category': 'finans',
        'name': 'Proje Satış & Pipeline',
        'summary': 'Teklif ve proje bedeli takibi.',
        'icon': 'trending-up',
        'hub_url_name': 'agency_pipeline',
        'access_perm': 'access.agency',
        'platform_modules': ('agency_pipeline',),
        'platform_particles': (),
        'sort': 50,
    },
    {
        'slug': 'app.agency.finance',
        'vertical': 'agency',
        'category': 'finans',
        'name': 'Ajans Finans',
        'summary': 'Ajans gelir-gider kayıtları.',
        'icon': 'receipt',
        'hub_url_name': 'agency_finance',
        'access_perm': 'access.agency',
        'platform_modules': ('agency_finance',),
        'platform_particles': (),
        'sort': 60,
    },
    {
        'slug': 'app.agency.campaigns',
        'vertical': 'agency',
        'category': 'iletisim',
        'name': 'Kampanya Merkezi',
        'summary': 'Ajans müşteri kampanya taslakları.',
        'icon': 'messages-square',
        'hub_url_name': 'agency_campaigns',
        'access_perm': 'access.agency',
        'platform_modules': ('agency_campaigns',),
        'platform_particles': (),
        'sort': 70,
    },
)

PROFILE_INTEGRATIONS: tuple[dict, ...] = (
    {
        'slug': 'int.whatsapp_bridge',
        'vertical': None,
        'category': 'entegrasyon',
        'name': 'WhatsApp Köprüsü (QR)',
        'summary': 'QR hat bağlantısı ve senaryolar.',
        'icon': 'message-circle',
        'hub_url_name': 'tools_whatsapp_baglan',
        'access_perm': 'tools.whatsapp',
        'platform_modules': ('integration_whatsapp_bridge',),
        'platform_particles': (),
        'sort': 200,
    },
    {
        'slug': 'int.whatsapp_api',
        'vertical': None,
        'category': 'entegrasyon',
        'name': 'WhatsApp Business API',
        'summary': 'Meta Cloud API — kampanya gönderimi.',
        'icon': 'cloud',
        'hub_url_name': 'tools_whatsapp_api_settings',
        'access_perm': 'tools.whatsapp',
        'platform_modules': ('integration_whatsapp_api',),
        'platform_particles': (),
        'sort': 210,
    },
    {
        'slug': 'int.media',
        'vertical': None,
        'category': 'entegrasyon',
        'name': 'Medya Kütüphanesi',
        'summary': 'Dosya ve fotoğraf arşivi.',
        'icon': 'images',
        'hub_url_name': 'tools_media_library',
        'access_perm': 'tools.media',
        'platform_modules': ('integration_media',),
        'platform_particles': (),
        'sort': 220,
    },
)

ALL_PROFILE_ITEMS: tuple[dict, ...] = PROFILE_APPS + PROFILE_INTEGRATIONS

LEGACY_TO_PROFILE: dict[str, str] = {
    'contact': 'app.kobi.customers',
    'services': 'app.kobi.service_desk',
    'accounting': 'app.kobi.finance',
    'outreach': 'app.kobi.campaigns',
    'agency_suite': 'app.agency.retainer_studio',
    'agency_retainer': 'app.agency.retainer_studio',
    'agency_clients': 'app.agency.clients',
    'agency_freelancers': 'app.agency.freelancers',
    'agency_firms': 'app.agency.firms',
    'agency_pipeline': 'app.agency.project_sales',
    'agency_finance': 'app.agency.finance',
    'agency_campaigns': 'app.agency.campaigns',
    'integration_whatsapp_bridge': 'int.whatsapp_bridge',
    'integration_whatsapp_api': 'int.whatsapp_api',
    'integration_media': 'int.media',
    'tools': 'int.whatsapp_bridge',
}


def profile_app_by_slug(slug: str) -> dict | None:
    for item in ALL_PROFILE_ITEMS:
        if item['slug'] == slug:
            return dict(item)
    return None


def profile_apps_for_vertical(vertical_slug: str) -> list[dict]:
    return [
        dict(a) for a in PROFILE_APPS
        if a['vertical'] == vertical_slug
    ]


def profile_integrations_for_vertical(vertical_slug: str) -> list[dict]:
    preset = set(VERTICAL_PROFILE_PRESETS.get(vertical_slug, ()))
    return [
        dict(i) for i in PROFILE_INTEGRATIONS
        if i['slug'] in preset
    ]


def vertical_profile_preset(vertical_slug: str) -> tuple[str, ...]:
    if vertical_slug not in ('kobi', 'agency'):
        vertical_slug = 'kobi'
    return VERTICAL_PROFILE_PRESETS.get(vertical_slug, VERTICAL_PROFILE_PRESETS['kobi'])


def expand_profile_slugs_to_platform(slugs: list[str]) -> list[str]:
    """Profil uygulama slug'ları → backend modül + parçacık listesi."""
    out: list[str] = []
    for slug in slugs:
        if slug in out:
            continue
        item = profile_app_by_slug(slug)
        if item:
            out.append(slug)
            for m in item.get('platform_modules', ()):
                if m not in out:
                    out.append(m)
            for p in item.get('platform_particles', ()):
                if p not in out:
                    out.append(p)
            continue
        if slug.startswith('p.') or slug.startswith('integration_') or slug.startswith('agency_') or slug in (
            'contact', 'services', 'accounting', 'outreach', 'agency_suite', 'settings',
        ):
            if slug not in out:
                out.append(slug)
    return out


def collapse_platform_to_profile_slugs(raw: list[str], vertical: str) -> list[str]:
    """Eski backend modül listesini profil uygulamalarına çevirir."""
    known_profile = {a['slug'] for a in ALL_PROFILE_ITEMS}
    profile_in_raw = [s for s in raw if s in known_profile]
    if profile_in_raw:
        return profile_in_raw
    legacy_platform = {
        'contact', 'services', 'accounting', 'outreach',
        'agency_suite', 'agency_retainer', 'agency_clients', 'agency_freelancers',
        'agency_firms', 'agency_pipeline', 'agency_finance', 'agency_campaigns',
        'tools',
        'integration_whatsapp_bridge', 'integration_whatsapp_api', 'integration_media',
    }
    if any(s in raw for s in legacy_platform) or any(s.startswith('p.') for s in raw):
        return list(vertical_profile_preset(vertical))
    return list(vertical_profile_preset(vertical))
