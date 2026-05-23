from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse, reverse_lazy
from django.shortcuts import redirect, render, get_object_or_404
from django.db.models import Q, Min, Case, When, IntegerField
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.views.decorators.http import require_POST, require_http_methods
import csv
from common.decorators import permission_required
from common.permissions import (
    SERVICES_BULK_PERM,
    SERVICES_DELETE_PERM,
    SERVICES_MANAGE_PERM,
    SERVICES_PRINT_PERM,
    SERVICES_WHATSAPP_PERM,
)
from users.mixins import PermissionRequiredMixin
from .models import ServiceRecord, ServiceImage, ServiceHistory
from .forms import ServiceRecordForm
from config.live_sync import publish_live_event, suppress_live_sync
from .form_context import build_service_form_context
from .whatsapp_status_prompt import (
    build_whatsapp_service_created_prompt,
    build_whatsapp_status_change_preview,
    build_whatsapp_status_change_prompt,
    dispatch_confirmed_scenario,
    dispatch_confirmed_status_whatsapp,
    pop_whatsapp_status_prompt_queue,
    queue_whatsapp_status_prompts,
)
from core_settings.models import ServiceTeam, ServicePersonnel, StatusOption, PriorityOption, SiteSettings
from core_settings.status_defaults import apply_service_list_visibility, ensure_default_statuses
from customers.media_utils import ingest_customer_media_uploads
from customers.models import CustomerMedia
from .customer_services import (
    build_service_customer_groups,
    customer_services_payload,
    get_active_status,
    is_open_service,
)


def _normalize_phone_for_wa(phone_raw):
    clean_phone = ''.join(ch for ch in (phone_raw or '') if ch.isdigit())
    if clean_phone.startswith('0'):
        clean_phone = '9' + clean_phone
    elif not clean_phone.startswith('90') and len(clean_phone) == 10:
        clean_phone = '90' + clean_phone
    return clean_phone


def _build_service_summary_message(target_label, services):
    lines = [f"{target_label} için servis özeti ({len(services)} kayıt):", ""]
    for index, s in enumerate(services, start=1):
        service_types = ", ".join([st.name for st in s.service_types.all()]) or "-"
        note = (s.notes or "-").strip() or "-"
        lines.append(f"{index}. Kayıt")
        lines.append(f"Müşteri Adı: {s.customer.name}")
        lines.append(f"Müşteri Telefonu: {s.customer.phone or '-TELEFON YOK- (Müşteriden telefon isteyin)'}")
        lines.append(f"Bölge: {s.customer.region or '-'}")
        lines.append(f"Arıza Tipi: {service_types}")
        lines.append(f"Servis Notu: {note}")
        if s.customer.location_link:
            lines.append(f"Konum URL: {s.customer.location_link}")
        else:
            lines.append("Konum URL: -URL Konum Yok- (Müşteriden konum isteyin)")
        lines.append("")
    return "\n".join(lines)


def _apply_service_filters(qs, request):
    ensure_default_statuses()
    q = request.GET.get('q')
    priority = request.GET.get('priority')
    product = request.GET.get('product')
    warranty = request.GET.get('warranty')

    if q:
        qs = qs.filter(
            Q(customer__name__icontains=q) |
            Q(customer__phone__icontains=q) |
            Q(customer__region__icontains=q) |
            Q(notes__icontains=q) |
            Q(products__name__icontains=q) |
            Q(service_types__name__icontains=q)
        )
    qs = apply_service_list_visibility(qs, request)
    if priority:
        qs = qs.filter(priority_id=priority)
    if product:
        qs = qs.filter(products__id=product)
    if warranty == 'expired':
        qs = qs.filter(Q(warranty_status='expired') | Q(status__name__icontains='ücretli'))
    elif warranty == 'active':
        qs = qs.filter(warranty_status='active').exclude(status__name__icontains='ücretli')
    return qs.distinct()


def _build_service_snapshot(service):
    customer = service.customer
    return {
        'service': {
            'status_id': service.status_id,
            'priority_id': service.priority_id,
            'solution_partner_id': service.solution_partner_id,
            'assigned_to_id': service.assigned_to_id,
            'service_personnel_id': service.service_personnel_id,
            'warranty_status': service.warranty_status,
            'list_price': service.list_price,
            'discounted_price': service.discounted_price,
            'notes': service.notes or '',
            'product_ids': list(service.products.values_list('id', flat=True)),
            'service_type_ids': list(service.service_types.values_list('id', flat=True)),
        },
        'customer': {
            'phone': customer.phone or '',
            'region': customer.region or '',
            'location_link': customer.location_link or '',
            'contract_date': customer.contract_date.isoformat() if customer.contract_date else '',
        }
    }


def _ingest_service_media_uploads(request, service):
    """Servis formundan gelen medya dosyalarını kaydeder (görsel + belge)."""
    ingest_customer_media_uploads(
        request,
        customer=service.customer,
        service=service,
        scope=CustomerMedia.SCOPE_SERVICE,
    )


def _create_service_history(service, action, user=None):
    return ServiceHistory.objects.create(
        service=service,
        user=user if user and user.is_authenticated else None,
        action=action,
        snapshot=_build_service_snapshot(service),
    )


def _user_display(user_obj):
    if not user_obj:
        return '-'
    return user_obj.get_full_name() or user_obj.username


def _text_preview(value, max_len=80):
    text = (value or '').strip()
    if not text:
        return '-'
    if len(text) <= max_len:
        return text
    return f"{text[:max_len]}..."


def _capture_service_state(service):
    return {
        'customer': service.customer.name if service.customer_id else '-',
        'status': service.status.name if service.status_id else '-',
        'priority': service.priority.name if service.priority_id else '-',
        'warranty_status': service.get_warranty_status_display(),
        'solution_partner': service.solution_partner.name if service.solution_partner_id else '-',
        'service_personnel': service.service_personnel.name if service.service_personnel_id else '-',
        'assigned_to': _user_display(service.assigned_to),
        'list_price': str(service.list_price) if service.list_price is not None else '-',
        'discounted_price': str(service.discounted_price) if service.discounted_price is not None else '-',
        'notes': _text_preview(service.notes),
        'products': tuple(sorted(service.products.values_list('name', flat=True))),
        'service_types': tuple(sorted(service.service_types.values_list('name', flat=True))),
    }


def _diff_service_state(before_state, after_state):
    labels = {
        'customer': 'Müşteri',
        'status': 'Durum',
        'priority': 'Öncelik',
        'warranty_status': 'Garanti Durumu',
        'list_price': 'Normal Fiyat',
        'discounted_price': 'İndirimli Fiyat',
        'solution_partner': 'Çözüm Ortağı',
        'service_personnel': 'Servis Personeli',
        'assigned_to': 'Atanan Kullanıcı',
        'notes': 'Servis Notu',
        'products': 'Ürünler',
        'service_types': 'Servis Tipleri',
    }
    changes = []
    for key, label in labels.items():
        before_val = before_state.get(key)
        after_val = after_state.get(key)
        if before_val == after_val:
            continue
        if key in {'products', 'service_types'}:
            before_text = ', '.join(before_val) if before_val else '-'
            after_text = ', '.join(after_val) if after_val else '-'
        else:
            before_text = before_val or '-'
            after_text = after_val or '-'
        changes.append(f"{label}: {before_text} -> {after_text}")
    return changes


def _apply_service_status_change(
    service,
    *,
    new_status_id,
    prev_status_id,
    prev_status_name=None,
    user=None,
    send_whatsapp=False,
    template_ids=None,
):
    new_status = StatusOption.objects.filter(pk=new_status_id).first()
    if not new_status:
        raise ValueError('Geçersiz durum.')

    if int(service.status_id or 0) == int(new_status_id):
        return {'status_changed': False, 'whatsapp_results': []}

    before_state = _capture_service_state(service)
    service.status = new_status
    service.save(update_fields=['status', 'updated_at'])
    service.refresh_from_db()
    after_state = _capture_service_state(service)
    changes = _diff_service_state(before_state, after_state)
    _create_service_history(
        service,
        ' | '.join(changes) if changes else f'Durum: {new_status.name}',
        user,
    )

    whatsapp_results = []
    if send_whatsapp:
        whatsapp_results = dispatch_confirmed_status_whatsapp(
            service,
            prev_status_id=int(prev_status_id),
            prev_status_name=prev_status_name or None,
            template_ids=template_ids,
        )

    return {
        'status_changed': True,
        'status_label': new_status.name,
        'status_color': new_status.color_hex,
        'whatsapp_results': whatsapp_results,
    }


class ServiceListView(PermissionRequiredMixin, ListView):
    permission_required = 'access.services'
    model = ServiceRecord
    template_name = 'services_dashboard/services/service_list.html'
    context_object_name = 'services'
    ordering = ['-created_at']

    def get_queryset(self):
        ensure_default_statuses()
        queryset = super().get_queryset().select_related('status', 'priority', 'customer', 'solution_partner', 'service_personnel', 'service_personnel__team').prefetch_related('products', 'service_types')
        q = self.request.GET.get('q')
        status = self.request.GET.get('status')
        priority = self.request.GET.get('priority')
        product = self.request.GET.get('product')
        warranty = self.request.GET.get('warranty')
        team = self.request.GET.get('team')
        personnel = self.request.GET.get('personnel')
        region = (self.request.GET.get('region') or '').strip()

        if q:
            queryset = queryset.filter(
                Q(customer__name__icontains=q) |
                Q(customer__phone__icontains=q) |
                Q(customer__region__icontains=q) |
                Q(notes__icontains=q) |
                Q(products__name__icontains=q) |
                Q(service_types__name__icontains=q)
            )
        queryset = apply_service_list_visibility(queryset, self.request)
        if priority:
            queryset = queryset.filter(priority_id=priority)
        if product:
            queryset = queryset.filter(products__id=product)
        if team and team.isdigit():
            queryset = queryset.filter(service_personnel__team_id=int(team))
        if personnel and personnel.isdigit():
            queryset = queryset.filter(service_personnel_id=int(personnel))
        if region:
            queryset = queryset.filter(customer__region__iexact=region)
        
        if warranty == 'expired':
            queryset = queryset.filter(
                Q(warranty_status='expired') | Q(status__name__icontains='ücretli')
            )
        elif warranty == 'active':
            queryset = queryset.filter(warranty_status='active').exclude(status__name__icontains='ücretli')

        queryset = queryset.distinct()
        view_mode = (self.request.GET.get('view') or 'customer').strip().lower()
        if view_mode not in ('customer', 'record'):
            view_mode = 'customer'
        if view_mode == 'customer':
            groups = build_service_customer_groups(queryset)
            primary_ids = [g['primary'].pk for g in groups]
            if not primary_ids:
                return queryset.none()
            order_cases = [
                When(pk=pk, then=pos) for pos, pk in enumerate(primary_ids)
            ]
            queryset = queryset.filter(pk__in=primary_ids).annotate(
                _customer_view_order=Case(
                    *order_cases,
                    default=9999,
                    output_field=IntegerField(),
                )
            ).order_by('_customer_view_order')
            self._service_groups_meta = {
                g['primary'].pk: g for g in groups
            }
        else:
            self._service_groups_meta = {}
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from core_settings.models import ProductOption, StatusOption, PriorityOption, ServiceTypeOption
        from customers.models import Customer
        context['products'] = ProductOption.objects.all()
        context['statuses'] = StatusOption.objects.order_by('sort_order', 'name')
        context['priorities'] = PriorityOption.objects.all()
        context['service_types'] = ServiceTypeOption.objects.order_by('name')
        context['teams'] = ServiceTeam.objects.filter(is_active=True).order_by('name')
        context['personnel_list'] = ServicePersonnel.objects.filter(is_active=True).select_related('team').order_by('name')
        context['customer_regions'] = list(
            Customer.objects.exclude(Q(region__isnull=True) | Q(region=''))
            .values_list('region', flat=True)
            .distinct()
            .order_by('region')
        )
        context['show_hidden'] = self.request.GET.get('show_hidden') == '1'
        context['show_pending'] = self.request.GET.get('show_pending') == '1'
        context['visibility_active'] = not self.request.GET.get('status')
        context['whatsapp_prompt_queue'] = pop_whatsapp_status_prompt_queue(self.request)
        view_mode = (self.request.GET.get('view') or 'customer').strip().lower()
        if view_mode not in ('customer', 'record'):
            view_mode = 'customer'
        context['list_view_mode'] = view_mode
        meta = getattr(self, '_service_groups_meta', {})
        for service in context['services']:
            group = meta.get(service.pk)
            if group:
                service.group_other_count = group['other_count']
                service.group_open_count = group['open_count']
                service.group_has_multiple_open = group['has_multiple_open']
            else:
                service.group_other_count = 0
                service.group_open_count = 0
                service.group_has_multiple_open = False
        return context


@require_http_methods(['GET'])
@permission_required('access.services')
def customer_service_summary_api(request, customer_id):
    if not str(customer_id).isdigit():
        return JsonResponse({'ok': False, 'error': 'Geçersiz müşteri.'}, status=400)
    from customers.models import Customer

    if not Customer.objects.filter(pk=int(customer_id)).exists():
        return JsonResponse({'ok': False, 'error': 'Müşteri bulunamadı.'}, status=404)
    return JsonResponse(customer_services_payload(int(customer_id)))


@require_POST
@permission_required(SERVICES_MANAGE_PERM)
def service_reopen_api(request, pk):
    service = get_object_or_404(
        ServiceRecord.objects.select_related('status'),
        pk=pk,
    )
    if is_open_service(service):
        return JsonResponse({
            'ok': False,
            'error': 'Bu kayıt zaten açık durumda.',
            'edit_url': reverse('service_update', args=[service.pk]),
        }, status=400)

    active_status = get_active_status()
    if not active_status:
        return JsonResponse({'ok': False, 'error': 'Aktif durum tanımı bulunamadı.'}, status=500)

    prev_name = service.status.name
    service.status = active_status
    service.save(update_fields=['status', 'updated_at'])
    _create_service_history(
        service,
        f'Kayıt yeniden açıldı ({prev_name} → {active_status.name}).',
        request.user,
    )
    return JsonResponse({
        'ok': True,
        'message': f'Servis #{service.pk} yeniden aktif yapıldı.',
        'edit_url': reverse('service_update', args=[service.pk]),
    })


class ServiceCreateView(PermissionRequiredMixin, CreateView):
    permission_required = SERVICES_MANAGE_PERM
    model = ServiceRecord
    form_class = ServiceRecordForm
    template_name = 'services_dashboard/services/service_form.html'
    success_url = reverse_lazy('services')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(build_service_form_context())
        context['can_upload_media'] = True
        return context

    def get_initial(self):
        initial = super().get_initial()
        customer_id = self.request.GET.get('customer')
        if customer_id and str(customer_id).isdigit():
            initial['customer'] = int(customer_id)
        return initial

    def form_valid(self, form):
        with suppress_live_sync():
            response = super().form_valid(form)
        publish_live_event(
            kind='service',
            action='created',
            object_id=self.object.id,
            message=f'Servis #{self.object.id} oluşturuldu.',
            user_id=self.request.user.id,
        )
        _create_service_history(self.object, "Servis kaydı oluşturuldu.", self.request.user)
        _ingest_service_media_uploads(self.request, self.object)

        service = ServiceRecord.objects.select_related(
            'customer', 'status', 'priority',
        ).prefetch_related('service_types').get(pk=self.object.pk)
        prompt = build_whatsapp_service_created_prompt(service)
        queue_whatsapp_status_prompts(self.request, prompt)
        return response

class ServiceUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = SERVICES_MANAGE_PERM
    model = ServiceRecord
    form_class = ServiceRecordForm
    template_name = 'services_dashboard/services/service_form.html'
    success_url = reverse_lazy('services')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(build_service_form_context(self.object))
        context['can_upload_media'] = True
        return context

    def form_valid(self, form):
        prev_status_id = self.object.status_id if self.object.pk else None
        before_state = _capture_service_state(self.object)
        with suppress_live_sync():
            response = super().form_valid(form)
            self.object.refresh_from_db()
        after_state = _capture_service_state(self.object)
        changes = _diff_service_state(before_state, after_state)

        if changes:
            _create_service_history(self.object, " | ".join(changes), self.request.user)

        publish_live_event(
            kind='service',
            action='updated',
            object_id=self.object.id,
            message=f'Servis #{self.object.id} güncellendi.',
            user_id=self.request.user.id,
        )

        if prev_status_id and prev_status_id != self.object.status_id:
            service = ServiceRecord.objects.select_related(
                'customer', 'status', 'priority',
            ).prefetch_related('service_types').get(pk=self.object.pk)
            prompt = build_whatsapp_status_change_prompt(service, prev_status_id)
            queue_whatsapp_status_prompts(self.request, prompt)

        _ingest_service_media_uploads(self.request, self.object)
        return response

class ServiceDeleteView(PermissionRequiredMixin, DeleteView):
    permission_required = SERVICES_DELETE_PERM
    model = ServiceRecord
    success_url = reverse_lazy('services')

class ServicePrintView(PermissionRequiredMixin, DetailView):
    permission_required = SERVICES_PRINT_PERM
    model = ServiceRecord
    template_name = 'services_dashboard/services/service_print.html'
    context_object_name = 's'

class ServiceBulkPrintView(ServiceListView):
    permission_required = SERVICES_PRINT_PERM
    template_name = 'services_dashboard/services/service_bulk_print.html'
    context_object_name = 'services'
    paginate_by = None

    def _default_sort_key(self):
        settings = SiteSettings.objects.first()
        return (settings.bulk_print_default_sort if settings else None) or 'created_desc'

    def _resolve_sort_key(self):
        sort_key = self.request.GET.get('sort', self._default_sort_key())
        valid_keys = {choice[0] for choice in SiteSettings.BULK_PRINT_SORT_CHOICES}
        return sort_key if sort_key in valid_keys else self._default_sort_key()

    def get_queryset(self):
        queryset = super().get_queryset()
        sort_key = self._resolve_sort_key()

        sort_map = {
            'created_asc': ('created_at',),
            'created_desc': ('-created_at',),
            'customer': ('customer__name', '-created_at'),
            'product': None,
            'team': ('service_personnel__team__name', 'service_personnel__name', '-created_at'),
            'personnel': ('service_personnel__name', '-created_at'),
            'status': ('status__name', '-created_at'),
            'priority': ('priority__name', '-created_at'),
        }
        if sort_key == 'product':
            return queryset.annotate(first_product_name=Min('products__name')).order_by('first_product_name', '-created_at')
        return queryset.order_by(*sort_map.get(sort_key, ('-created_at',)))

    def _build_filter_summary(self):
        request = self.request
        parts = []
        label_map = {
            'q': 'Arama',
            'status': 'Durum',
            'priority': 'Öncelik',
            'product': 'Ürün',
            'warranty': 'Garanti',
            'team': 'Ekip',
            'personnel': 'Personel',
        }
        for key, label in label_map.items():
            value = request.GET.get(key)
            if not value:
                continue
            if key == 'status':
                obj = StatusOption.objects.filter(pk=value).first()
                parts.append(f'{label}: {obj.name if obj else value}')
            elif key == 'priority':
                obj = PriorityOption.objects.filter(pk=value).first()
                parts.append(f'{label}: {obj.name if obj else value}')
            elif key == 'product':
                from core_settings.models import ProductOption
                obj = ProductOption.objects.filter(pk=value).first()
                parts.append(f'{label}: {obj.name if obj else value}')
            elif key == 'team':
                obj = ServiceTeam.objects.filter(pk=value).first()
                parts.append(f'{label}: {obj.name if obj else value}')
            elif key == 'personnel':
                obj = ServicePersonnel.objects.filter(pk=value).first()
                parts.append(f'{label}: {obj.name if obj else value}')
            elif key == 'warranty':
                warranty_labels = {'active': 'Garantisi devam eden', 'expired': 'Garantisi biten'}
                parts.append(f'{label}: {warranty_labels.get(value, value)}')
            else:
                parts.append(f'{label}: {value}')
        return parts

    def get_context_data(self, **kwargs):
        from services.bulk_print_helpers import build_bulk_print_qr

        context = super().get_context_data(**kwargs)
        context['sort_options'] = SiteSettings.BULK_PRINT_SORT_CHOICES
        context['current_sort'] = self._resolve_sort_key()
        context['filter_summary'] = self._build_filter_summary()
        context['record_count'] = self.get_queryset().count()
        site_name = 'Gölgede Yaşam'
        if context.get('site_settings') and context['site_settings'].site_name:
            site_name = context['site_settings'].site_name
        for service in context['services']:
            service.bulk_qr = build_bulk_print_qr(service, site_name=site_name)
        return context

    def get(self, request, *args, **kwargs):
        dl = (request.GET.get('download') or '').lower()
        if dl == 'csv':
            return self._download_csv()
        if dl in ('xlsx', 'xls'):
            return self._download_xlsx()
        return super().get(request, *args, **kwargs)

    def _rows_for_export(self):
        for s in self.get_queryset():
            products = ', '.join(p.name for p in s.products.all()) or '-'
            service_types = ', '.join(st.name for st in s.service_types.all()) or '-'
            personnel = s.service_personnel.name if s.service_personnel_id else '-'
            team = s.service_personnel.team.name if s.service_personnel_id and s.service_personnel.team_id else '-'
            yield [
                s.id,
                s.customer.name,
                s.customer.phone or '-',
                s.customer.region or '-',
                products,
                service_types,
                s.status.name,
                s.priority.name,
                personnel,
                team,
                s.notes or '-',
                timezone.localtime(s.created_at).strftime('%d.%m.%Y %H:%M'),
            ]

    def _download_csv(self):
        ts = timezone.localtime().strftime('%Y%m%d-%H%M')
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="servis-raporu-{ts}.csv"'
        response.write('\ufeff')

        writer = csv.writer(response, delimiter=';')
        headers = [
            'ID', 'Müşteri', 'Telefon', 'Bölge', 'Ürünler', 'Arıza Tipleri',
            'Durum', 'Öncelik', 'Servis Personeli', 'Ekip', 'Notlar', 'Oluşturma Tarihi',
        ]
        writer.writerow(headers)
        for row in self._rows_for_export():
            writer.writerow(row)
        return response

    def _download_xlsx(self):
        from io import BytesIO

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = 'Servisler'

        headers = [
            'ID', 'Müşteri', 'Telefon', 'Bölge', 'Ürünler', 'Arıza Tipleri',
            'Durum', 'Öncelik', 'Servis Personeli', 'Ekip', 'Notlar', 'Oluşturma Tarihi',
        ]
        ws.append(headers)
        for row in self._rows_for_export():
            ws.append(row)

        ts = timezone.localtime().strftime('%Y%m%d-%H%M')
        bio = BytesIO()
        wb.save(bio)
        bio.seek(0)

        response = HttpResponse(
            bio.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="servis-raporu-{ts}.xlsx"'
        return response

@permission_required(SERVICES_DELETE_PERM)
def bulk_delete_services(request):
    if request.method == 'POST':
        ids = request.POST.getlist('ids')
        ServiceRecord.objects.filter(id__in=ids).delete()
    return redirect('services')


@require_POST
@permission_required(SERVICES_BULK_PERM)
def bulk_manage_services(request):
    ids = [int(x) for x in request.POST.getlist('ids') if str(x).isdigit()]
    action = (request.POST.get('bulk_action') or '').strip()
    queryset = ServiceRecord.objects.filter(id__in=ids)

    if not ids:
        messages.error(request, "Toplu işlem için en az bir servis seçin.")
        return redirect('services')
    if not action:
        messages.error(request, "Toplu işlem türü seçin.")
        return redirect('services')

    if action == 'delete':
        count = queryset.count()
        queryset.delete()
        messages.success(request, f"{count} servis kaydı silindi.")
        return redirect('services')

    if action == 'set_status':
        status_id = request.POST.get('bulk_status_id')
        if not status_id or not str(status_id).isdigit():
            messages.error(request, "Geçerli bir durum seçin.")
            return redirect('services')
        status = get_object_or_404(StatusOption, pk=int(status_id))
        updated = 0
        prompts = []
        for service in queryset:
            before_state = _capture_service_state(service)
            prev_status_id = service.status_id
            prev_status_name = service.status.name if service.status_id else None
            service.status = status
            service.save(update_fields=['status', 'updated_at'])
            service.refresh_from_db()
            after_state = _capture_service_state(service)
            changes = _diff_service_state(before_state, after_state)
            _create_service_history(
                service,
                ' | '.join(changes) if changes else f"Durum aynı kaldı: {status.name}",
                request.user,
            )
            updated += 1
            if prev_status_id != service.status_id:
                loaded = ServiceRecord.objects.select_related(
                    'customer', 'status', 'priority',
                ).prefetch_related('service_types').get(pk=service.pk)
                prompt = build_whatsapp_status_change_prompt(loaded, prev_status_id, prev_status_name)
                if prompt:
                    prompts.append(prompt)
        queue_whatsapp_status_prompts(request, prompts)
        messages.success(request, f"{updated} servis kaydının durumu güncellendi.")
        return redirect('services')

    if action == 'set_priority':
        priority_id = request.POST.get('bulk_priority_id')
        if not priority_id or not str(priority_id).isdigit():
            messages.error(request, "Geçerli bir öncelik seçin.")
            return redirect('services')
        priority = get_object_or_404(PriorityOption, pk=int(priority_id))
        updated = 0
        for service in queryset:
            before_state = _capture_service_state(service)
            service.priority = priority
            service.save(update_fields=['priority', 'updated_at'])
            service.refresh_from_db()
            after_state = _capture_service_state(service)
            changes = _diff_service_state(before_state, after_state)
            _create_service_history(
                service,
                ' | '.join(changes) if changes else f"Öncelik aynı kaldı: {priority.name}",
                request.user,
            )
            updated += 1
        messages.success(request, f"{updated} servis kaydının önceliği güncellendi.")
        return redirect('services')

    if action == 'set_personnel':
        personnel_value = (request.POST.get('bulk_personnel_id') or '').strip()
        personnel = None
        label = "Boş"
        if personnel_value and personnel_value != 'clear':
            if not personnel_value.isdigit():
                messages.error(request, "Geçerli bir personel seçin.")
                return redirect('services')
            personnel = get_object_or_404(ServicePersonnel, pk=int(personnel_value))
            label = personnel.name
        updated = 0
        for service in queryset:
            before_state = _capture_service_state(service)
            service.service_personnel = personnel
            service.save(update_fields=['service_personnel', 'updated_at'])
            service.refresh_from_db()
            after_state = _capture_service_state(service)
            changes = _diff_service_state(before_state, after_state)
            _create_service_history(
                service,
                ' | '.join(changes) if changes else f"Servis personeli aynı kaldı: {label}",
                request.user,
            )
            updated += 1
        messages.success(request, f"{updated} servis kaydının personel ataması güncellendi.")
        return redirect('services')

    messages.error(request, "Geçersiz toplu işlem.")
    return redirect('services')


@require_POST
@permission_required(SERVICES_MANAGE_PERM)
def quick_update_service_field(request):
    service_id = request.POST.get('service_id')
    field = request.POST.get('field')
    value = request.POST.get('value')

    if not service_id or not str(service_id).isdigit():
        return JsonResponse({'error': 'Geçersiz servis kaydı.'}, status=400)
    if field not in {'status', 'priority'}:
        return JsonResponse({'error': 'Geçersiz alan.'}, status=400)
    if not value or not str(value).isdigit():
        return JsonResponse({'error': 'Geçersiz değer.'}, status=400)

    service = get_object_or_404(ServiceRecord, pk=int(service_id))
    option_model = StatusOption if field == 'status' else PriorityOption
    option = get_object_or_404(option_model, pk=int(value))

    if field == 'status':
        if int(service.status_id or 0) == int(option.id):
            return JsonResponse({
                'ok': True,
                'field': field,
                'value': option.id,
                'label': option.name,
                'color': option.color_hex,
            })

        loaded = ServiceRecord.objects.select_related(
            'customer', 'status', 'priority',
        ).prefetch_related('service_types').get(pk=service.pk)
        preview = build_whatsapp_status_change_preview(
            loaded,
            prev_status_id=service.status_id,
            prev_status_name=service.status.name if service.status_id else None,
            new_status_id=option.id,
            new_status_name=option.name,
        )
        if preview:
            preview['deferred'] = True
            return JsonResponse({
                'ok': True,
                'deferred': True,
                'whatsapp_prompt': preview,
            })

    before_state = _capture_service_state(service)
    prev_status_id = service.status_id if field == 'status' else None
    prev_status_name = service.status.name if field == 'status' and service.status_id else None

    with suppress_live_sync():
        if field == 'status':
            service.status = option
        else:
            service.priority = option
        service.save(update_fields=[field, 'updated_at'])
    service.refresh_from_db()
    after_state = _capture_service_state(service)
    changes = _diff_service_state(before_state, after_state)

    _create_service_history(
        service,
        ' | '.join(changes) if changes else f"{field} aynı kaldı: {option.name}",
        request.user,
    )
    publish_live_event(
        kind='service',
        action='updated',
        object_id=service.id,
        message=f'Servis #{service.id} güncellendi.',
        user_id=request.user.id,
    )

    return JsonResponse({
        'ok': True,
        'field': field,
        'value': option.id,
        'label': option.name,
        'color': option.color_hex,
    })

def _restore_service_from_snapshot(service, snapshot):
    service_data = snapshot.get('service', {})
    customer_data = snapshot.get('customer', {})

    status_id = service_data.get('status_id')
    priority_id = service_data.get('priority_id')
    if status_id:
        service.status_id = status_id
    if priority_id:
        service.priority_id = priority_id

    service.solution_partner_id = service_data.get('solution_partner_id')
    service.assigned_to_id = service_data.get('assigned_to_id')
    service.service_personnel_id = service_data.get('service_personnel_id')
    service.warranty_status = service_data.get('warranty_status') or service.warranty_status
    if 'list_price' in service_data:
        service.list_price = service_data.get('list_price') or None
    if 'discounted_price' in service_data:
        service.discounted_price = service_data.get('discounted_price') or None
    service.notes = service_data.get('notes') or ''
    service.save()

    service.products.set(service_data.get('product_ids') or [])
    service.service_types.set(service_data.get('service_type_ids') or [])

    customer = service.customer
    customer.phone = customer_data.get('phone') or None
    customer.region = customer_data.get('region') or None
    customer.location_link = customer_data.get('location_link') or None
    customer.contract_date = customer_data.get('contract_date') or None
    customer.save(update_fields=['phone', 'region', 'location_link', 'contract_date', 'updated_at'])

@require_POST
@permission_required(SERVICES_MANAGE_PERM)
def restore_service_history_entry(request, pk, history_id):
    service = get_object_or_404(ServiceRecord, pk=pk)
    history_entry = get_object_or_404(ServiceHistory, pk=history_id, service=service)
    snapshot = history_entry.snapshot or {}
    if not snapshot:
        messages.error(request, "Bu geçmiş kaydında geri yükleme snapshot verisi yok.")
        return redirect('service_update', pk=service.id)

    before_state = _capture_service_state(service)
    _restore_service_from_snapshot(service, snapshot)
    service.refresh_from_db()
    after_state = _capture_service_state(service)
    changes = _diff_service_state(before_state, after_state)

    restore_action = f"İşlem geçmişinden geri yüklendi ({history_entry.created_at.strftime('%d.%m.%Y %H:%M')})"
    if changes:
        restore_action = f"{restore_action} | {' | '.join(changes)}"

    _create_service_history(
        service,
        restore_action,
        request.user,
    )
    messages.success(request, "Servis kaydı işlem geçmişinden geri yüklendi.")
    return redirect('service_update', pk=service.id)


@permission_required(SERVICES_WHATSAPP_PERM)
def send_services_whatsapp(request):
    team_id = request.GET.get('team')
    personnel_id = request.GET.get('personnel')
    qs = ServiceRecord.objects.select_related(
        'customer', 'status', 'priority', 'service_personnel', 'service_personnel__team'
    ).prefetch_related('products', 'service_types')

    if team_id and team_id.isdigit():
        qs = qs.filter(service_personnel__team_id=int(team_id))
    if personnel_id and personnel_id.isdigit():
        qs = qs.filter(service_personnel_id=int(personnel_id))

    target_phone = ''
    target_label = ''
    if personnel_id and personnel_id.isdigit():
        person = ServicePersonnel.objects.filter(pk=int(personnel_id), is_active=True).select_related('team').prefetch_related('product_groups').first()
        if person:
            target_phone = (person.company_phone or '').strip()
            target_label = person.name
            skill_product_ids = list(person.product_groups.values_list('id', flat=True))
            if not skill_product_ids:
                messages.error(request, "Bu personel için yetenekli ürün grubu tanımlı değil.")
                return redirect('services')
            qs = qs.filter(products__id__in=skill_product_ids)
    elif team_id and team_id.isdigit():
        team = ServiceTeam.objects.filter(pk=int(team_id), is_active=True).first()
        if team:
            target_phone = (team.company_phone or '').strip()
            target_label = team.name

    if not target_phone:
        messages.error(request, "WhatsApp için ekip/personel şirket numarası tanımlı değil.")
        return redirect('services')

    services = list(qs.distinct().order_by('-created_at')[:40])
    if not services:
        messages.error(request, "Seçilen ekip/personel ve yetenek ürün grupları için gönderilecek servis bulunamadı.")
        return redirect('services')

    message = _build_service_summary_message(target_label, services)
    clean_phone = _normalize_phone_for_wa(target_phone)

    team_label = target_label
    if personnel_id and personnel_id.isdigit():
        person = ServicePersonnel.objects.filter(pk=int(personnel_id)).select_related('team').first()
        team_label = person.team.name if person and person.team else 'Ekipsiz'

    card = {
        'recipient_type': 'personnel' if personnel_id else 'team',
        'recipient_label': target_label,
        'team_label': team_label,
        'count': len(services),
        'phone': clean_phone,
        'message': message,
        'services': [
            {
                'id': s.id,
                'customer_name': s.customer.name,
                'region': s.customer.region or '-',
            }
            for s in services
        ],
    }

    return render(
        request,
        'services_dashboard/services/whatsapp_dispatch.html',
        {
            'team_groups': [{
                'team_label': team_label,
                'total_count': len(services),
                'items': [card],
            }],
            'total_service_count': len(services),
            'total_receiver_count': 1,
        },
    )


@permission_required(SERVICES_WHATSAPP_PERM)
def send_services_whatsapp_auto(request):
    base_qs = ServiceRecord.objects.select_related(
        'customer', 'status', 'priority', 'service_personnel', 'service_personnel__team'
    ).prefetch_related('products', 'service_types')
    services = list(_apply_service_filters(base_qs, request).order_by('-created_at')[:120])
    if not services:
        messages.error(request, "Dağıtılacak servis kaydı bulunamadı.")
        return redirect('services')

    personnel_candidates = list(
        ServicePersonnel.objects.filter(is_active=True)
        .select_related('team')
        .prefetch_related('product_groups', 'team__product_groups')
        .order_by('name')
    )
    team_candidates = list(
        ServiceTeam.objects.filter(is_active=True)
        .prefetch_related('product_groups')
        .order_by('name')
    )

    assignments = {}

    def add_assignment(kind, pk, label, phone, team_label, service):
        key = (kind, pk)
        if key not in assignments:
            assignments[key] = {
                'kind': kind,
                'label': label,
                'phone': phone,
                'team_label': team_label or 'Ekipsiz',
                'services': [],
            }
        assignments[key]['services'].append(service)

    for service in services:
        service_product_ids = set(service.products.values_list('id', flat=True))
        assigned = False

        if service.service_personnel and service.service_personnel.is_active and service.service_personnel.company_phone:
            person = service.service_personnel
            add_assignment(
                'personnel',
                person.id,
                person.name,
                person.company_phone,
                person.team.name if person.team else 'Ekipsiz',
                service,
            )
            assigned = True
        if assigned:
            continue

        for person in personnel_candidates:
            skill_ids = set(person.product_groups.values_list('id', flat=True))
            if not skill_ids and person.team_id:
                skill_ids = set(person.team.product_groups.values_list('id', flat=True)) if person.team else set()
            if not skill_ids or not person.company_phone:
                continue
            if service_product_ids & skill_ids:
                add_assignment(
                    'personnel',
                    person.id,
                    person.name,
                    person.company_phone,
                    person.team.name if person.team else 'Ekipsiz',
                    service,
                )
                assigned = True
                break
        if assigned:
            continue

        for team in team_candidates:
            team_skill_ids = set(team.product_groups.values_list('id', flat=True))
            if not team_skill_ids or not team.company_phone:
                continue
            if service_product_ids & team_skill_ids:
                add_assignment('team', team.id, team.name, team.company_phone, team.name, service)
                assigned = True
                break

    assignment_cards = []
    for _, payload in assignments.items():
        if not payload['services']:
            continue
        phone = _normalize_phone_for_wa(payload['phone'])
        if not phone:
            continue
        ordered_services = sorted(payload['services'], key=lambda s: s.created_at, reverse=True)
        message = _build_service_summary_message(payload['label'], ordered_services)
        assignment_cards.append({
            'recipient_type': payload['kind'],
            'recipient_label': payload['label'],
            'team_label': payload['team_label'],
            'count': len(ordered_services),
            'phone': phone,
            'message': message,
            'services': [
                {
                    'id': s.id,
                    'customer_name': s.customer.name,
                    'region': s.customer.region or '-',
                }
                for s in ordered_services
            ],
        })

    if not assignment_cards:
        messages.error(request, "Uygun ekip/personel ve ürün eşleşmesi bulunamadı.")
        return redirect('services')

    grouped = {}
    for card in assignment_cards:
        key = card['team_label']
        if key not in grouped:
            grouped[key] = {'team_label': key, 'total_count': 0, 'items': []}
        grouped[key]['total_count'] += card['count']
        grouped[key]['items'].append(card)

    team_groups = sorted(grouped.values(), key=lambda g: g['team_label'].lower())
    for group in team_groups:
        group['items'].sort(
            key=lambda item: (0 if item['recipient_type'] == 'team' else 1, item['recipient_label'].lower())
        )

    return render(
        request,
        'services_dashboard/services/whatsapp_dispatch.html',
        {
            'team_groups': team_groups,
            'total_service_count': sum(group['total_count'] for group in team_groups),
            'total_receiver_count': sum(len(group['items']) for group in team_groups),
        },
    )


@require_POST
@permission_required(SERVICES_WHATSAPP_PERM)
def service_status_change_preview_api(request):
    import json
    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Geçersiz JSON.'}, status=400)

    service_id = body.get('service_id')
    new_status_id = body.get('new_status_id')
    if not service_id or not str(service_id).isdigit():
        return JsonResponse({'ok': False, 'error': 'Geçersiz servis kaydı.'}, status=400)
    if not new_status_id or not str(new_status_id).isdigit():
        return JsonResponse({'ok': False, 'error': 'Geçersiz durum.'}, status=400)

    service = get_object_or_404(
        ServiceRecord.objects.select_related('customer', 'status', 'priority').prefetch_related('service_types'),
        pk=int(service_id),
    )
    new_status = get_object_or_404(StatusOption, pk=int(new_status_id))

    if int(service.status_id or 0) == int(new_status_id):
        return JsonResponse({'ok': True, 'deferred': False, 'whatsapp_prompt': None})

    preview = build_whatsapp_status_change_preview(
        service,
        prev_status_id=service.status_id,
        prev_status_name=service.status.name if service.status_id else None,
        new_status_id=new_status.id,
        new_status_name=new_status.name,
    )
    if preview:
        preview['deferred'] = True
    return JsonResponse({
        'ok': True,
        'deferred': bool(preview),
        'whatsapp_prompt': preview,
    })


@require_POST
@permission_required(SERVICES_WHATSAPP_PERM)
def service_status_change_apply_api(request):
    import json
    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Geçersiz JSON.'}, status=400)

    service_id = body.get('service_id')
    new_status_id = body.get('new_status_id')
    if not service_id or not str(service_id).isdigit():
        return JsonResponse({'ok': False, 'error': 'Geçersiz servis kaydı.'}, status=400)
    if not new_status_id or not str(new_status_id).isdigit():
        return JsonResponse({'ok': False, 'error': 'Yeni durum bilgisi eksik.'}, status=400)

    prev_status_id = body.get('prev_status_id')
    if not prev_status_id or not str(prev_status_id).isdigit():
        return JsonResponse({'ok': False, 'error': 'Önceki durum bilgisi eksik.'}, status=400)

    service = get_object_or_404(
        ServiceRecord.objects.select_related('customer', 'status', 'priority').prefetch_related('service_types'),
        pk=int(service_id),
    )
    send_whatsapp = bool(body.get('send_whatsapp'))
    template_ids = body.get('template_ids')
    if template_ids is not None and not isinstance(template_ids, list):
        template_ids = [template_ids]

    try:
        result = _apply_service_status_change(
            service,
            new_status_id=int(new_status_id),
            prev_status_id=int(prev_status_id),
            prev_status_name=(body.get('prev_status_name') or '').strip() or None,
            user=request.user,
            send_whatsapp=send_whatsapp,
            template_ids=template_ids,
        )
    except ValueError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

    sent = sum(1 for r in result.get('whatsapp_results') or [] if r.get('ok'))
    return JsonResponse({
        'ok': True,
        'sent': sent,
        'status_label': result.get('status_label'),
        'status_color': result.get('status_color'),
        'results': result.get('whatsapp_results') or [],
    })


@require_POST
@permission_required(SERVICES_WHATSAPP_PERM)
def service_whatsapp_status_confirm_api(request):
    import json

    from core_settings.models import WhatsAppTemplate
    from customers.models import Customer
    from sales_leads.models import SalesLead

    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Geçersiz JSON.'}, status=400)

    prompt_type = (body.get('prompt_type') or 'status_change').strip()
    template_ids = body.get('template_ids')
    if template_ids is not None and not isinstance(template_ids, list):
        template_ids = [template_ids]

    if prompt_type == 'service_created':
        service_id = body.get('service_id')
        if not service_id or not str(service_id).isdigit():
            return JsonResponse({'ok': False, 'error': 'Geçersiz servis kaydı.'}, status=400)
        service = get_object_or_404(
            ServiceRecord.objects.select_related('customer', 'status', 'priority').prefetch_related('service_types'),
            pk=int(service_id),
        )
        from tools.whatsapp_scenarios import build_service_context
        from .whatsapp_status_prompt import _status_values as scenario_status_values

        to_values = scenario_status_values(
            service.status_id,
            service.status.name if service.status_id else None,
        )
        results = dispatch_confirmed_scenario(
            WhatsAppTemplate.SCENARIO_SERVICE_CREATED,
            phone_raw=service.customer.phone or '' if service.customer_id else '',
            context=build_service_context(service),
            customer_id=service.customer_id,
            template_ids=template_ids,
            event_to_values=to_values,
        )
    elif prompt_type == 'customer_created':
        customer_id = body.get('customer_id')
        if not customer_id or not str(customer_id).isdigit():
            return JsonResponse({'ok': False, 'error': 'Geçersiz müşteri.'}, status=400)
        customer = get_object_or_404(Customer, pk=int(customer_id))
        from tools.whatsapp_scenarios import build_customer_context

        results = dispatch_confirmed_scenario(
            WhatsAppTemplate.SCENARIO_CUSTOMER_CREATED,
            phone_raw=customer.phone or '',
            context=build_customer_context(customer),
            customer_id=customer.id,
            template_ids=template_ids,
        )
    elif prompt_type in ('sales_created', 'sales_status'):
        lead_id = body.get('sales_lead_id')
        if not lead_id or not str(lead_id).isdigit():
            return JsonResponse({'ok': False, 'error': 'Geçersiz satış kaydı.'}, status=400)
        lead = get_object_or_404(SalesLead.objects.select_related('customer'), pk=int(lead_id))
        from tools.whatsapp_scenarios import build_sales_lead_context

        if prompt_type == 'sales_created':
            results = dispatch_confirmed_scenario(
                WhatsAppTemplate.SCENARIO_SALES_LEAD_CREATED,
                phone_raw=lead.customer.phone or '' if lead.customer_id else '',
                context=build_sales_lead_context(lead),
                customer_id=lead.customer_id,
                template_ids=template_ids,
                event_to_values=[lead.status],
            )
        else:
            prev_status = (body.get('prev_status') or '').strip()
            if not prev_status:
                return JsonResponse({'ok': False, 'error': 'Önceki durum bilgisi eksik.'}, status=400)
            results = dispatch_confirmed_scenario(
                WhatsAppTemplate.SCENARIO_SALES_LEAD_STATUS,
                phone_raw=lead.customer.phone or '' if lead.customer_id else '',
                context=build_sales_lead_context(lead, old_status_code=prev_status),
                customer_id=lead.customer_id,
                template_ids=template_ids,
                event_from_values=[prev_status],
                event_to_values=[lead.status],
            )
    else:
        service_id = body.get('service_id')
        if not service_id or not str(service_id).isdigit():
            return JsonResponse({'ok': False, 'error': 'Geçersiz servis kaydı.'}, status=400)

        service = get_object_or_404(
            ServiceRecord.objects.select_related('customer', 'status', 'priority').prefetch_related('service_types'),
            pk=int(service_id),
        )
        prev_status_id = body.get('prev_status_id')
        if not prev_status_id or not str(prev_status_id).isdigit():
            return JsonResponse({'ok': False, 'error': 'Önceki durum bilgisi eksik.'}, status=400)

        results = dispatch_confirmed_status_whatsapp(
            service,
            prev_status_id=int(prev_status_id),
            prev_status_name=(body.get('prev_status_name') or '').strip() or None,
            template_ids=template_ids,
        )

    sent = sum(1 for r in results if r.get('ok'))
    failed = [r for r in results if not r.get('ok')]
    return JsonResponse({
        'ok': True,
        'sent': sent,
        'results': results,
        'error': failed[0]['error'] if len(failed) == 1 and sent == 0 else None,
    })
