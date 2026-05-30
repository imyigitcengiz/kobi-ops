"""Modül kataloğu — Uygulama (app) / entegrasyon / yol haritası.

- **app**: Rehber, Muhasebe… — Modül Merkezi'nde aç/kapa, menü + URL
- **integration**: WhatsApp motoru (Tools) — diğer uygulamalar tüketir
- **roadmap**: Vitrinde listelenir, route yok

Yeni uygulama: MODULES'a kayıt + route_prefixes + izin.
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
    ('retail', 'Perakende & Bayi', 'Mağaza, bayi ağı, sipariş ve stok', 'store', 'amber'),
    ('healthcare', 'Sağlık & Randevu', 'Klinik, muayenehane, randevu', 'heart-pulse', 'rose'),
    ('nonprofit', 'STK & Dernek', 'Üye, bağış, gönüllü', 'hand-heart', 'sky'),
    ('universal', 'Evrensel', 'Ortak araçlar', 'layers', 'slate'),
)

# Sektör seçilince önerilen modül seti (Modül Merkezi → "Paketi uygula")
VERTICAL_PRESETS: dict[str, tuple[str, ...]] = {
    'kobi': ('contact', 'services', 'accounting', 'outreach', 'tools'),
    'agency': ('contact', 'outreach', 'accounting', 'tools', 'agency_suite'),
    'retail': ('contact', 'services', 'accounting', 'tools'),
    'healthcare': ('contact', 'services', 'outreach', 'tools'),
    'nonprofit': ('contact', 'outreach', 'tools'),
    'universal': ('contact', 'accounting', 'tools', 'settings'),
}

MODULES: tuple[dict, ...] = (
    {
        'slug': 'contact',
        'kind': MODULE_KIND_APP,
        'name': 'Rehber',
        'summary': 'Müşteri, firma ve paylaşılan kayıt merkezi.',
        'access_perm': 'access.contact',
        'hub_url_name': 'contact_hub',
        'icon': 'book-user',
        'verticals': ('kobi', 'agency', 'retail', 'nonprofit', 'universal'),
        'status': MODULE_STATUS_ACTIVE,
        'panel_section': 'contact',
        'route_prefixes': ('/contact/', '/crm/', '/ortak/'),
        'features': (
            'Müşteri kartları',
            'Firma rehberi & Maps',
            'Ekip tanımları',
            'Çözüm ortağı ağı',
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
        'features': (
            'Servis kayıtları',
            'Durum & öncelik',
            'Toplu işlem & yazdırma',
            'Servis WhatsApp bildirimi',
        ),
        'sort': 20,
        'default_enabled': True,
        'can_disable': True,
    },
    {
        'slug': 'accounting',
        'kind': MODULE_KIND_APP,
        'name': 'Muhasebe',
        'summary': 'Personel, maaş/avans, gelir-gider ve satış.',
        'access_perm': 'access.accounting',
        'hub_url_name': 'accounting_hub',
        'icon': 'calculator',
        'verticals': ('kobi', 'agency', 'retail', 'universal'),
        'status': MODULE_STATUS_ACTIVE,
        'panel_section': 'accounting',
        'route_prefixes': ('/muhasebe/', '/sales-lead/'),
        'features': (
            'Personel yönetimi',
            'Maaş & avans',
            'Gelir & gider',
            'Satış kayıtları & raporlar',
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
        'features': (
            'Kampanya listeleri',
            'Toplu mesaj',
            'Mesaj geçmişi',
        ),
        'sort': 40,
        'default_enabled': True,
        'can_disable': True,
    },
    {
        'slug': 'agency_suite',
        'kind': MODULE_KIND_APP,
        'name': 'Ajans Çalışma Alanı',
        'summary': 'Retainer projeler, müşteri pipeline ve ajans özeti — ajanslara özel.',
        'access_perm': None,
        'hub_url_name': 'agency_hub',
        'icon': 'palette',
        'verticals': ('agency',),
        'status': MODULE_STATUS_BETA,
        'panel_section': 'agency',
        'route_prefixes': ('/panel/ajans/',),
        'features': (
            'Retainer proje panosu',
            'Müşteri pipeline özeti',
            'Kampanya & satış kısayolları',
            'Aylık retainer takibi',
        ),
        'sort': 15,
        'default_enabled': False,
        'can_disable': True,
        'requires_any_perm': ('access.contact', 'access.outreach', 'access.accounting'),
    },
    {
        'slug': 'tools',
        'kind': MODULE_KIND_INTEGRATION,
        'name': 'Tools (entegrasyonlar)',
        'summary': 'WhatsApp köprüsü, medya ve AI — diğer uygulamaların altyapısı.',
        'access_perm': 'access.tools',
        'hub_url_name': 'tools_hub',
        'icon': 'plug',
        'verticals': ('universal', 'kobi', 'agency'),
        'status': MODULE_STATUS_ACTIVE,
        'panel_section': None,
        'route_prefixes': ('/tools/',),
        'features': (
            'WhatsApp QR / Business API',
            'Medya kütüphanesi',
            'AI ayarları',
        ),
        'sort': 50,
        'default_enabled': True,
        'can_disable': True,
    },
    {
        'slug': 'settings',
        'kind': MODULE_KIND_APP,
        'name': 'Site Ayarları',
        'summary': 'Katalog, durumlar ve firma bilgileri.',
        'access_perm': 'access.settings',
        'hub_url_name': 'settings_genel',
        'icon': 'sliders-horizontal',
        'verticals': ('universal',),
        'status': MODULE_STATUS_ACTIVE,
        'panel_section': None,
        'route_prefixes': ('/ayarlar/',),
        'features': ('Ürün & durum katalogları', 'Firma bilgileri', 'Modül merkezi'),
        'sort': 60,
        'default_enabled': True,
        'can_disable': False,
    },
    {
        'slug': 'projects',
        'kind': MODULE_KIND_ROADMAP,
        'name': 'Proje & Retainer (genişletilmiş)',
        'summary': 'Ajans Çalışma Alanı yerine tam proje modülü — ileride.',
        'access_perm': None,
        'hub_url_name': None,
        'icon': 'kanban',
        'verticals': ('agency',),
        'status': MODULE_STATUS_ROADMAP,
        'panel_section': None,
        'route_prefixes': (),
        'features': ('Sprint', 'Teslimat', 'Müşteri portalı'),
        'sort': 110,
        'default_enabled': False,
        'can_disable': False,
    },
    {
        'slug': 'timesheet',
        'kind': MODULE_KIND_ROADMAP,
        'name': 'Zaman & Faturalama',
        'summary': 'Ekip zaman kaydı ve faturalama.',
        'access_perm': None,
        'hub_url_name': None,
        'icon': 'clock',
        'verticals': ('agency', 'kobi'),
        'status': MODULE_STATUS_ROADMAP,
        'panel_section': None,
        'route_prefixes': (),
        'features': ('Zaman çizelgesi', 'Fatura'),
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


def module_by_slug(slug: str) -> dict | None:
    for mod in MODULES:
        if mod['slug'] == slug:
            return dict(mod)
    return None


def vertical_preset_modules(vertical_slug: str) -> tuple[str, ...]:
    return VERTICAL_PRESETS.get(vertical_slug, default_enabled_module_slugs())


def route_prefix_to_module_slug() -> list[tuple[str, str]]:
    """Uzun prefix önce — eşleştirme için sıralı liste."""
    pairs = []
    for mod in MODULES:
        if mod.get('route_prefixes'):
            for prefix in mod['route_prefixes']:
                pairs.append((prefix, mod['slug']))
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    return pairs
