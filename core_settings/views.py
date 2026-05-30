from django.urls import reverse
from django.views.generic import TemplateView
from django.views import View
import csv
from django.utils import timezone
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from .models import (
    SiteSettings, ServiceTypeOption, ProductOption, ProductColorOption, StatusOption, PriorityOption,
    WhatsAppTemplate, SolutionPartner, SolutionPartnerType, ServiceTeam, ServicePersonnel,
    PersonnelPayment, FinanceRecord,
)
from .forms import (
    GeneralSiteSettingsForm, SiteSettingsForm, ServiceTypeOptionForm, ProductOptionForm, StatusOptionForm,
    PriorityOptionForm, WhatsAppTemplateForm, SolutionPartnerForm, SolutionPartnerTypeForm,
    ServiceTeamForm, ServicePersonnelForm, PersonnelPaymentForm, PersonnelAdvanceForm,
    PersonnelSalaryPayForm, PersonnelSalaryAddForm, PayrollPersonnelQuickForm,
    PayrollQuickAdvanceForm, FinanceRecordForm,
)
from .payroll import (
    build_period_summary,
    build_payroll_report,
    bulk_pay_pending_salaries,
    create_salary_payment,
    default_report_range,
    default_salary_payment_date,
    parse_period,
    period_label,
    release_advances_on_salary_delete,
)
from common.permissions import (
    can_manage_payroll, can_manage_finance, can_manage_teams, can_manage_personnel,
)
from django.http import HttpResponse, JsonResponse
from common.decorators import json_auth_required, permission_required
from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
import os
import json


def _update_color_option(request, model, label):
    obj = get_object_or_404(model, pk=request.POST.get('id'))
    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, f"{label}: isim boş olamaz.")
        return
    obj.name = name
    obj.color = request.POST.get('color', obj.color)
    obj.save()
    messages.success(request, f"{label} güncellendi.")


def _safe_delete_option(request, model, label):
    obj = model.objects.filter(pk=request.POST.get('id')).first()
    if not obj:
        messages.error(request, f"{label} bulunamadı.")
        return
    try:
        obj.delete()
        messages.info(request, f"{label} silindi.")
    except ProtectedError as exc:
        count = len(exc.protected_objects)
        messages.error(
            request,
            f"Bu {label.lower()} {count} servis kaydında kullanıldığı için silinemez. "
            f"Önce ilgili servislerin {label.lower()}ünü değiştirin.",
        )


SETTINGS_SECTION_META = {
    'genel': {
        'template': 'settings/genel.html',
        'url_name': 'settings_genel',
        'title': 'Genel bilgiler',
        'icon': 'building-2',
    },
    'urunler': {
        'template': 'settings/urunler.html',
        'url_name': 'settings_products',
        'title': 'Ürünler',
        'icon': 'package',
    },
    'ariza-tipleri': {
        'template': 'settings/ariza_tipleri.html',
        'url_name': 'settings_service_types',
        'title': 'Arıza tipleri',
        'icon': 'wrench',
    },
    'durumlar': {
        'template': 'settings/durumlar.html',
        'url_name': 'settings_statuses',
        'title': 'Durumlar',
        'icon': 'list-checks',
    },
    'oncelikler': {
        'template': 'settings/oncelikler.html',
        'url_name': 'settings_priorities',
        'title': 'Öncelikler',
        'icon': 'flag',
    },
    'cozum-turleri': {
        'template': 'settings/cozum_turleri.html',
        'url_name': 'settings_partner_types',
        'title': 'Çözüm ortağı türleri',
        'icon': 'handshake',
    },
}


class SiteSettingsView(TemplateView):
    """Site genel ayarları — /ayarlar/<bölüm>/ (servis modülünden bağımsız)."""
    section = 'genel'

    def dispatch(self, request, *args, **kwargs):
        self.section = kwargs.pop('section', self.section)
        if self.section not in SETTINGS_SECTION_META:
            self.section = 'genel'
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [SETTINGS_SECTION_META[self.section]['template']]

    def _build_options_context(self):
        service_types = ServiceTypeOption.objects.prefetch_related('products').all().order_by('name')
        products = ProductOption.objects.prefetch_related('service_types', 'color_options').all().order_by('name')
        return {
            'settings_section': self.section,
            'settings_section_meta': SETTINGS_SECTION_META,
            'settings_form': GeneralSiteSettingsForm(instance=SiteSettings.objects.first()),
            'service_type_form': ServiceTypeOptionForm(),
            'product_form': ProductOptionForm(),
            'status_form': StatusOptionForm(),
            'priority_form': PriorityOptionForm(),
            'solution_partner_type_form': SolutionPartnerTypeForm(),
            'service_types': service_types,
            'products': products,
            'all_service_types': service_types,
            'all_products': products,
            'statuses': StatusOption.objects.order_by('sort_order', 'name'),
            'priorities': PriorityOption.objects.all(),
            'solution_partner_types': SolutionPartnerType.objects.all(),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self._build_options_context())
        meta = SETTINGS_SECTION_META[self.section]
        context['page_title'] = meta['title']
        context['page_icon'] = meta['icon']
        return context

    def _redirect_after_post(self):
        return redirect(SETTINGS_SECTION_META[self.section]['url_name'])

    def post(self, request, *args, **kwargs):
        if 'update_site' in request.POST:
            settings = SiteSettings.objects.first()
            form = GeneralSiteSettingsForm(request.POST, request.FILES, instance=settings)
            try:
                if form.is_valid():
                    form.save()
                    messages.success(request, "Site ayarları güncellendi.")
                else:
                    # Show detailed form errors to help debugging
                    messages.error(request, f"Ayarlar güncellenirken hata oluştu: {form.errors.as_text()}")
            except Exception as e:
                messages.error(request, f"Ayarlar kaydedilirken beklenmeyen hata oluştu: {str(e)}")
                
        elif 'add_service_type' in request.POST:
            form = ServiceTypeOptionForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Servis tipi eklendi.")
            else:
                messages.error(request, "Geçersiz servis tipi verisi.")
                
        elif 'add_product' in request.POST:
            form = ProductOptionForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Ürün eklendi.")
            else:
                messages.error(request, "Geçersiz ürün verisi.")
                
        elif 'add_status' in request.POST:
            form = StatusOptionForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Durum seçeneği eklendi.")
            else:
                messages.error(request, "Geçersiz durum verisi. İsim ve renk gerekli.")
                
        elif 'add_priority' in request.POST:
            form = PriorityOptionForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Öncelik seçeneği eklendi.")
            else:
                messages.error(request, "Geçersiz öncelik verisi. İsim ve renk gerekli.")
                
        elif 'add_solution_partner_type' in request.POST:
            form = SolutionPartnerTypeForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Çözüm ortağı türü eklendi.")
            else:
                messages.error(request, "Geçersiz tür verisi.")
        elif 'update_service_type' in request.POST:
            obj = get_object_or_404(ServiceTypeOption, pk=request.POST.get('id'))
            obj.products.set(request.POST.getlist('product_ids'))
            messages.success(request, "Servis tipi ürün ilişkileri güncellendi.")
        elif 'update_product' in request.POST:
            obj = get_object_or_404(ProductOption, pk=request.POST.get('id'))
            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, "Ürün: isim boş olamaz.")
            else:
                obj.name = name
                obj.color = request.POST.get('color', obj.color)
                obj.save()
                obj.service_types.set(request.POST.getlist('service_type_ids'))
                messages.success(request, "Ürün güncellendi.")
        elif 'add_product_color' in request.POST:
            product = get_object_or_404(ProductOption, pk=request.POST.get('product_id'))
            color_name = request.POST.get('color_name', '').strip()
            if not color_name:
                messages.error(request, "Renk adı boş olamaz.")
            elif ProductColorOption.objects.filter(product=product, name__iexact=color_name).exists():
                messages.error(request, "Bu ürün için aynı renk adı zaten var.")
            else:
                ProductColorOption.objects.create(
                    product=product,
                    name=color_name,
                    color=request.POST.get('color', '#0284c7'),
                )
                messages.success(request, f"{product.name} için renk eklendi.")
        elif 'delete_product_color' in request.POST:
            color = ProductColorOption.objects.filter(pk=request.POST.get('color_id')).first()
            if color:
                label = f"{color.product.name} — {color.name}"
                try:
                    color.delete()
                    messages.info(request, f"Renk silindi: {label}")
                except Exception:
                    messages.error(request, "Bu renk satış kayıtlarında kullanıldığı için silinemez.")
        elif 'update_status' in request.POST:
            _update_color_option(request, StatusOption, 'Durum')
        elif 'update_priority' in request.POST:
            _update_color_option(request, PriorityOption, 'Öncelik')
        elif 'update_solution_partner_type' in request.POST:
            obj = get_object_or_404(SolutionPartnerType, pk=request.POST.get('id'))
            form = SolutionPartnerTypeForm(request.POST, instance=obj)
            if form.is_valid():
                form.save()
                messages.success(request, "Çözüm ortağı türü güncellendi.")
            else:
                messages.error(request, "Tür güncellenemedi.")
        elif 'delete_service_type' in request.POST:
            _safe_delete_option(request, ServiceTypeOption, 'Servis tipi')
        elif 'delete_product' in request.POST:
            _safe_delete_option(request, ProductOption, 'Ürün')
        elif 'delete_status' in request.POST:
            _safe_delete_option(request, StatusOption, 'Durum')
        elif 'delete_priority' in request.POST:
            _safe_delete_option(request, PriorityOption, 'Öncelik')
        elif 'delete_solution_partner_type' in request.POST:
            try:
                SolutionPartnerType.objects.filter(id=request.POST.get('id')).delete()
                messages.info(request, "Çözüm ortağı türü silindi.")
            except Exception:
                messages.error(request, "Bu tür kullanımda olduğu için silinemedi.")

        return self._redirect_after_post()



class WhatsAppTemplatesView(TemplateView):
    template_name = 'crm/whatsapp_templates.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['whatsapp_form'] = WhatsAppTemplateForm()
        context['whatsapp_templates'] = WhatsAppTemplate.objects.all()
        return context

    def post(self, request, *args, **kwargs):
        if 'add_whatsapp' in request.POST:
            form = WhatsAppTemplateForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "WhatsApp şablonu eklendi.")
            else:
                messages.error(request, "Geçersiz şablon verisi.")
        elif 'update_whatsapp' in request.POST:
            obj = get_object_or_404(WhatsAppTemplate, pk=request.POST.get('id'))
            title = request.POST.get('title', '').strip()
            message = request.POST.get('message', '').strip()
            if not title or not message:
                messages.error(request, "Şablon başlığı ve mesajı gerekli.")
            else:
                obj.title = title
                obj.message = message
                obj.save()
                messages.success(request, "WhatsApp şablonu güncellendi.")
        elif 'delete_whatsapp' in request.POST:
            WhatsAppTemplate.objects.filter(id=request.POST.get('id')).delete()
            messages.info(request, "Şablon silindi.")
        return redirect('contact_whatsapp_templates')


class SolutionNetworkView(TemplateView):
    template_name = 'crm/solution_network.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        q = self.request.GET.get('q', '').strip()
        t = self.request.GET.get('type', '').strip()
        active = self.request.GET.get('active', '').strip()

        partners = SolutionPartner.objects.all().order_by('name')
        if q:
            partners = partners.filter(
                Q(name__icontains=q) | Q(phone__icontains=q) | Q(notes__icontains=q)
            )
        if t and t.isdigit():
            partners = partners.filter(partner_type_id=int(t))
        if active == '1':
            partners = partners.filter(is_active=True)
        elif active == '0':
            partners = partners.filter(is_active=False)

        context['solution_partner_form'] = SolutionPartnerForm()
        context['solution_partners'] = partners
        context['partner_types'] = SolutionPartnerType.objects.order_by('name')
        context['active_count'] = SolutionPartner.objects.filter(is_active=True).count()
        context['total_count'] = SolutionPartner.objects.count()
        return context

    def post(self, request, *args, **kwargs):
        if 'add_solution_partner' in request.POST:
            form = SolutionPartnerForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Çözüm ortağı eklendi.")
            else:
                messages.error(request, "Geçersiz çözüm ortağı verisi.")
        elif 'update_solution_partner' in request.POST:
            obj = get_object_or_404(SolutionPartner, pk=request.POST.get('id'))
            form = SolutionPartnerForm(request.POST, instance=obj)
            if form.is_valid():
                form.save()
                messages.success(request, "Çözüm ortağı güncellendi.")
            else:
                messages.error(request, "Çözüm ortağı güncellenemedi.")
        elif 'delete_solution_partner' in request.POST:
            SolutionPartner.objects.filter(id=request.POST.get('id')).delete()
            messages.info(request, "Çözüm ortağı silindi.")
        return redirect('solution_network')


class TeamNetworkView(TemplateView):
    template_name = 'crm/team_network.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_manage_teams'] = can_manage_teams(self.request.user)
        context['team_form'] = ServiceTeamForm()
        context['teams'] = ServiceTeam.objects.prefetch_related('product_groups').all().order_by('name')
        return context

    def post(self, request, *args, **kwargs):
        if not can_manage_teams(request.user):
            messages.error(request, 'Ekip yönetimi için yetkiniz yok.')
            return redirect('team_network')
        if 'add_team' in request.POST:
            form = ServiceTeamForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Ekip eklendi.')
            else:
                messages.error(request, 'Ekip kaydı eklenemedi.')
        elif 'update_team' in request.POST:
            obj = get_object_or_404(ServiceTeam, pk=request.POST.get('id'))
            form = ServiceTeamForm(request.POST, instance=obj)
            if form.is_valid():
                form.save()
                messages.success(request, 'Ekip güncellendi.')
            else:
                messages.error(request, 'Ekip güncellenemedi.')
        elif 'delete_team' in request.POST:
            try:
                ServiceTeam.objects.filter(id=request.POST.get('id')).delete()
                messages.info(request, 'Ekip silindi.')
            except Exception:
                messages.error(request, 'Ekip silinemedi.')
        return redirect('team_network')


class PersonnelNetworkView(TemplateView):
    template_name = 'crm/personnel_network.html'

    def dispatch(self, request, *args, **kwargs):
        if not can_manage_personnel(request.user):
            messages.error(request, 'Personel kayıtları için yetkiniz yok.')
            return redirect('contact_hub')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        q = self.request.GET.get('q', '').strip()
        team = self.request.GET.get('team', '').strip()

        personnel = ServicePersonnel.objects.select_related('team').prefetch_related('product_groups').all().order_by('name')
        if q:
            personnel = personnel.filter(Q(name__icontains=q) | Q(company_phone__icontains=q) | Q(notes__icontains=q))
        if team and team.isdigit():
            personnel = personnel.filter(team_id=int(team))

        context['can_manage_personnel'] = True
        context['personnel_form'] = ServicePersonnelForm()
        context['teams'] = ServiceTeam.objects.all().order_by('name')
        context['personnel_list'] = personnel
        return context

    def post(self, request, *args, **kwargs):
        if 'add_personnel' in request.POST:
            if not can_manage_personnel(request.user):
                messages.error(request, 'Personel yönetimi için yetkiniz yok.')
                return redirect('personnel_network')
            form = ServicePersonnelForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Personel eklendi.')
            else:
                messages.error(request, 'Personel kaydı eklenemedi.')
        elif 'update_personnel' in request.POST:
            if not can_manage_personnel(request.user):
                messages.error(request, 'Personel yönetimi için yetkiniz yok.')
                return redirect('personnel_network')
            obj = get_object_or_404(ServicePersonnel, pk=request.POST.get('id'))
            form = ServicePersonnelForm(request.POST, instance=obj)
            if form.is_valid():
                form.save()
                messages.success(request, 'Personel güncellendi.')
            else:
                messages.error(request, 'Personel güncellenemedi.')
        elif 'delete_personnel' in request.POST:
            if not can_manage_personnel(request.user):
                messages.error(request, 'Personel yönetimi için yetkiniz yok.')
                return redirect('personnel_network')
            ServicePersonnel.objects.filter(id=request.POST.get('id')).delete()
            messages.info(request, 'Personel silindi.')
        return redirect('personnel_network')


class AccountingHubView(TemplateView):
    template_name = 'muhasebe/index.html'


class AccountingReportsHubView(TemplateView):
    template_name = 'muhasebe/reports_hub.html'

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        can_payroll = can_manage_payroll(user)
        can_sales = user.is_superuser or user.has_perm_codename('sales.reports')
        if not can_payroll and not can_sales:
            messages.error(request, 'Raporlar için yetkiniz yok.')
            return redirect('accounting_hub')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['show_payroll_report'] = can_manage_payroll(user)
        context['show_sales_report'] = user.is_superuser or user.has_perm_codename('sales.reports')
        return context


class AccountingPayrollView(TemplateView):
    template_name = 'muhasebe/payroll.html'

    def dispatch(self, request, *args, **kwargs):
        if not can_manage_payroll(request.user):
            messages.error(request, 'Maaş/avans kayıtları için yetkiniz yok.')
            return redirect('accounting_hub')
        return super().dispatch(request, *args, **kwargs)

    def _selected_period(self):
        return parse_period(self.request.GET.get('period'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period = self._selected_period()
        period_str = period.strftime('%Y-%m')
        payment_personnel = self.request.GET.get('payment_personnel', '').strip()

        personnel_qs = ServicePersonnel.objects.filter(is_active=True).order_by('name')
        if payment_personnel and payment_personnel.isdigit():
            personnel_qs = personnel_qs.filter(id=int(payment_personnel))

        summary = build_period_summary(period, personnel_qs)
        payments = PersonnelPayment.objects.select_related(
            'personnel', 'recorded_by', 'settled_by',
        ).filter(period=period)
        if payment_personnel and payment_personnel.isdigit():
            payments = payments.filter(personnel_id=int(payment_personnel))

        context['period'] = period
        context['period_str'] = period_str
        context['period_label'] = period_label(period)
        context['payroll_summary'] = summary
        context['advance_form'] = PersonnelAdvanceForm(period_default=period_str)
        context['salary_form'] = PersonnelSalaryAddForm(period_default=period_str)
        context['personnel_form'] = PayrollPersonnelQuickForm()
        context['teams'] = ServiceTeam.objects.filter(is_active=True).order_by('name')
        context['pending_pay_count'] = sum(1 for r in summary['rows'] if r['can_pay'])
        context['recent_payments'] = payments.order_by('-payment_date', '-created_at')
        context['all_personnel'] = ServicePersonnel.objects.filter(is_active=True).order_by('name')
        context['filter_personnel'] = payment_personnel
        context['personnel_pay_meta'] = {
            str(p.id): {
                'due_date': default_salary_payment_date(p, period).isoformat(),
                'gross': str(p.monthly_salary) if p.monthly_salary else '',
                'pay_day': p.salary_pay_day or '',
            }
            for p in context['all_personnel']
        }
        return context

    def post(self, request, *args, **kwargs):
        period = parse_period(request.POST.get('period') or request.GET.get('period'))
        period_qs = f'?period={period.strftime("%Y-%m")}'
        personnel_filter = request.POST.get('payment_personnel') or request.GET.get('payment_personnel', '')
        if personnel_filter:
            period_qs += f'&payment_personnel={personnel_filter}'

        if not can_manage_payroll(request.user):
            messages.error(request, 'Maaş/avans kaydı için yetkiniz yok.')
            return redirect('accounting_payroll')

        if 'add_personnel' in request.POST:
            form = PayrollPersonnelQuickForm(request.POST)
            if form.is_valid():
                person = form.save()
                messages.success(request, f'{person.name} personel listesine eklendi.')
            else:
                messages.error(request, 'Personel eklenemedi. Ad soyad zorunludur.')
        elif 'quick_advance' in request.POST:
            form = PayrollQuickAdvanceForm(request.POST)
            if form.is_valid():
                pay_period = parse_period(form.cleaned_data['period'])
                payment = PersonnelPayment.objects.create(
                    personnel=form.cleaned_data['personnel'],
                    payment_type=PersonnelPayment.TYPE_ADVANCE,
                    period=pay_period,
                    amount=form.cleaned_data['amount'],
                    payment_date=form.cleaned_data.get('payment_date') or timezone.localdate(),
                    notes=form.cleaned_data.get('notes') or '',
                    recorded_by=request.user if request.user.is_authenticated else None,
                )
                messages.success(request, f'{payment.personnel.name} için {payment.amount} ₺ avans kaydedildi.')
            else:
                messages.error(request, 'Hızlı avans kaydedilemedi.')
        elif 'bulk_pay_salaries' in request.POST:
            result = bulk_pay_pending_salaries(period, request.user if request.user.is_authenticated else None)
            if result['paid']:
                names = ', '.join(result['paid'][:5])
                if len(result['paid']) > 5:
                    names += '…'
                messages.success(request, f"{len(result['paid'])} personelin maaşı ödendi: {names}")
            for name, reason in result['skipped'][:3]:
                messages.warning(request, f'{name}: {reason}')
            if not result['paid'] and not result['skipped']:
                messages.info(request, 'Bu dönemde ödenecek bekleyen maaş yok.')
        elif 'add_advance' in request.POST:
            form = PersonnelAdvanceForm(request.POST, period_default=period.strftime('%Y-%m'))
            if form.is_valid():
                payment = form.save(commit=False)
                if request.user.is_authenticated:
                    payment.recorded_by = request.user
                payment.save()
                messages.success(request, f'{payment.personnel.name} için avans kaydedildi.')
            else:
                messages.error(request, 'Avans kaydı eklenemedi.')
        elif 'add_salary' in request.POST:
            form = PersonnelSalaryAddForm(request.POST, period_default=period.strftime('%Y-%m'))
            if form.is_valid():
                personnel = form.cleaned_data['personnel']
                pay_period = form.cleaned_data['period']
                try:
                    create_salary_payment(
                        personnel=personnel,
                        period=pay_period,
                        payment_date=form.cleaned_data['payment_date'],
                        recorded_by=request.user if request.user.is_authenticated else None,
                        gross_override=form.cleaned_data.get('gross_amount'),
                        notes=form.cleaned_data.get('notes') or '',
                    )
                    messages.success(request, f'{personnel.name} — {period_label(pay_period)} maaşı kaydedildi.')
                except ValueError as exc:
                    messages.error(request, str(exc))
            else:
                messages.error(request, 'Maaş kaydı eklenemedi.')
        elif 'pay_salary' in request.POST:
            form = PersonnelSalaryPayForm(request.POST)
            if form.is_valid():
                personnel = form.cleaned_data['personnel']
                pay_period = parse_period(form.cleaned_data['period'])
                try:
                    create_salary_payment(
                        personnel=personnel,
                        period=pay_period,
                        payment_date=form.cleaned_data['payment_date'],
                        recorded_by=request.user if request.user.is_authenticated else None,
                        notes=form.cleaned_data.get('notes') or '',
                    )
                    messages.success(request, f'{personnel.name} — {period_label(pay_period)} maaşı net olarak kaydedildi.')
                except ValueError as exc:
                    messages.error(request, str(exc))
            else:
                messages.error(request, 'Maaş ödemesi kaydedilemedi.')
        elif 'update_monthly_salary' in request.POST:
            personnel_id = request.POST.get('personnel')
            raw_salary = (request.POST.get('monthly_salary') or '').strip().replace(',', '.')
            raw_pay_day = (request.POST.get('salary_pay_day') or '').strip()
            person = ServicePersonnel.objects.filter(pk=personnel_id, is_active=True).first()
            if not person:
                messages.error(request, 'Personel bulunamadı.')
            else:
                from decimal import Decimal

                if raw_salary:
                    person.monthly_salary = Decimal(raw_salary)
                else:
                    person.monthly_salary = None
                if raw_pay_day:
                    day = int(raw_pay_day)
                    if day < 1 or day > 31:
                        messages.error(request, 'Maaş günü 1–31 arasında olmalı.')
                        return redirect(f"{reverse('accounting_payroll')}{period_qs}")
                    person.salary_pay_day = day
                else:
                    person.salary_pay_day = None
                person.save(update_fields=['monthly_salary', 'salary_pay_day'])
                messages.success(request, f'{person.name} maaş bilgileri güncellendi.')
        elif 'delete_payment' in request.POST:
            payment = PersonnelPayment.objects.filter(id=request.POST.get('id')).first()
            if not payment:
                messages.error(request, 'Kayıt bulunamadı.')
            elif payment.payment_type == PersonnelPayment.TYPE_ADVANCE and payment.settled_by_id:
                messages.error(request, 'Mahsup edilmiş avans silinemez. Önce ilgili maaş kaydını silin.')
            else:
                if payment.payment_type == PersonnelPayment.TYPE_SALARY:
                    release_advances_on_salary_delete(payment)
                payment.delete()
                messages.info(request, 'Ödeme kaydı silindi.')
        return redirect(f"{reverse('accounting_payroll')}{period_qs}")


class AccountingPayrollReportsView(TemplateView):
    template_name = 'muhasebe/payroll_reports.html'

    def dispatch(self, request, *args, **kwargs):
        if not can_manage_payroll(request.user):
            messages.error(request, 'Maaş raporları için yetkiniz yok.')
            return redirect('accounting_hub')
        return super().dispatch(request, *args, **kwargs)

    def _report_params(self):
        default_from, default_to = default_report_range()
        period_from = parse_period(self.request.GET.get('period_from') or default_from.strftime('%Y-%m'))
        period_to = parse_period(self.request.GET.get('period_to') or default_to.strftime('%Y-%m'))
        personnel_id = self.request.GET.get('personnel', '').strip()
        personnel_qs = ServicePersonnel.objects.filter(is_active=True).order_by('name')
        if personnel_id.isdigit():
            personnel_qs = personnel_qs.filter(id=int(personnel_id))
        return period_from, period_to, personnel_qs, personnel_id

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period_from, period_to, personnel_qs, personnel_id = self._report_params()
        report = build_payroll_report(period_from, period_to, personnel_qs)
        context.update(report)
        context['period_from_str'] = period_from.strftime('%Y-%m')
        context['period_to_str'] = period_to.strftime('%Y-%m')
        context['filter_personnel'] = personnel_id
        context['all_personnel'] = ServicePersonnel.objects.filter(is_active=True).order_by('name')
        context['export_query'] = self.request.GET.urlencode()
        return context


class AccountingPayrollExportView(View):
    def get(self, request, *args, **kwargs):
        if not can_manage_payroll(request.user):
            messages.error(request, 'Dışa aktarma için yetkiniz yok.')
            return redirect('accounting_reports')

        default_from, default_to = default_report_range()
        period_from = parse_period(request.GET.get('period_from') or default_from.strftime('%Y-%m'))
        period_to = parse_period(request.GET.get('period_to') or default_to.strftime('%Y-%m'))
        personnel_id = request.GET.get('personnel', '').strip()
        personnel_qs = ServicePersonnel.objects.filter(is_active=True).order_by('name')
        if personnel_id.isdigit():
            personnel_qs = personnel_qs.filter(id=int(personnel_id))

        report = build_payroll_report(period_from, period_to, personnel_qs)
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="maas-avans-{period_from.strftime("%Y-%m")}-{period_to.strftime("%Y-%m")}.csv"'
        )
        response.write('\ufeff')
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['Dönem', 'Personel', 'Ekip', 'Brüt', 'Avans (toplam)', 'Bekleyen avans', 'Net (beklenen)', 'Net (ödenen)', 'Durum'])
        for row in report['rows']:
            writer.writerow([
                row['period_label'],
                row['personnel'].name,
                row['personnel'].team.name if row['personnel'].team_id else '—',
                row['gross'],
                row['advances_all'],
                row['advances_open'],
                row['net_expected'] if row['net_expected'] is not None else '',
                row['net_paid'],
                row['status'],
            ])
        writer.writerow([])
        writer.writerow(['TOPLAM', '', '', report['totals']['gross'], report['totals']['advances'], '', report['totals']['pending_net'], report['totals']['net_paid'], ''])
        return response


class AccountingFinanceView(TemplateView):
    template_name = 'muhasebe/finance.html'

    def dispatch(self, request, *args, **kwargs):
        if not can_manage_finance(request.user):
            messages.error(request, 'Gelir/gider kayıtları için yetkiniz yok.')
            return redirect('accounting_hub')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        record_type = self.request.GET.get('record_type', '').strip()
        records = FinanceRecord.objects.select_related('recorded_by').all()
        if record_type in (FinanceRecord.TYPE_INCOME, FinanceRecord.TYPE_EXPENSE):
            records = records.filter(record_type=record_type)
        context['finance_form'] = FinanceRecordForm()
        context['recent_records'] = records.order_by('-record_date', '-created_at')[:100]
        return context

    def post(self, request, *args, **kwargs):
        if 'add_finance' in request.POST:
            if not can_manage_finance(request.user):
                messages.error(request, 'Gelir/gider kaydı için yetkiniz yok.')
                return redirect('accounting_finance')
            form = FinanceRecordForm(request.POST)
            if form.is_valid():
                record = form.save(commit=False)
                if request.user.is_authenticated:
                    record.recorded_by = request.user
                record.save()
                messages.success(request, 'Kayıt eklendi.')
            else:
                messages.error(request, 'Kayıt eklenemedi.')
        elif 'delete_finance' in request.POST:
            if not can_manage_finance(request.user):
                messages.error(request, 'Gelir/gider kaydı için yetkiniz yok.')
                return redirect('accounting_finance')
            FinanceRecord.objects.filter(id=request.POST.get('id')).delete()
            messages.info(request, 'Kayıt silindi.')
        return redirect('accounting_finance')


@json_auth_required
@permission_required('access.settings')
def settings_api(request):
    """SiteSettings JSON API — kimlik doğrulama, CSRF ve access.settings zorunlu."""
    try:
        settings = SiteSettings.objects.first()
        if request.method == 'GET':
            return JsonResponse({
                'site_name': settings.site_name if settings else '',
                'company_phone': settings.company_phone if settings else '',
                'company_address': settings.company_address if settings else '',
                'ai_chat_enabled': settings.ai_chat_enabled if settings else False,
                'ai_system_prompt': settings.ai_system_prompt if settings else '',
            })

        if request.method == 'POST':
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
            form = SiteSettingsForm(data, files=None, instance=settings)
            if form.is_valid():
                form.save()
                return JsonResponse({'success': True})
            return JsonResponse({'error': 'validation_error', 'details': form.errors}, status=400)

        return JsonResponse({'error': 'Method not allowed'}, status=405)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Geçersiz JSON'}, status=400)
    except Exception:
        return JsonResponse({'error': 'İşlem başarısız.'}, status=500)


def _serialize_option(obj):
    return {'id': obj.id, 'name': obj.name, 'color': obj.color_hex}


@json_auth_required
@permission_required('access.services', 'access.settings', any_perm=True)
def options_catalog_api(request):
    """Servis formu için tüm seçenekler ve ürün–servis tipi eşlemesi."""
    from core_settings.catalog import build_options_catalog

    return JsonResponse(build_options_catalog())


@json_auth_required
@permission_required('access.services', 'access.settings', any_perm=True)
def service_types_for_products_api(request):
    """Seçili ürünlere göre servis tiplerini döndürür."""
    raw = request.GET.get('product_ids', '')
    product_ids = [int(x) for x in raw.split(',') if x.strip().isdigit()]
    all_types = list(ServiceTypeOption.objects.order_by('name'))

    if not product_ids:
        return JsonResponse({
            'service_types': [_serialize_option(s) for s in all_types],
            'filter_mode': 'none',
            'message': 'Ürün seçilmedi; tüm servis tipleri listeleniyor.',
        })

    from core_settings.catalog import resolve_allowed_service_type_ids

    allowed_ids, mode = resolve_allowed_service_type_ids(product_ids)
    if mode == 'all_fallback':
        filtered = all_types
        message = (
            'Seçili ürünlerde tanımlı arıza tipi yok veya en az bir üründe eşleme yok; '
            'tüm tipler gösteriliyor.'
        )
    else:
        filtered = [s for s in all_types if s.id in allowed_ids]
        message = f'{len(filtered)} servis tipi bu ürün(ler) için tanımlı.'

    return JsonResponse({
        'service_types': [_serialize_option(s) for s in filtered],
        'filter_mode': mode,
        'message': message,
    })


@json_auth_required
@permission_required('services.manage', 'access.settings', any_perm=True)
def quick_option_create_api(request):
    """Servis formundan hızlı seçenek ekleme."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Geçersiz JSON'}, status=400)

    kind = data.get('type')
    name = (data.get('name') or '').strip()
    color = data.get('color') or '#3b82f6'

    if not name:
        return JsonResponse({'error': 'İsim gerekli'}, status=400)

    model_map = {
        'status': StatusOption,
        'priority': PriorityOption,
        'product': ProductOption,
        'service_type': ServiceTypeOption,
    }
    model = model_map.get(kind)
    if not model:
        return JsonResponse({'error': 'Geçersiz tip'}, status=400)

    obj = model.objects.create(name=name, color=color)
    payload = _serialize_option(obj)
    if kind == 'product':
        st_ids = data.get('service_type_ids') or []
        if st_ids:
            obj.service_types.set(st_ids)
        payload['service_type_ids'] = list(obj.service_types.values_list('id', flat=True))
    if kind == 'service_type':
        product_ids = [int(x) for x in data.get('product_ids') or [] if str(x).isdigit()]
        for product in ProductOption.objects.filter(id__in=product_ids):
            product.service_types.add(obj)
        payload['product_ids'] = list(obj.products.values_list('id', flat=True))

    from config.live_sync import publish_live_event

    publish_live_event(
        kind='options',
        action='created',
        message='Yeni seçenek eklendi.',
        user_id=getattr(request.user, 'id', None),
    )
    return JsonResponse({'ok': True, 'item': payload, 'type': kind})


@json_auth_required
@permission_required('services.manage', 'access.settings', any_perm=True)
def quick_option_update_api(request):
    """Servis formundan hızlı seçenek güncelleme."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Geçersiz JSON'}, status=400)

    kind = data.get('type')
    pk = data.get('id')
    name = (data.get('name') or '').strip()
    if not pk or not name:
        return JsonResponse({'error': 'id ve name gerekli'}, status=400)

    model_map = {
        'status': StatusOption,
        'priority': PriorityOption,
        'product': ProductOption,
        'service_type': ServiceTypeOption,
    }
    model = model_map.get(kind)
    if not model:
        return JsonResponse({'error': 'Geçersiz tip'}, status=400)

    obj = get_object_or_404(model, pk=pk)
    obj.name = name
    if 'color' in data:
        obj.color = data['color']
    obj.save()

    if kind == 'product' and 'service_type_ids' in data:
        obj.service_types.set(data['service_type_ids'] or [])

    if kind == 'service_type' and 'product_ids' in data:
        product_ids = [int(x) for x in data.get('product_ids') or [] if str(x).isdigit()]
        for product in ProductOption.objects.filter(id__in=product_ids):
            product.service_types.add(obj)

    payload = _serialize_option(obj)
    if kind == 'product':
        payload['service_type_ids'] = list(obj.service_types.values_list('id', flat=True))
    if kind == 'service_type':
        payload['product_ids'] = list(obj.products.values_list('id', flat=True))

    from config.live_sync import publish_live_event

    publish_live_event(
        kind='options',
        action='updated',
        message='Seçenek güncellendi.',
        user_id=getattr(request.user, 'id', None),
    )
    return JsonResponse({'ok': True, 'item': payload})
