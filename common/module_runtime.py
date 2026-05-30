"""Kurulum modül çözümlemesi — aç/kapa, menü, URL kilidi."""

from __future__ import annotations

from django.urls import NoReverseMatch, reverse

from common.module_catalog import (
    DEFAULT_PRIMARY_VERTICAL,
    MODULE_GATE_EXEMPT_PREFIXES,
    MODULE_KIND_APP,
    MODULE_KIND_INTEGRATION,
    MODULE_KIND_ROADMAP,
    MODULE_STATUS_ACTIVE,
    MODULE_STATUS_BETA,
    MODULE_STATUS_ROADMAP,
    MODULES,
    VERTICALS,
    default_enabled_module_slugs,
    module_by_slug,
    route_prefix_to_module_slug,
    vertical_by_slug,
    vertical_preset_modules,
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
            return slug
    return DEFAULT_PRIMARY_VERTICAL


def get_enabled_module_slugs() -> list[str]:
    settings = _site_settings()
    if settings and settings.enabled_module_slugs:
        known = {m['slug'] for m in MODULES}
        cleaned = [s for s in settings.enabled_module_slugs if s in known]
        if cleaned:
            return cleaned
    return default_enabled_module_slugs()


def is_module_enabled(slug: str) -> bool:
    return slug in get_enabled_module_slugs()


def resolve_path_module_slug(path: str) -> str | None:
    if any(_path_matches(path, p) for p in MODULE_GATE_EXEMPT_PREFIXES):
        return None
    for prefix, slug in route_prefix_to_module_slug():
        if _path_matches(path, prefix):
            return slug
    return None


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


def module_available_for_nav(user, slug: str) -> bool:
    """Menüde göster: kurulu + kullanıcı yetkisi."""
    if not is_module_enabled(slug):
        return False
    mod = module_by_slug(slug)
    if not mod or mod['status'] not in (MODULE_STATUS_ACTIVE, MODULE_STATUS_BETA):
        return False
    return user_can_access_module(user, mod)


def build_modules_nav_flags(user) -> dict[str, bool]:
    slugs = {m['slug'] for m in MODULES}
    return {slug: module_available_for_nav(user, slug) for slug in slugs}


def _module_hub_url(module: dict) -> str | None:
    url_name = module.get('hub_url_name')
    if not url_name:
        return None
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return None


def _status_label(status: str) -> str:
    return {
        MODULE_STATUS_ACTIVE: 'Aktif',
        MODULE_STATUS_BETA: 'Beta',
        MODULE_STATUS_ROADMAP: 'Yakında',
    }.get(status, status)


def _kind_label(kind: str) -> str:
    return {
        MODULE_KIND_APP: 'Uygulama',
        MODULE_KIND_INTEGRATION: 'Entegrasyon',
        MODULE_KIND_ROADMAP: 'Yol haritası',
    }.get(kind, kind)


def build_module_record(user, module: dict, *, installed: bool) -> dict:
    record = dict(module)
    record['installed'] = installed
    record['status_label'] = _status_label(module['status'])
    record['kind_label'] = _kind_label(module.get('kind', MODULE_KIND_APP))
    record['hub_url'] = (
        _module_hub_url(module)
        if installed and module['status'] in (MODULE_STATUS_ACTIVE, MODULE_STATUS_BETA)
        else None
    )
    record['user_has_access'] = user_can_access_module(user, module) if installed else False
    record['can_open'] = bool(record['hub_url'] and record['user_has_access'])
    record['can_toggle'] = (
        module['status'] in (MODULE_STATUS_ACTIVE, MODULE_STATUS_BETA)
        and module.get('can_disable', True)
    )
    return record


def build_module_hub_context(user, *, vertical_filter: str | None = None, query: str = '') -> dict:
    enabled = set(get_enabled_module_slugs())
    primary = get_primary_vertical_slug()
    vf = None
    if vertical_filter and vertical_filter != 'all':
        vf = vertical_filter if vertical_by_slug(vertical_filter) else None

    q = (query or '').strip().lower()
    modules = []
    for mod in MODULES:
        if vf and vf not in mod.get('verticals', ()):
            continue
        if q:
            hay = ' '.join([
                mod['name'].lower(),
                mod['summary'].lower(),
                ' '.join(mod.get('features', ())).lower(),
            ])
            if q not in hay:
                continue
        installed = mod['slug'] in enabled and mod['status'] in (MODULE_STATUS_ACTIVE, MODULE_STATUS_BETA)
        modules.append(build_module_record(user, mod, installed=installed))

    modules.sort(key=lambda m: (m['kind'] == MODULE_KIND_INTEGRATION, m['status'] != MODULE_STATUS_ACTIVE, m['sort'], m['name']))

    verticals = [{'slug': 'all', 'name': 'Tüm sektörler', 'tagline': '', 'icon': 'layout-grid', 'color': 'slate'}]
    verticals.extend(v for v in (vertical_by_slug(row[0]) for row in VERTICALS) if v)

    apps = [m for m in modules if m.get('kind') == MODULE_KIND_APP and m['status'] != MODULE_STATUS_ROADMAP]
    integrations = [m for m in modules if m.get('kind') == MODULE_KIND_INTEGRATION]
    roadmap = [m for m in modules if m['status'] == MODULE_STATUS_ROADMAP]

    return {
        'module_verticals': verticals,
        'module_vertical_filter': vertical_filter or 'all',
        'module_primary_vertical': primary,
        'module_catalog_items': modules,
        'module_catalog_apps': apps,
        'module_catalog_integrations': integrations,
        'module_catalog_roadmap': roadmap,
        'module_installed_count': sum(1 for m in apps if m['installed']),
        'module_roadmap_count': len(roadmap),
        'module_search_query': query,
        'vertical_preset_slugs': vertical_preset_modules(primary),
    }


def panel_section_visible(section_key: str) -> bool:
    mapping = {
        'contact': 'contact',
        'services': 'services',
        'accounting': 'accounting',
        'outreach': 'outreach',
        'agency': 'agency_suite',
    }
    slug = mapping.get(section_key)
    if not slug:
        return True
    return is_module_enabled(slug)


def recommended_modules_for_vertical(vertical_slug: str) -> list[dict]:
    preset = vertical_preset_modules(vertical_slug)
    return [dict(m) for m in MODULES if m['slug'] in preset and m['status'] in (MODULE_STATUS_ACTIVE, MODULE_STATUS_BETA)]


def apply_vertical_preset(vertical_slug: str) -> list[str]:
    """SiteSettings.enabled_module_slugs günceller; uygulanan slug listesini döner."""
    preset = list(vertical_preset_modules(vertical_slug))
    settings = _site_settings()
    if not settings:
        from core_settings.models import SiteSettings
        settings = SiteSettings.objects.create()
    settings.primary_vertical_slug = vertical_slug
    settings.enabled_module_slugs = preset
    settings.save(update_fields=['primary_vertical_slug', 'enabled_module_slugs'])
    return preset
