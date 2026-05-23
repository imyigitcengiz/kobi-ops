from django import forms

from core_settings.catalog import filter_service_type_ids
from customers.models import Customer
from .models import ServiceRecord, ServiceImage
from core_settings.models import ServiceTypeOption, ProductOption, SolutionPartner, ServicePersonnel


class ServiceRecordForm(forms.ModelForm):
    class Meta:
        model = ServiceRecord
        fields = [
            'customer', 'solution_partner', 'status', 'priority', 'products',
            'service_types', 'notes', 'assigned_to', 'service_personnel',
            'warranty_status', 'list_price', 'discounted_price',
        ]
        widgets = {
            'customer': forms.Select(attrs={'class': 'w-full p-3 bg-slate-50 border-none rounded-xl focus:ring-2 focus:ring-brand-500'}),
            'solution_partner': forms.Select(attrs={'class': 'w-full p-3 bg-slate-50 border-none rounded-xl focus:ring-2 focus:ring-brand-500'}),
            'status': forms.Select(attrs={'class': 'w-full p-3 bg-slate-50 border-none rounded-xl focus:ring-2 focus:ring-brand-500'}),
            'priority': forms.Select(attrs={'class': 'w-full p-3 bg-slate-50 border-none rounded-xl focus:ring-2 focus:ring-brand-500'}),
            'products': forms.CheckboxSelectMultiple(attrs={'class': 'grid grid-cols-2 gap-4'}),
            'service_types': forms.CheckboxSelectMultiple(attrs={'class': 'grid grid-cols-2 gap-4'}),
            'notes': forms.Textarea(attrs={'class': 'w-full p-3 bg-slate-50 border-none rounded-xl focus:ring-2 focus:ring-brand-500', 'rows': 3}),
            'assigned_to': forms.Select(attrs={'class': 'w-full p-3 bg-slate-50 border-none rounded-xl focus:ring-2 focus:ring-brand-500'}),
            'service_personnel': forms.Select(attrs={'class': 'w-full p-3 bg-slate-50 border-none rounded-xl focus:ring-2 focus:ring-brand-500'}),
            'warranty_status': forms.Select(attrs={'class': 'w-full p-3 bg-slate-50 border-none rounded-xl focus:ring-2 focus:ring-brand-500'}),
            'list_price': forms.NumberInput(attrs={
                'class': 'w-full p-3 bg-slate-50 border-none rounded-xl focus:ring-2 focus:ring-brand-500',
                'step': '0.01',
                'min': '0',
                'placeholder': '0,00',
            }),
            'discounted_price': forms.NumberInput(attrs={
                'class': 'w-full p-3 bg-slate-50 border-none rounded-xl focus:ring-2 focus:ring-brand-500',
                'step': '0.01',
                'min': '0',
                'placeholder': '0,00',
            }),
        }

    def _resolve_customer(self):
        if self.instance and self.instance.pk and self.instance.customer_id:
            return self.instance.customer
        raw = self.data.get('customer') if self.is_bound else None
        if raw and str(raw).isdigit():
            return Customer.objects.filter(pk=int(raw)).first()
        initial = self.initial.get('customer')
        if initial and str(initial).isdigit():
            return Customer.objects.filter(pk=int(initial)).first()
        return None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['solution_partner'].queryset = SolutionPartner.objects.filter(is_active=True).order_by('name')
        self.fields['solution_partner'].empty_label = 'Çözüm ortağı seçin (opsiyonel)'
        self.fields['service_personnel'].queryset = ServicePersonnel.objects.filter(is_active=True).select_related('team').order_by('name')
        self.fields['service_personnel'].empty_label = 'Servis personeli seçin (opsiyonel)'
        self.fields['list_price'].label = 'Normal fiyat (₺)'
        self.fields['discounted_price'].label = 'İndirimli fiyat (₺)'

        customer = self._resolve_customer()
        if customer:
            self.fields['products'].queryset = customer.products.order_by('name')
        else:
            self.fields['products'].queryset = ProductOption.objects.none()

    def clean(self):
        cleaned = super().clean()
        customer = cleaned.get('customer') or self._resolve_customer()
        products = cleaned.get('products')
        service_types = cleaned.get('service_types')

        if customer and products is not None:
            allowed_ids = set(customer.products.values_list('id', flat=True))
            picked = list(products)
            invalid = [p for p in picked if p.pk not in allowed_ids]
            if invalid:
                names = ', '.join(p.name for p in invalid)
                self.add_error(
                    'products',
                    f'Seçilen ürünler müşteriye tanımlı değil: {names}. '
                    f'Ürün tanımı yalnızca müşteri düzenleme sayfasından yapılır.',
                )
            cleaned['products'] = picked

        if products is not None and service_types is not None:
            product_ids = [p.pk for p in products]
            st_ids = [st.pk for st in service_types]
            allowed = filter_service_type_ids(product_ids, st_ids)
            allowed_set = set(allowed)
            cleaned['service_types'] = [st for st in service_types if st.pk in allowed_set]
        return cleaned
