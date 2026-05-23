"""Güvenli `next` yönlendirmesi (servis formu ↔ müşteri düzenleme)."""


def get_safe_return_url(request) -> str | None:
    raw = (request.GET.get('next') or request.POST.get('next') or '').strip()
    if not raw:
        return None
    if raw.startswith('/') and not raw.startswith('//'):
        return raw
    return None
