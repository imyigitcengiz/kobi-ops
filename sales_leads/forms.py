from decimal import Decimal, InvalidOperation

from django import forms

from core_settings.models import ProductColorOption, ProductOption
from customers.models import Customer
from users.models import User

from .models import SalesLead, SalesLeadInterimPayment, SalesLeadProductLine

INPUT = 'w-full p-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-amber-500 outline-none text-sm'
MONEY = INPUT + ' text-right'


def _parse_decimal(value):
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return None


def _post_list(data, key):
    if hasattr(data, 'getlist'):
        return data.getlist(key)
    value = data.get(key)
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


class SalesLeadForm(forms.Form):
    use_existing_customer = forms.BooleanField(
        required=False,
        initial=False,
        label='Mevcut müşteriye yeni proje ekle',
        widget=forms.CheckboxInput(attrs={'class': 'w-4 h-4 accent-amber-600 rounded'}),
    )
    existing_customer = forms.ModelChoiceField(
        queryset=Customer.objects.order_by('name'),
        required=False,
        label='Mevcut müşteri',
        widget=forms.Select(attrs={'class': INPUT}),
    )

    name = forms.CharField(required=False, label='Ad Soyad', widget=forms.TextInput(attrs={'class': INPUT}))
    phone = forms.CharField(required=False, label='Telefon', widget=forms.TextInput(attrs={'class': INPUT}))
    region = forms.CharField(required=False, label='Yer', widget=forms.TextInput(attrs={'class': INPUT}))
    address = forms.CharField(required=False, label='Adres', widget=forms.Textarea(attrs={'class': INPUT, 'rows': 2}))
    location_link = forms.URLField(
        required=False,
        label='Konum Linki',
        widget=forms.URLInput(attrs={'class': INPUT, 'placeholder': 'Google Maps konum linki'}),
    )
    contract_date = forms.DateField(
        required=False,
        label='Sözleşme Tarihi',
        widget=forms.DateInput(attrs={'type': 'date', 'class': INPUT}),
    )

    project = forms.CharField(
        required=True,
        label='Proje',
        widget=forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn. Proje adı — Müşteri'}),
    )
    sale_date = forms.DateField(label='Tarih', widget=forms.DateInput(attrs={'type': 'date', 'class': INPUT}))
    sale_amount = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
        label='Toplam (₺)',
        widget=forms.NumberInput(attrs={'class': MONEY, 'step': '0.01', 'placeholder': '0,00'}),
    )
    down_payment = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
        label='Peşinat (₺)',
        widget=forms.NumberInput(attrs={'class': MONEY, 'step': '0.01', 'placeholder': '0,00'}),
    )
    assigned_to = forms.ModelChoiceField(
        queryset=User.objects.order_by('username'),
        required=False,
        label='Satış Temsilcisi',
        widget=forms.Select(attrs={'class': INPUT}),
    )
    status = forms.ChoiceField(
        choices=SalesLead.STATUS_CHOICES,
        label='Satış Durumu',
        widget=forms.Select(attrs={'class': INPUT}),
    )
    notes = forms.CharField(
        required=False,
        label='Not',
        widget=forms.Textarea(attrs={
            'class': INPUT + ' min-h-[140px] resize-y',
            'rows': 6,
            'placeholder': 'Bu projeye özel notlar…',
        }),
    )

    def __init__(self, *args, instance=None, add_project_for_customer=None, **kwargs):
        self.instance = instance
        self.add_project_for_customer = add_project_for_customer
        super().__init__(*args, **kwargs)

        if instance:
            customer = instance.customer
            self.fields['use_existing_customer'].initial = False
            self.fields['use_existing_customer'].widget = forms.HiddenInput()
            self.fields['existing_customer'].initial = customer.pk
            self.fields['existing_customer'].widget = forms.HiddenInput()
            self.fields['name'].initial = customer.name
            self.fields['phone'].initial = customer.phone
            self.fields['region'].initial = customer.region
            self.fields['address'].initial = customer.address
            self.fields['location_link'].initial = customer.location_link
            self.fields['contract_date'].initial = customer.contract_date
            self.fields['project'].initial = instance.project
            self.fields['sale_date'].initial = instance.sale_date
            self.fields['sale_amount'].initial = instance.sale_amount
            self.fields['down_payment'].initial = instance.down_payment
            self.fields['assigned_to'].initial = instance.assigned_to_id
            self.fields['status'].initial = instance.status
            self.fields['notes'].initial = instance.notes
        elif add_project_for_customer:
            self.fields['use_existing_customer'].initial = True
            self.fields['use_existing_customer'].widget = forms.HiddenInput()
            self.fields['existing_customer'].initial = add_project_for_customer.pk
            self.fields['existing_customer'].widget = forms.HiddenInput()
            self.fields['name'].initial = add_project_for_customer.name
            self.fields['phone'].initial = add_project_for_customer.phone
            self.fields['region'].initial = add_project_for_customer.region
            self.fields['address'].initial = add_project_for_customer.address
            self.fields['location_link'].initial = add_project_for_customer.location_link
            self.fields['contract_date'].initial = add_project_for_customer.contract_date

    @property
    def interim_payments_initial(self):
        if not self.instance:
            return []
        return [
            {'amount': p.amount}
            for p in self.instance.interim_payments.all()
        ]

    @property
    def product_lines_initial(self):
        if not self.instance:
            return []
        return [
            {
                'product_id': line.product_id,
                'quantity': line.quantity,
                'color_id': line.color_id,
                'note': line.note or '',
            }
            for line in self.instance.product_lines.select_related('product', 'color').all()
        ]

    def clean(self):
        cleaned = super().clean()
        use_existing = cleaned.get('use_existing_customer')
        existing = cleaned.get('existing_customer')

        if self.instance:
            customer = self.instance.customer
            cleaned['name'] = customer.name
            cleaned['phone'] = customer.phone
            cleaned['region'] = customer.region
            cleaned['address'] = customer.address
            cleaned['location_link'] = customer.location_link
            cleaned['contract_date'] = customer.contract_date
        elif use_existing and existing:
            cleaned['name'] = existing.name
            cleaned['phone'] = existing.phone
            cleaned['region'] = existing.region
            cleaned['address'] = existing.address
            cleaned['location_link'] = existing.location_link
            cleaned['contract_date'] = existing.contract_date
        elif use_existing and not existing:
            self.add_error('existing_customer', 'Mevcut müşteri seçin.')
        elif not cleaned.get('name'):
            self.add_error('name', 'Ad soyad zorunludur.')

        project = (cleaned.get('project') or '').strip()
        if not project:
            self.add_error('project', 'Proje adı zorunludur.')
        else:
            cleaned['project'] = project

        if self.instance and project:
            duplicate = SalesLead.objects.filter(
                customer_id=self.instance.customer_id,
                project__iexact=project,
            ).exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error('project', 'Bu müşteride aynı isimde bir proje zaten var.')

        if not self.instance and existing and project:
            duplicate = SalesLead.objects.filter(customer=existing, project__iexact=project)
            if duplicate.exists():
                self.add_error('project', 'Bu müşteride aynı isimde bir proje zaten var.')

        return cleaned

    def _parse_interim_payments(self):
        amounts = _post_list(self.data, 'interim_payment_amount')
        payments = []
        for raw in amounts:
            amount = _parse_decimal(raw)
            if amount is not None and amount > 0:
                payments.append(amount)
        return payments

    def _parse_product_lines(self):
        product_ids = _post_list(self.data, 'product_line_product')
        quantities = _post_list(self.data, 'product_line_quantity')
        color_ids = _post_list(self.data, 'product_line_color')
        notes = _post_list(self.data, 'product_line_note')
        lines = []
        for idx, product_id in enumerate(product_ids):
            if not product_id or not str(product_id).isdigit():
                continue
            qty_raw = quantities[idx] if idx < len(quantities) else '1'
            try:
                quantity = max(1, int(qty_raw or 1))
            except (TypeError, ValueError):
                quantity = 1
            color_id = color_ids[idx] if idx < len(color_ids) else ''
            color_id = int(color_id) if color_id and str(color_id).isdigit() else None
            note = (notes[idx] if idx < len(notes) else '').strip() or None
            lines.append({
                'product_id': int(product_id),
                'quantity': quantity,
                'color_id': color_id,
                'note': note,
            })
        return lines

    def save(self):
        use_existing = self.cleaned_data.get('use_existing_customer')
        is_new_project = self.instance is None

        if use_existing and self.cleaned_data.get('existing_customer'):
            customer = self.cleaned_data['existing_customer']
        elif self.instance:
            customer = self.instance.customer
        else:
            customer = Customer()

        if is_new_project and not use_existing:
            customer.name = self.cleaned_data['name']
            customer.phone = self.cleaned_data.get('phone') or None
            customer.region = self.cleaned_data.get('region') or None
            customer.address = self.cleaned_data.get('address') or None
            customer.location_link = self.cleaned_data.get('location_link') or None
            customer.contract_date = self.cleaned_data.get('contract_date') or None
            customer.save()
        elif self.instance:
            customer.name = self.cleaned_data['name']
            customer.phone = self.cleaned_data.get('phone') or None
            customer.region = self.cleaned_data.get('region') or None
            customer.address = self.cleaned_data.get('address') or None
            customer.location_link = self.cleaned_data.get('location_link') or None
            customer.contract_date = self.cleaned_data.get('contract_date') or None
            customer.save()
        elif not use_existing:
            customer.name = self.cleaned_data['name']
            customer.phone = self.cleaned_data.get('phone') or None
            customer.region = self.cleaned_data.get('region') or None
            customer.address = self.cleaned_data.get('address') or None
            customer.location_link = self.cleaned_data.get('location_link') or None
            customer.contract_date = self.cleaned_data.get('contract_date') or None
            customer.save()

        lead = self.instance or SalesLead(customer=customer)
        lead.customer = customer
        lead.project = self.cleaned_data['project']
        lead.sale_date = self.cleaned_data['sale_date']
        lead.sale_amount = self.cleaned_data.get('sale_amount')
        lead.down_payment = self.cleaned_data.get('down_payment')
        lead.assigned_to = self.cleaned_data.get('assigned_to')
        lead.status = self.cleaned_data['status']
        lead.notes = self.cleaned_data.get('notes') or None
        lead.save()

        lead.interim_payments.all().delete()
        for order, amount in enumerate(self._parse_interim_payments()):
            SalesLeadInterimPayment.objects.create(
                sales_lead=lead,
                amount=amount,
                sort_order=order,
            )

        lead.product_lines.all().delete()
        product_ids_for_m2m = []
        for order, line in enumerate(self._parse_product_lines()):
            color = None
            if line['color_id']:
                color = ProductColorOption.objects.filter(
                    pk=line['color_id'],
                    product_id=line['product_id'],
                ).first()
            SalesLeadProductLine.objects.create(
                sales_lead=lead,
                product_id=line['product_id'],
                quantity=line['quantity'],
                color=color,
                note=line['note'],
                sort_order=order,
            )
            product_ids_for_m2m.append(line['product_id'])

        if product_ids_for_m2m:
            lead.products.set(product_ids_for_m2m)
            for product_id in product_ids_for_m2m:
                customer.products.add(product_id)
        else:
            lead.products.clear()

        self.instance = lead
        return lead
