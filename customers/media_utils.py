from __future__ import annotations

from .models import Customer, CustomerMedia


def ingest_customer_media_uploads(
    request,
    *,
    customer: Customer,
    service=None,
    scope: str = CustomerMedia.SCOPE_CUSTOMER,
    field_names: tuple[str, ...] = ('customer_media', 'media_files', 'images'),
) -> list[CustomerMedia]:
    """Form POST veya API ile gelen dosyaları CustomerMedia olarak kaydeder."""
    created: list[CustomerMedia] = []
    seen_names: set[str] = set()

    for field in field_names:
        for uploaded in request.FILES.getlist(field):
            key = f'{field}:{uploaded.name}:{uploaded.size}'
            if key in seen_names:
                continue
            seen_names.add(key)
            media = CustomerMedia.objects.create(
                customer=customer,
                service=service if scope == CustomerMedia.SCOPE_SERVICE else None,
                scope=scope,
                file=uploaded,
                title=uploaded.name,
                uploaded_by=request.user if request.user.is_authenticated else None,
            )
            created.append(media)
    return created
