"""Modül kataloğu — Uygulama / entegrasyon / yol haritası.

Parçacıklar (personel, freelancer, maaş…) → common.module_particles
"""

from __future__ import annotations

MODULE_KIND_APP = 'app'
MODULE_KIND_INTEGRATION = 'integration'
MODULE_KIND_ROADMAP = 'roadmap'

MODULE_STATUS_ACTIVE = 'active'
MODULE_STATUS_BETA = 'beta'
MODULE_STATUS_ROADMAP = 'roadmap'

VERTICALS: tuple[tuple[str, str, str, str, str], ...] = (
    ('kobi', 'KOBİ & Saha Servis', 'Montaj, teknik servis, B2B satış, saha ekibi', 'wrench', 'emerald'),
    ('agency', 'Ajans & Proje', 'Dijital ajans, yazılım evi, danışmanlık, retainer', 'palette', 'violet'),
    ('universal', 'Evrensel', 'Ortak araçlar', 'layers', 'slate'),
)

# Kurulumda seçilebilir profiller — yalnızca KOBİ ve Ajans
INSTALLATION_VERTICAL_SLUGS: tuple[str, ...] = ('kobi', 'agency')

MODULES: tuple[dict, ...] = (
    {
        'slug': 'contact',
        'kind': MODULE_KIND_APP,
        'name': 'Rehber',
        'summary': 'Müşteri, firma ve ilişki merkezi — parçacıklarla özelleştirilir.',
        'access_perm': 'access.contact',
        'hub_url_name': 'contact_hub',
        'icon': 'book-user',
        'verticals': ('kobi', 'agency', 'retail', 'nonprofit', 'universal', 'healthcare'),
        'status': MODULE_STATUS_ACTIVE,
        'panel_section': 'contact',
        'route_prefixes': ('/contact/', '/crm/', '/ortak/'),
        'particle_slugs': (
            'p.contact.customers', 'p.contact.firms', 'p.contact.teams', 'p.contact.freelancers',
        ),
        'sort': 10,
        'default_enabled': True,
        'can_disable': True,
    },
    {
        'slug': 'services',
        'kind': MODULE_KIND_APP,
        'name': 'Yardım Masası',
        'summary': 'Servis / iş emri, saha ve durum takibi.',
        'access_perm': 'access.services',
        'hub_url_name': 'dashboard',
        'icon': 'headphones',
        'verticals': ('kobi', 'retail', 'healthcare', 'universal'),
        'status': MODULE_STATUS_ACTIVE,
        'panel_section': 'services',
        'route_prefixes': ('/services-dashboard/',),
        'particle_slugs': (),
        'sort': 20,
        'default_enabled': True,
        'can_disable': True,
    },
    {
        'slug': 'accounting',
        'kind': MODULE_KIND_APP,
        'name': 'Muhasebe',
        'summary': 'Finans ve ödeme — personel/maaş veya satış odaklı parçacıklarla.',
        'access_perm': 'access.accounting',
        'hub_url_name': 'accounting_hub',
        'icon': 'calculator',
        'verticals': ('kobi', 'agency', 'retail', 'universal'),
        'status': MODULE_STATUS_ACTIVE,
        'panel_section': 'accounting',
        'route_prefixes': ('/muhasebe/', '/sales-lead/'),
        'particle_slugs': (
            'p.accounting.personnel', 'p.accounting.payroll',
            'p.accounting.finance', 'p.accounting.sales',
        ),
        'sort': 30,
        'default_enabled': True,
        'can_disable': True,
    },
    {
        'slug': 'outreach',
        'kind': MODULE_KIND_APP,
        'name': 'İletişim Merkezi',
        'summary': 'Kampanya ve toplu WhatsApp gönderimi.',
        'access_perm': 'access.outreach',
        'hub_url_name': 'outreach_hub',
        'icon': 'messages-square',
        'verticals': ('kobi', 'agency', 'nonprofit', 'universal'),
        'status': MODULE_STATUS_ACTIVE,
        'panel_section': 'outreach',
        'route_prefixes': ('/iletisim/', '/contact/pazarlama/'),
        'particle_slugs': ('p.outreach.campaigns',),
        'sort': 40,
        'default_enabled': True,
        'can_disable': True,
    },
    {
        'slug': 'agency_suite',
        'kind': MODULE_KIND_APP,
        'name': 'Ajans Çalışma Alanı',
        'summary': 'Retainer projeler ve pipeline — ajans paketi.',
        'access_perm': None,
        'hub_url_name': 'agency_hub',
        'icon': 'palette',
        'verticals': ('agency',),
        'status': MODULE_STATUS_BETA,
        'panel_section': 'agency',
        'route_prefixes': (),
        'particle_slugs': ('p.agency.retainer',),
        'sort': 15,
        'default_enabled': False,
        'can_disable': True,
        'requires_any_perm': ('access.contact', 'access.outreach', 'access.accounting'),
    },
    {
        'slug': 'integration_whatsapp_bridge',
        'kind': MODULE_KIND_INTEGRATION,
        'name': 'WhatsApp Köprüsü (QR)',
        'summary': 'QR bağlantı, hat yönetimi, senaryolar ve servis bildirimleri.',
        'access_perm': 'tools.whatsapp',
        'hub_url_name': 'tools_whatsapp_baglan',
        'icon': 'message-circle',
        'verticals': ('kobi', 'agency', 'retail', 'healthcare', 'universal'),
        'status': MODULE_STATUS_ACTIVE,
        'panel_section': None,
        'route_prefixes': ('/tools/whatsapp-baglan/', '/tools/whatsapp/'),
        'particle_slugs': (),
        'sort': 51,
        'default_enabled': True,
        'can_disable': True,
    },
    {
        'slug': 'integration_whatsapp_api',
        'kind': MODULE_KIND_INTEGRATION,
        'name': 'WhatsApp Business API',
        'summary': 'Meta Cloud API token, telefon ID — kampanya ve toplu gönderim.',
        'access_perm': 'tools.whatsapp',
        'hub_url_name': 'tools_whatsapp_api_settings',
        'icon': 'cloud',
        'verticals': ('kobi', 'agency', 'nonprofit', 'universal'),
        'status': MODULE_STATUS_ACTIVE,
        'panel_section': None,
        'route_prefixes': ('/tools/whatsapp-api/',),
        'particle_slugs': (),
        'sort': 52,
        'default_enabled': True,
        'can_disable': True,
    },
    {
        'slug': 'integration_media',
        'kind': MODULE_KIND_INTEGRATION,
        'name': 'Medya Kütüphanesi',
        'summary': 'Dosya ve fotoğraf arşivi — müşteri ve kampanya medyası.',
        'access_perm': 'tools.media',
        'hub_url_name': 'tools_media_library',
        'icon': 'images',
        'verticals': ('kobi', 'agency', 'retail', 'nonprofit', 'universal', 'healthcare'),
        'status': MODULE_STATUS_ACTIVE,
        'panel_section': None,
        'route_prefixes': ('/tools/medya/',),
        'particle_slugs': (),
        'sort': 53,
        'default_enabled': True,
        'can_disable': True,
    },
    {
        'slug': 'settings',
        'kind': MODULE_KIND_APP,
        'name': 'Site Ayarları',
        'summary': 'Katalog, durumlar, AI ve firma bilgileri.',
        'access_perm': 'access.settings',
        'hub_url_name': 'settings_genel',
        'icon': 'sliders-horizontal',
        'verticals': ('universal',),
        'status': MODULE_STATUS_ACTIVE,
        'panel_section': None,
        'route_prefixes': ('/ayarlar/',),
        'particle_slugs': (),
        'sort': 60,
        'default_enabled': True,
        'can_disable': False,
    },
    {
        'slug': 'projects',
        'kind': MODULE_KIND_ROADMAP,
        'name': 'Proje & Sprint (genişletilmiş)',
        'summary': 'Tam proje modülü — ileride.',
        'access_perm': None,
        'hub_url_name': None,
        'icon': 'kanban',
        'verticals': ('agency',),
        'status': MODULE_STATUS_ROADMAP,
        'panel_section': None,
        'route_prefixes': (),
        'particle_slugs': (),
        'sort': 110,
        'default_enabled': False,
        'can_disable': False,
    },
    {
        'slug': 'timesheet',
        'kind': MODULE_KIND_ROADMAP,
        'name': 'Zaman & Faturalama',
        'summary': 'Freelancer zaman kaydı ve faturalama.',
        'access_perm': None,
        'hub_url_name': None,
        'icon': 'clock',
        'verticals': ('agency', 'kobi'),
        'status': MODULE_STATUS_ROADMAP,
        'panel_section': None,
        'route_prefixes': (),
        'particle_slugs': (),
        'sort': 120,
        'default_enabled': False,
        'can_disable': False,
    },
)

DEFAULT_PRIMARY_VERTICAL = 'kobi'

MODULE_GATE_EXEMPT_PREFIXES = (
    '/panel/',
    '/panel/moduller/',
    '/profil/',
    '/giris/',
    '/healthz/',
    '/static/',
    '/media/',
    '/chat/',
    '/yonetim/',
    '/tools/',  # hub — entegrasyon kartlarından yönlendirme
)


def default_enabled_module_slugs() -> list[str]:
    return [m['slug'] for m in MODULES if m.get('default_enabled')]


def vertical_by_slug(slug: str) -> dict | None:
    for row in VERTICALS:
        if row[0] == slug:
            return {
                'slug': row[0],
                'name': row[1],
                'tagline': row[2],
                'icon': row[3],
                'color': row[4],
            }
    return None


def all_verticals() -> list[dict]:
    return [vertical_by_slug(row[0]) for row in VERTICALS]


def installation_verticals() -> list[dict]:
    """Kurulum profili seçimi — KOBİ ve Ajans."""
    return [v for v in all_verticals() if v and v['slug'] in INSTALLATION_VERTICAL_SLUGS]


def is_installation_vertical(slug: str) -> bool:
    return slug in INSTALLATION_VERTICAL_SLUGS


def normalize_installation_vertical(slug: str) -> str:
    return slug if is_installation_vertical(slug) else DEFAULT_PRIMARY_VERTICAL


def module_by_slug(slug: str) -> dict | None:
    for mod in MODULES:
        if mod['slug'] == slug:
            return dict(mod)
    return None


def route_prefix_to_module_slug() -> list[tuple[str, str]]:
    pairs = []
    for mod in MODULES:
        if mod.get('route_prefixes'):
            for prefix in mod['route_prefixes']:
                pairs.append((prefix, mod['slug']))
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    return pairs
