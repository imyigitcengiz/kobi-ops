from common import business_modes as bm
from common import module_labels as ml


def _resolve_business_mode(request):
    if getattr(request, 'user', None) and request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile is not None and profile.business_mode:
            return bm.normalize_mode(profile.business_mode)
    query_mode = request.GET.get('mode') if hasattr(request, 'GET') else None
    if query_mode:
        return bm.normalize_mode(query_mode)
    session_mode = request.session.get('business_mode') if hasattr(request, 'session') else None
    if session_mode:
        return bm.normalize_mode(session_mode)
    return bm.MODE_KOBI


def gy_branding(request):
    """Modül adları — şablonlarda {{ gy.rehber }}, moda göre {{ gy.app_profile_name }} vb."""
    mode = _resolve_business_mode(request)
    meta = bm.get_mode_meta(mode)
    return {
        'gy': bm.build_gy_labels(mode),
        'user_business_mode': mode,
        'app_profile': meta,
    }
