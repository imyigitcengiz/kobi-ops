"""Ürün ↔ arıza tipi kataloğu ve doğrulama (servis formu, hızlı düzenleme)."""

from django.contrib.auth import get_user_model

from core_settings.models import (
    PriorityOption,
    ProductOption,
    ServiceTypeOption,
    StatusOption,
)
from services.models import ServiceRecord

User = get_user_model()


def build_options_catalog():
    products = ProductOption.objects.prefetch_related('service_types').order_by('name')
    service_types = ServiceTypeOption.objects.prefetch_related('products').order_by('name')

    def service_type_color(st):
        first_product = next(iter(st.products.all()), None)
        return first_product.color_hex if first_product else st.color_hex

    return {
        'products': [
            {
                'id': p.id,
                'name': p.name,
                'color': p.color_hex,
                'service_type_ids': list(p.service_types.values_list('id', flat=True)),
            }
            for p in products
        ],
        'service_types': [
            {
                'id': s.id,
                'name': s.name,
                'color': service_type_color(s),
                'product_ids': list(s.products.values_list('id', flat=True)),
            }
            for s in service_types
        ],
        'statuses': [
            {
                'id': s.id,
                'name': s.name,
                'color': s.color_hex,
                'is_paid': ServiceRecord.status_name_is_paid(s.name),
            }
            for s in StatusOption.objects.order_by('name')
        ],
        'priorities': [
            {'id': p.id, 'name': p.name, 'color': p.color_hex}
            for p in PriorityOption.objects.order_by('name')
        ],
    }


def resolve_allowed_service_type_ids(product_ids: list[int]) -> tuple[set[int] | None, str]:
    """
    product_ids için izinli arıza tipi id kümesi.
    None = tüm tipler (ürün yok veya eşleme tanımsız).
    """
    if not product_ids:
        return None, 'none'

    products = ProductOption.objects.filter(id__in=product_ids).prefetch_related('service_types')
    allowed = set()
    any_mapping = False
    for product in products:
        ids = list(product.service_types.values_list('id', flat=True))
        if not ids:
            return None, 'all_fallback'
        any_mapping = True
        allowed.update(ids)

    if not any_mapping:
        return None, 'all_fallback'
    return allowed, 'filtered'


def filter_service_type_ids(product_ids: list[int], service_type_ids: list[int]) -> list[int]:
    """Seçili ürünlere uymayan arıza tiplerini düşürür."""
    if not service_type_ids:
        return []
    allowed, mode = resolve_allowed_service_type_ids(product_ids)
    if allowed is None:
        return list(dict.fromkeys(service_type_ids))
    return [sid for sid in service_type_ids if sid in allowed]
