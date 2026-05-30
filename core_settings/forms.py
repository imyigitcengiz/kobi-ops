from django import forms
from decimal import Decimal

from .color_utils import DEFAULT_HEX
from .models import (
    PriorityOption,
    ProductOption,
    ServiceTypeOption,
    SiteSettings,
    SolutionPartner,
    SolutionPartnerType,
    ServiceTeam,
    ServicePersonnel,
    PersonnelPayment,
    FinanceRecord,
    StatusOption,
    WhatsAppTemplate,
)

INPUT = 'w-full p-3 bg-slate-50 border-none rounded-xl text-sm'


class SiteSettingsForm(forms.ModelForm):
    """Geriye dönük uyumluluk — genel + AI alanları."""
    class Meta:
        model = SiteSettings
        fields = [
            'site_name', 'logo', 'company_phone', 'company_address',
            'openai_api_key', 'google_api_key', 'ai_chat_enabled', 'ai_system_prompt',
        ]
        widgets = {
            'site_name': forms.TextInput(attrs={'class': INPUT}),
            'company_phone': forms.TextInput(attrs={'class': INPUT}),
            'company_address': forms.Textarea(attrs={'class': INPUT, 'rows': 2}),
            'openai_api_key': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'sk-...'}),
            'google_api_key': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'AIza...'}),
            'ai_chat_enabled': forms.CheckboxInput(attrs={'class': 'w-5 h-5 accent-brand-600 rounded'}),
            'ai_system_prompt': forms.Textarea(attrs={'class': INPUT, 'rows': 3}),
        }


class GeneralSiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ['site_name', 'logo', 'company_phone', 'company_address']
        widgets = {
            'site_name': forms.TextInput(attrs={'class': INPUT}),
            'company_phone': forms.TextInput(attrs={'class': INPUT}),
            'company_address': forms.Textarea(attrs={'class': INPUT, 'rows': 2}),
        }


class WhatsappCloudSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ['whatsapp_cloud_token', 'whatsapp_cloud_phone_id']
        widgets = {
            'whatsapp_cloud_token': forms.PasswordInput(
                attrs={'class': INPUT, 'placeholder': 'EAA…', 'autocomplete': 'off'},
                render_value=True,
            ),
            'whatsapp_cloud_phone_id': forms.TextInput(
                attrs={'class': INPUT, 'placeholder': '123456789012345'},
            ),
        }


class AISettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ['openai_api_key', 'google_api_key', 'ai_chat_enabled', 'ai_system_prompt']
        widgets = {
            'openai_api_key': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'sk-...'}),
            'google_api_key': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'AIza...'}),
            'ai_chat_enabled': forms.CheckboxInput(attrs={'class': 'w-5 h-5 accent-violet-600 rounded'}),
            'ai_system_prompt': forms.Textarea(attrs={'class': INPUT, 'rows': 4}),
        }



class ColorOptionForm(forms.ModelForm):
    color = forms.CharField(
        widget=forms.HiddenInput(attrs={'class': 'color-picker-value'}),
        required=True,
    )

    class Meta:
        fields = ['name', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'İsim'}),
        }

    def __init__(self, *args, default_color='#3b82f6', **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get('color') and not self.data:
            self.initial['color'] = default_color


class ServiceTypeOptionForm(forms.ModelForm):
    class Meta:
        model = ServiceTypeOption
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn: Montaj'}),
        }


class ProductOptionForm(ColorOptionForm):
    class Meta(ColorOptionForm.Meta):
        model = ProductOption
        fields = ['name', 'color']
        widgets = {
            **ColorOptionForm.Meta.widgets,
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn: Pergola'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, default_color=DEFAULT_HEX['product'], **kwargs)


class StatusOptionForm(ColorOptionForm):
    class Meta(ColorOptionForm.Meta):
        model = StatusOption
        widgets = {
            **ColorOptionForm.Meta.widgets,
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn: Servis'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, default_color=DEFAULT_HEX['status'], **kwargs)


class PriorityOptionForm(ColorOptionForm):
    class Meta(ColorOptionForm.Meta):
        model = PriorityOption
        widgets = {
            **ColorOptionForm.Meta.widgets,
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn: Acil'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, default_color=DEFAULT_HEX['priority'], **kwargs)


class WhatsAppTemplateForm(forms.ModelForm):
    class Meta:
        model = WhatsAppTemplate
        fields = ['title', 'message']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full p-2 bg-slate-50 border-none rounded-xl text-sm', 'placeholder': 'Örn: Servis Tamamlandı'}),
            'message': forms.Textarea(attrs={'class': 'w-full p-2 bg-slate-50 border-none rounded-xl text-sm', 'rows': 2, 'placeholder': 'Mesaj metni...'}),
        }


class SolutionPartnerForm(forms.ModelForm):
    class Meta:
        model = SolutionPartner
        fields = ['name', 'partner_type', 'phone', 'notes', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn: ABC Taşeron'}),
            'partner_type': forms.Select(attrs={'class': INPUT}),
            'phone': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn: +90...'}),
            'notes': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn: Vinçli araç'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'w-4 h-4 accent-brand-600 rounded'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['partner_type'].queryset = SolutionPartnerType.objects.order_by('name')
        self.fields['partner_type'].empty_label = 'Tür seçin'


class SolutionPartnerTypeForm(forms.ModelForm):
    class Meta:
        model = SolutionPartnerType
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn: Taşeron Firma'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'w-4 h-4 accent-brand-600 rounded'}),
        }


class ServiceTeamForm(forms.ModelForm):
    class Meta:
        model = ServiceTeam
        fields = ['name', 'product_groups', 'company_phone', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn: Mobil Ekip 1'}),
            'product_groups': forms.SelectMultiple(attrs={'class': INPUT, 'size': 6}),
            'company_phone': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn: +9053...'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'w-4 h-4 accent-brand-600 rounded'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product_groups'].queryset = ProductOption.objects.order_by('name')


class ServicePersonnelForm(forms.ModelForm):
    class Meta:
        model = ServicePersonnel
        fields = ['name', 'team', 'product_groups', 'company_phone', 'notes', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn: Ahmet Usta'}),
            'team': forms.Select(attrs={'class': INPUT}),
            'product_groups': forms.SelectMultiple(attrs={'class': INPUT, 'size': 6}),
            'company_phone': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn: +9053...'}),
            'notes': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn: Vinç uzmanı'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'w-4 h-4 accent-brand-600 rounded'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['team'].queryset = ServiceTeam.objects.filter(is_active=True).order_by('name')
        self.fields['team'].empty_label = 'Ekip seçin'
        self.fields['product_groups'].queryset = ProductOption.objects.order_by('name')


class PayrollPersonnelQuickForm(forms.ModelForm):
    """Muhasebe panelinden hızlı personel ekleme."""

    salary_pay_date = forms.DateField(
        required=False,
        label='Maaş tarihi',
        widget=forms.DateInput(attrs={'class': INPUT, 'type': 'date'}),
    )

    class Meta:
        model = ServicePersonnel
        fields = ['name', 'team', 'company_phone', 'monthly_salary', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Ad Soyad'}),
            'team': forms.Select(attrs={'class': INPUT}),
            'company_phone': forms.TextInput(attrs={'class': INPUT, 'placeholder': '+905…'}),
            'monthly_salary': forms.NumberInput(attrs={'class': INPUT, 'step': '0.01', 'min': '0', 'placeholder': 'Aylık maaş'}),
            'notes': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Not (opsiyonel)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['team'].queryset = ServiceTeam.objects.filter(is_active=True).order_by('name')
        self.fields['team'].required = False
        self.fields['team'].empty_label = 'Ekip (opsiyonel)'
        self.fields['monthly_salary'].required = False


class AccountingPersonnelForm(forms.ModelForm):
    """Muhasebe — personel, maaş ve (opsiyonel) saha yetkinlikleri."""

    salary_pay_date = forms.DateField(
        required=False,
        label='Maaş tarihi',
        widget=forms.DateInput(attrs={'class': INPUT, 'type': 'date'}),
    )

    class Meta:
        model = ServicePersonnel
        fields = ['name', 'team', 'company_phone', 'monthly_salary', 'product_groups', 'notes', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Ad Soyad'}),
            'team': forms.Select(attrs={'class': INPUT}),
            'company_phone': forms.TextInput(attrs={'class': INPUT, 'placeholder': '+905…'}),
            'monthly_salary': forms.NumberInput(attrs={'class': INPUT, 'step': '0.01', 'min': '0', 'placeholder': 'Aylık maaş'}),
            'product_groups': forms.SelectMultiple(attrs={'class': INPUT, 'size': 4}),
            'notes': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Not (opsiyonel)'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'w-4 h-4 accent-brand-600 rounded'}),
        }

    def __init__(self, *args, show_product_groups=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['team'].queryset = ServiceTeam.objects.filter(is_active=True).order_by('name')
        self.fields['team'].required = False
        self.fields['team'].empty_label = 'Ekip (opsiyonel)'
        self.fields['monthly_salary'].required = False
        if show_product_groups:
            self.fields['product_groups'].queryset = ProductOption.objects.order_by('name')
        else:
            del self.fields['product_groups']
        if self.instance.pk and self.instance.salary_pay_day:
            from django.utils import timezone
            from core_settings.payroll import default_salary_payment_date, period_start

            period = period_start(timezone.localdate())
            self.fields['salary_pay_date'].initial = default_salary_payment_date(self.instance, period)


class PayrollQuickAdvanceForm(forms.Form):
    personnel = forms.ModelChoiceField(
        queryset=ServicePersonnel.objects.none(),
        widget=forms.HiddenInput(),
    )
    period = forms.CharField(widget=forms.HiddenInput())
    amount = forms.DecimalField(
        min_value=Decimal('0.01'),
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': INPUT, 'step': '0.01', 'min': '0.01'}),
        label='Tutar',
    )
    payment_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': INPUT, 'type': 'date'}),
        label='Tarih',
    )
    notes = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Not'}),
        label='Not',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['personnel'].queryset = ServicePersonnel.objects.filter(is_active=True)


class PersonnelAdvanceForm(forms.ModelForm):
    period = forms.CharField(
        widget=forms.TextInput(attrs={'class': INPUT, 'type': 'month'}),
        label='Dönem',
    )

    class Meta:
        model = PersonnelPayment
        fields = ['personnel', 'amount', 'payment_date', 'notes']
        widgets = {
            'personnel': forms.Select(attrs={'class': INPUT}),
            'amount': forms.NumberInput(attrs={'class': INPUT, 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
            'payment_date': forms.DateInput(attrs={'class': INPUT, 'type': 'date'}),
            'notes': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Opsiyonel not'}),
        }

    def __init__(self, *args, period_default: str = '', **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['personnel'].queryset = ServicePersonnel.objects.filter(is_active=True).order_by('name')
        self.fields['personnel'].empty_label = 'Personel seçin'
        if period_default:
            self.fields['period'].initial = period_default[:7]

    def clean_period(self):
        from core_settings.payroll import parse_period

        return parse_period(self.cleaned_data['period'])

    def save(self, commit=True):
        payment = super().save(commit=False)
        payment.payment_type = PersonnelPayment.TYPE_ADVANCE
        payment.period = self.cleaned_data['period']
        if commit:
            payment.save()
        return payment


class PersonnelSalaryAddForm(forms.Form):
    personnel = forms.ModelChoiceField(
        queryset=ServicePersonnel.objects.none(),
        widget=forms.Select(attrs={'class': INPUT}),
        label='Personel',
        empty_label='Personel seçin',
    )
    period = forms.CharField(
        widget=forms.TextInput(attrs={'class': INPUT, 'type': 'month'}),
        label='Dönem',
    )
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': INPUT, 'type': 'date'}),
        label='Ödeme tarihi',
    )
    gross_amount = forms.DecimalField(
        required=False,
        min_value=Decimal('0.01'),
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': INPUT, 'step': '0.01', 'min': '0', 'placeholder': 'Boş = aylık maaş'}),
        label='Brüt maaş (opsiyonel)',
    )
    notes = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Not (opsiyonel)'}),
        label='Not',
    )

    def __init__(self, *args, period_default: str = '', **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['personnel'].queryset = ServicePersonnel.objects.filter(is_active=True).order_by('name')
        if period_default:
            self.fields['period'].initial = period_default[:7]

    def clean_period(self):
        from core_settings.payroll import parse_period

        return parse_period(self.cleaned_data['period'])


class PersonnelSalaryPayForm(forms.Form):
    personnel = forms.ModelChoiceField(
        queryset=ServicePersonnel.objects.none(),
        widget=forms.HiddenInput(),
    )
    period = forms.CharField(widget=forms.HiddenInput())
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': INPUT, 'type': 'date'}),
        label='Ödeme tarihi',
    )
    notes = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Not (opsiyonel)'}),
        label='Not',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['personnel'].queryset = ServicePersonnel.objects.filter(is_active=True)


class PersonnelMonthlySalaryForm(forms.Form):
    personnel = forms.ModelChoiceField(
        queryset=ServicePersonnel.objects.none(),
        widget=forms.HiddenInput(),
    )
    monthly_salary = forms.DecimalField(
        min_value=Decimal('0'),
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': INPUT, 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
        label='Aylık maaş',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['personnel'].queryset = ServicePersonnel.objects.filter(is_active=True)


class PersonnelPaymentForm(forms.ModelForm):
    """Geriye dönük uyumluluk."""
    class Meta:
        model = PersonnelPayment
        fields = ['personnel', 'payment_type', 'amount', 'payment_date', 'notes']
        widgets = {
            'personnel': forms.Select(attrs={'class': INPUT}),
            'payment_type': forms.Select(attrs={'class': INPUT}),
            'amount': forms.NumberInput(attrs={'class': INPUT, 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'payment_date': forms.DateInput(attrs={'class': INPUT, 'type': 'date'}),
            'notes': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Opsiyonel not'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['personnel'].queryset = ServicePersonnel.objects.filter(is_active=True).order_by('name')
        self.fields['personnel'].empty_label = 'Personel seçin'


class FinanceRecordForm(forms.ModelForm):
    class Meta:
        model = FinanceRecord
        fields = ['record_type', 'title', 'amount', 'record_date', 'notes']
        widgets = {
            'record_type': forms.Select(attrs={'class': INPUT}),
            'title': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn: Ofis kirası'}),
            'amount': forms.NumberInput(attrs={'class': INPUT, 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'record_date': forms.DateInput(attrs={'class': INPUT, 'type': 'date'}),
            'notes': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Opsiyonel not'}),
        }

