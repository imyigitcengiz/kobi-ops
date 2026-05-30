"""Kurulum profili uygulamaları + backend platform çözümlemesi."""

from __future__ import annotations

from django.urls import NoReverseMatch, reverse

from common.module_catalog import (
    DEFAULT_PRIMARY_VERTICAL,
    MODULE_GATE_EXEMPT_PREFIXES,
    MODULE_STATUS_ACTIVE,
    MODULE_STATUS_BETA,
    MODULE_STATUS_ROADMAP,
    MODULES,
    installation_verticals,
    module_by_slug,
    normalize_installation_vertical,
    route_prefix_to_module_slug,
    vertical_by_slug,
)
from common.module_particles import (
    LEGACY_MODULE_ALIASES,
    particle_by_slug,
    particle_route_prefixes,
)
from common.profile_apps import (
    ALL_PROFILE_ITEMS,
    APP_CATEGORY_LABELS,
    LEGACY_TO_PROFILE,
    collapse_platform_to_profile_slugs,
    expand_profile_slugs_to_platform,
    profile_app_by_slug,
    profile_apps_for_vertical,
    profile_integrations_for_vertical,
    vertical_profile_preset,
)


def _path_matches(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix)


def _site_settings():
    from core_settings.models import SiteSettings
    return SiteSettings.objects.first()


def get_primary_vertical_slug() -> str:
    settings = _site_settings()
    if settings and settings.primary_vertical_slug:
        slug = settings.primary_vertical_slug.strip()
        if vertical_by_slug(slug):
            return normalize_installation_vertical(slug)
    return DEFAULT_PRIMARY_VERTICAL


def _normalize_stored_slugs(raw: list | tuple | None) -> list[str]:
    vertical = get_primary_vertical_slug()
    if not raw:
        return list(vertical_profile_preset(vertical))

    known_profile = {i['slug'] for i in ALL_PROFILE_ITEMS}
    out: list[str] = []

    for slug in raw:
        if slug in LEGACY_MODULE_ALIASES:
            for alias in LEGACY_MODULE_ALIASES[slug]:
                mapped = LEGACY_TO_PROFILE.get(alias)
                if mapped and mapped not in out:
                    out.append(mapped)
            continue
        if slug in LEGACY_TO_PROFILE and slug not in known_profile:
            mapped = LEGACY_TO_PROFILE[slug]
            if mapped not in out:
                out.append(mapped)
            continue
        if slug in known_profile and slug not in out:
            out.append(slug)

    if not out or not any(s.startswith('app.') or s.startswith('int.') for s in out):
        out = collapse_platform_to_profile_slugs(list(raw), vertical)

    preset = vertical_profile_preset(vertical)
    return out or list(preset)


def get_enabled_profile_slugs() -> list[str]:
    settings = _site_settings()
    if settings and settings.enabled_module_slugs:
        return _normalize_stored_slugs(settings.enabled_module_slugs)
    return _normalize_stored_slugs(None)


def get_enabled_catalog_slugs() -> list[str]:
    return expand_profile_slugs_to_platform(get_enabled_profile_slugs())


def get_enabled_module_slugs() -> list[str]:
    known = {m['slug'] for m in MODULES}
    return [s for s in get_enabled_catalog_slugs() if s in known]


def get_enabled_particle_slugs() -> list[str]:
    return [s for s in get_enabled_catalog_slugs() if s.startswith('p.')]


def is_profile_app_enabled(slug: str) -> bool:
    return slug in get_enabled_profile_slugs()


def is_module_enabled(slug: str) -> bool:
    if slug in LEGACY_MODULE_ALIASES:
        return all(is_module_enabled(s) for s in LEGACY_MODULE_ALIASES[slug])
    return slug in get_enabled_module_slugs()


def is_particle_enabled(slug: str) -> bool:
    return slug in get_enabled_particle_slugs()


def is_particle_enabled_for_nav(slug: str) -> bool:
    p = particle_by_slug(slug)
    if not p or not is_particle_enabled(slug):
        return False
    parent = p.get('parent_module')
    if parent and not is_module_enabled(parent):
        return False
    return True


def resolve_path_module_slug(path: str) -> str | None:
    if any(_path_matches(path, p) for p in MODULE_GATE_EXEMPT_PREFIXES):
        return None
    for prefix, slug in route_prefix_to_module_slug():
        if _path_matches(path, prefix):
            return slug
    return None


def resolve_path_particle_slug(path: str) -> str | None:
    for prefix, slug in particle_route_prefixes():
        if _path_matches(path, prefix):
            return slug
    return None


def user_can_access_profile_app(user, app: dict) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    required_any = app.get('requires_any_perm')
    if required_any:
        return user.has_any_perm_codename(*required_any)
    perm = app.get('access_perm')
    if not perm:
        return False
    return user.has_perm_codename(perm)


def user_can_access_module(user, module: dict) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    required_any = module.get('requires_any_perm')
    if required_any:
        return user.has_any_perm_codename(*required_any)
    perm = module.get('access_perm')
    if not perm:
        return False
    return user.has_perm_codename(perm)


def profile_app_available_for_nav(user, slug: str) -> bool:
    if not is_profile_app_enabled(slug):
        return False
    app = profile_app_by_slug(slug)
    if not app:
        return False
    if app.get('vertical') and app['vertical'] != get_primary_vertical_slug():
        return False
    return user_can_access_profile_app(user, app)


def module_available_for_nav(user, slug: str) -> bool:
    if not is_module_enabled(slug):
        return False
    mod = module_by_slug(slug)
    if not mod or mod['status'] not in (MODULE_STATUS_ACTIVE, MODULE_STATUS_BETA):
        return False
    return user_can_access_module(user, mod)


def build_modules_nav_flags(user) -> dict[str, bool]:
    flags = {m['slug']: module_available_for_nav(user, m['slug']) for m in MODULES}
    for item in ALL_PROFILE_ITEMS:
        for mod_slug in item.get('platform_modules', ()):
            int_key = mod_slug
            flags[int_key] = module_available_for_nav(user, mod_slug)
    return flags


def build_particles_nav_short(user) -> dict[str, bool]:
    mapping = {
        'p.contact.customers': 'contact_customers',
        'p.contact.firms': 'contact_firms',
        'p.contact.teams': 'contact_teams',
        'p.contact.freelancers': 'contact_freelancers',
        'p.accounting.personnel': 'accounting_personnel',
        'p.accounting.payroll': 'accounting_payroll',
        'p.accounting.finance': 'accounting_finance',
        'p.accounting.sales': 'accounting_sales',
        'p.agency.retainer': 'agency_retainer',
        'p.outreach.campaigns': 'outreach_campaigns',
    }
    return {
        short: is_particle_enabled_for_nav(full)
        for full, short in mapping.items()
    }


def _hub_url(url_name: str | None) -> str | None:
    if not url_name:
        return None
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return None


def profile_app_mini_hub_url(slug: str) -> str | None:
    try:
        return reverse('profile_app_hub', kwargs={'app_slug': slug})
    except NoReverseMatch:
        return None


_PLATFORM_MODULE_PATH_PREFIXES: dict[str, tuple[str, ...]] = {
    'services': ('/services-dashboard/',),
    'contact': ('/contact/', '/crm/', '/ortak/'),
    'accounting': ('/muhasebe/', '/sales-lead/'),
    'outreach': ('/iletisim/',),
    'agency_suite': ('/ajans/', '/panel/ajans/'),
    'agency_retainer': ('/ajans/',),
    'agency_clients': ('/ajans/musteriler/',),
    'agency_freelancers': ('/ajans/freelancer/',),
    'agency_firms': ('/ajans/firmalar/',),
    'agency_pipeline': ('/ajans/pipeline/',),
    'agency_finance': ('/ajans/finans/',),
    'agency_campaigns': ('/ajans/kampanya/',),
    'integration_whatsapp_bridge': ('/tools/whatsapp',),
    'integration_whatsapp_api': ('/tools/whatsapp',),
    'integration_media': ('/tools/media',),
}


def _app_is_active(app: dict, path: str, url_name: str | None, app_slug_kw: str | None) -> bool:
    if app_slug_kw and app['slug'] == app_slug_kw:
        return True
    if url_name and url_name == app.get('hub_url_name'):
        return True
    for mod in app.get('platform_modules', ()):
        for prefix in _PLATFORM_MODULE_PATH_PREFIXES.get(mod, ()):
            if path.startswith(prefix):
                return True
    return False


def build_profile_sidebar(user, request) -> dict:
    """Sol menü — yalnızca aktif profile ait uygulamalar."""
    vertical = get_primary_vertical_slug()
    path = getattr(request, 'path', '') or ''
    match = getattr(request, 'resolver_match', None)
    url_name = match.url_name if match else None
    app_slug_kw = match.kwargs.get('app_slug') if match and match.kwargs else None

    groups: dict[str, dict] = {}
    for app in profile_apps_for_vertical(vertical):
        if not profile_app_available_for_nav(user, app['slug']):
            continue
        cat = app.get('category', 'operasyon')
        cat_label = APP_CATEGORY_LABELS.get(cat, (cat, 'puzzle'))
        mini = profile_app_mini_hub_url(app['slug'])
        hub = _hub_url(app.get('hub_url_name'))
        groups.setdefault(cat, {
            'slug': cat,
            'name': cat_label[0],
            'icon': cat_label[1],
            'items': [],
        })
        groups[cat]['items'].append({
            'slug': app['slug'],
            'name': app['name'],
            'icon': app.get('icon', 'puzzle'),
            'url': mini or hub,
            'platform_modules': tuple(app.get('platform_modules', ())),
            'active': _app_is_active(app, path, url_name, app_slug_kw),
        })

    integrations = []
    for item in profile_integrations_for_vertical(vertical):
        if not profile_app_available_for_nav(user, item['slug']):
            continue
        mini = profile_app_mini_hub_url(item['slug'])
        hub = _hub_url(item.get('hub_url_name'))
        integrations.append({
            'slug': item['slug'],
            'name': item['name'],
            'icon': item.get('icon', 'plug'),
            'url': mini or hub,
            'platform_modules': tuple(item.get('platform_modules', ())),
            'active': _app_is_active(item, path, url_name, app_slug_kw),
        })

    ordered_groups = []
    for cat_slug, (cat_name, cat_icon) in APP_CATEGORY_LABELS.items():
        if cat_slug == 'entegrasyon':
            continue
        g = groups.get(cat_slug)
        if g and g['items']:
            g['items'].sort(key=lambda i: i['name'])
            ordered_groups.append(g)

    return {
        'groups': ordered_groups,
        'integrations': integrations,
    }


def build_profile_app_record(user, app: dict) -> dict:
    slug = app['slug']
    installed = is_profile_app_enabled(slug)
    cat = APP_CATEGORY_LABELS.get(app.get('category', ''), ('', 'puzzle'))
    record = dict(app)
    record['installed'] = installed
    record['category_name'] = cat[0]
    record['category_icon'] = cat[1]
    record['hub_url'] = _hub_url(app.get('hub_url_name')) if installed else None
    record['mini_hub_url'] = profile_app_mini_hub_url(slug) if installed else None
    record['open_url'] = record['mini_hub_url'] or record['hub_url']
    record['user_has_access'] = user_can_access_profile_app(user, app) if installed else False
    record['can_open'] = bool(record['open_url'] and record['user_has_access'])
    record['can_toggle'] = True
    return record


def build_profile_hub_context(user, *, query: str = '') -> dict:
    vertical = get_primary_vertical_slug()
    vinfo = vertical_by_slug(vertical)
    q = (query or '').strip().lower()

    apps = []
    for app in profile_apps_for_vertical(vertical):
        if q and q not in f"{app['name']} {app['summary']}".lower():
            continue
        apps.append(build_profile_app_record(user, app))

    integrations = []
    for item in profile_integrations_for_vertical(vertical):
        if q and q not in f"{item['name']} {item['summary']}".lower():
            continue
        integrations.append(build_profile_app_record(user, item))

    apps.sort(key=lambda a: (a.get('sort', 99), a['name']))
    integrations.sort(key=lambda a: a.get('sort', 99))

    groups: dict[str, list] = {}
    for a in apps:
        groups.setdefault(a['category'], []).append(a)

    profile_app_groups = []
    for cat_slug, (cat_name, cat_icon) in APP_CATEGORY_LABELS.items():
        if cat_slug == 'entegrasyon':
            continue
        items = groups.get(cat_slug, [])
        if items:
            profile_app_groups.append({
                'slug': cat_slug,
                'name': cat_name,
                'icon': cat_icon,
                'items': items,
            })

    roadmap = [
        dict(m) for m in MODULES
        if m['status'] == MODULE_STATUS_ROADMAP
        and vertical in m.get('verticals', ())
    ]

    enabled_profile = get_enabled_profile_slugs()
    return {
        'module_primary_vertical': vertical,
        'panel_vertical': vinfo,
        'module_verticals': installation_verticals(),
        'profile_app_groups': profile_app_groups,
        'profile_integrations': integrations,
        'profile_apps_flat': apps + integrations,
        'module_catalog_roadmap': roadmap,
        'module_installed_count': sum(1 for a in apps + integrations if a['installed']),
        'module_roadmap_count': len(roadmap),
        'module_search_query': query,
        'vertical_preset_slugs': vertical_profile_preset(vertical),
        'enabled_profile_slugs': enabled_profile,
    }


def build_profile_panel_apps(user) -> list[dict]:
    """Ana panel — yalnızca kurulum profili uygulamaları."""
    vertical = get_primary_vertical_slug()
    items = profile_apps_for_vertical(vertical) + profile_integrations_for_vertical(vertical)
    records = []
    for app in items:
        rec = build_profile_app_record(user, app)
        if rec['installed'] and rec['can_open']:
            records.append(rec)
    records.sort(key=lambda a: (a.get('sort', 99), a['name']))
    return records


def panel_section_visible(section_key: str) -> bool:
    """Geriye dönük — profil uygulaması eşlemesi."""
    vertical = get_primary_vertical_slug()
    mapping = {
        'contact': {
            'kobi': 'app.kobi.customers',
            'agency': 'app.agency.clients',
        },
        'services': {
            'kobi': 'app.kobi.service_desk',
        },
        'accounting': {
            'kobi': 'app.kobi.finance',
            'agency': 'app.agency.finance',
        },
        'outreach': {
            'kobi': 'app.kobi.campaigns',
            'agency': 'app.agency.campaigns',
        },
        'agency': {
            'agency': 'app.agency.retainer_studio',
        },
    }
    app_slug = mapping.get(section_key, {}).get(vertical)
    if not app_slug:
        return False
    return is_profile_app_enabled(app_slug)


def apply_vertical_preset(vertical_slug: str) -> list[str]:
    vertical_slug = normalize_installation_vertical(vertical_slug)
    slugs = list(vertical_profile_preset(vertical_slug))
    settings = _site_settings()
    if not settings:
        from core_settings.models import SiteSettings
        settings = SiteSettings.objects.create()
    settings.primary_vertical_slug = vertical_slug
    settings.enabled_module_slugs = slugs
    settings.save(update_fields=['primary_vertical_slug', 'enabled_module_slugs'])
    return slugs


def is_profile_setup_complete() -> bool:
    settings = _site_settings()
    if not settings:
        return False
    return bool(settings.profile_setup_completed_at)


def mark_profile_setup_complete() -> None:
    settings = _site_settings()
    if not settings:
        from core_settings.models import SiteSettings
        settings = SiteSettings.objects.create()
    from django.utils import timezone
    settings.profile_setup_completed_at = timezone.now()
    settings.save(update_fields=['profile_setup_completed_at'])


def user_can_manage_profile_setup(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.has_perm_codename('access.settings')


def vertical_preset_modules(vertical_slug: str) -> tuple[str, ...]:
    return vertical_profile_preset(vertical_slug)


# Geriye dönük isimler
def build_module_hub_context(user, *, vertical_filter: str | None = None, query: str = '') -> dict:
    return build_profile_hub_context(user, query=query)


def recommended_modules_for_vertical(vertical_slug: str) -> list[dict]:
    return profile_apps_for_vertical(vertical_slug)


def recommended_particles_for_vertical(vertical_slug: str) -> list[dict]:
    return []
