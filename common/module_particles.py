"""Modül parçacıkları — uygulama içi özellikler, sektöre göre ayrı aç/kapa.

Örnek: KOBİ → personel & saha ekipleri; Ajans → freelancer ağı, retainer (personel kapalı).
"""

from __future__ import annotations

PARTICLE_CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ('rehber', 'Rehber & ilişkiler', 'users'),
    ('operasyon', 'Operasyon & saha', 'wrench'),
    ('finans', 'Finans & ödeme', 'wallet'),
    ('ajans', 'Ajans & proje', 'palette'),
    ('iletisim', 'İletişim', 'messages-square'),
)

PARTICLES: tuple[dict, ...] = (
    {
        'slug': 'p.contact.customers',
        'name': 'Müşteri kartları',
        'summary': 'Müşteri kayıtları, ürünler ve sözleşme bilgileri.',
        'category': 'rehber',
        'parent_module': 'contact',
        'route_prefixes': (),
        'vertical_tags': ('kobi', 'agency', 'retail', 'nonprofit', 'healthcare'),
        'default_enabled': True,
        'sort': 10,
    },
    {
        'slug': 'p.contact.firms',
        'name': 'Firma rehberi & Maps',
        'summary': 'Firma kaydı, etiketler ve Google Maps araması.',
        'category': 'rehber',
        'parent_module': 'contact',
        'route_prefixes': ('/contact/firmalar/', '/contact/firma-kazi/'),
        'vertical_tags': ('kobi', 'agency', 'retail', 'nonprofit'),
        'default_enabled': True,
        'sort': 20,
    },
    {
        'slug': 'p.contact.teams',
        'name': 'Saha servis ekipleri',
        'summary': 'Montaj/servis ekipleri ve ürün yetkinlikleri — kurumsal saha ops.',
        'category': 'operasyon',
        'parent_module': 'contact',
        'route_prefixes': ('/contact/ekip/',),
        'vertical_tags': ('kobi', 'retail', 'healthcare'),
        'default_enabled': True,
        'sort': 30,
    },
    {
        'slug': 'p.contact.freelancers',
        'name': 'Freelancer & taşeron ağı',
        'summary': 'Çözüm ortağı / freelancer ağı — ajans proje kadrosu.',
        'category': 'ajans',
        'parent_module': 'contact',
        'route_prefixes': ('/contact/cozum-agi/',),
        'vertical_tags': ('agency',),
        'default_enabled': False,
        'sort': 35,
    },
    {
        'slug': 'p.accounting.personnel',
        'name': 'Personel & kadro',
        'summary': 'Sigortalı personel, ekip ataması — kurumsal İK.',
        'category': 'operasyon',
        'parent_module': 'accounting',
        'route_prefixes': ('/muhasebe/personel/', '/contact/personel/'),
        'vertical_tags': ('kobi', 'retail', 'healthcare'),
        'default_enabled': True,
        'sort': 40,
    },
    {
        'slug': 'p.accounting.payroll',
        'name': 'Maaş & avans',
        'summary': 'Aylık maaş döngüsü, avans mahsubu, brüt − avans = net.',
        'category': 'finans',
        'parent_module': 'accounting',
        'route_prefixes': ('/muhasebe/maas-avans/',),
        'vertical_tags': ('kobi', 'retail'),
        'default_enabled': True,
        'sort': 50,
    },
    {
        'slug': 'p.accounting.finance',
        'name': 'Gelir & gider',
        'summary': 'Kasa hareketleri ve dönem özeti.',
        'category': 'finans',
        'parent_module': 'accounting',
        'route_prefixes': ('/muhasebe/gelir-gider/',),
        'vertical_tags': ('kobi', 'agency', 'retail', 'nonprofit'),
        'default_enabled': True,
        'sort': 60,
    },
    {
        'slug': 'p.accounting.sales',
        'name': 'Satış kayıtları',
        'summary': 'Proje satışları, peşinat ve pipeline.',
        'category': 'finans',
        'parent_module': 'accounting',
        'route_prefixes': ('/muhasebe/satis/', '/sales-lead/'),
        'vertical_tags': ('kobi', 'agency', 'retail'),
        'default_enabled': True,
        'sort': 70,
    },
    {
        'slug': 'p.agency.retainer',
        'name': 'Retainer proje panosu',
        'summary': 'Aylık retainer ve proje durumu — ajans çalışma alanı.',
        'category': 'ajans',
        'parent_module': 'agency_retainer',
        'route_prefixes': ('/ajans/',),
        'vertical_tags': ('agency',),
        'default_enabled': False,
        'sort': 15,
    },
    {
        'slug': 'p.outreach.campaigns',
        'name': 'Kampanya & toplu mesaj',
        'summary': 'WhatsApp kampanyaları ve mesaj geçmişi.',
        'category': 'iletisim',
        'parent_module': 'outreach',
        'route_prefixes': (),
        'vertical_tags': ('kobi', 'agency', 'nonprofit'),
        'default_enabled': True,
        'sort': 80,
    },
)

# Sektör paketi: modül slug'ları + parçacık slug'ları
VERTICAL_CATALOG_PRESETS: dict[str, dict[str, tuple[str, ...]]] = {
    'kobi': {
        'modules': (
            'contact', 'services', 'accounting', 'outreach',
            'integration_whatsapp_bridge', 'integration_whatsapp_api', 'integration_media',
        ),
        'particles': (
            'p.contact.customers', 'p.contact.firms', 'p.contact.teams',
            'p.accounting.personnel', 'p.accounting.payroll',
            'p.accounting.finance', 'p.accounting.sales', 'p.outreach.campaigns',
        ),
    },
    'agency': {
        'modules': (
            'agency_retainer', 'agency_clients', 'agency_freelancers', 'agency_firms',
            'agency_pipeline', 'agency_finance', 'agency_campaigns',
            'integration_whatsapp_bridge', 'integration_whatsapp_api', 'integration_media',
        ),
        'particles': (
            'p.agency.retainer',
        ),
    },
    'retail': {
        'modules': (
            'contact', 'services', 'accounting',
            'integration_whatsapp_bridge', 'integration_media',
        ),
        'particles': (
            'p.contact.customers', 'p.contact.firms', 'p.contact.teams',
            'p.accounting.personnel', 'p.accounting.payroll',
            'p.accounting.finance', 'p.accounting.sales',
        ),
    },
    'healthcare': {
        'modules': (
            'contact', 'services', 'outreach',
            'integration_whatsapp_bridge', 'integration_media',
        ),
        'particles': (
            'p.contact.customers', 'p.contact.teams', 'p.outreach.campaigns',
        ),
    },
    'nonprofit': {
        'modules': (
            'contact', 'outreach',
            'integration_whatsapp_api', 'integration_media',
        ),
        'particles': (
            'p.contact.customers', 'p.contact.firms', 'p.outreach.campaigns',
        ),
    },
    'universal': {
        'modules': ('contact', 'accounting', 'settings', 'integration_media'),
        'particles': (
            'p.contact.customers', 'p.accounting.finance', 'p.accounting.sales',
        ),
    },
}

LEGACY_MODULE_ALIASES: dict[str, tuple[str, ...]] = {
    'tools': (
        'integration_whatsapp_bridge',
        'integration_whatsapp_api',
        'integration_media',
    ),
}


def particle_by_slug(slug: str) -> dict | None:
    for p in PARTICLES:
        if p['slug'] == slug:
            return dict(p)
    return None


def category_by_slug(slug: str) -> dict | None:
    for row in PARTICLE_CATEGORIES:
        if row[0] == slug:
            return {'slug': row[0], 'name': row[1], 'icon': row[2]}
    return None


def default_enabled_particle_slugs() -> list[str]:
    return [p['slug'] for p in PARTICLES if p.get('default_enabled')]


def vertical_preset_all_slugs(vertical_slug: str) -> tuple[str, ...]:
    from common.profile_apps import expand_profile_slugs_to_platform, vertical_profile_preset
    return tuple(expand_profile_slugs_to_platform(list(vertical_profile_preset(vertical_slug))))


def particle_route_prefixes() -> list[tuple[str, str]]:
    pairs = []
    for p in PARTICLES:
        for prefix in p.get('route_prefixes', ()):
            pairs.append((prefix, p['slug']))
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    return pairs
