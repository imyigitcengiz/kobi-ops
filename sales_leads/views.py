import csv
import json
from datetime import timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import ListView, TemplateView, View

from common.permissions import (
    SALES_DELETE_PERM,
    SALES_EXPORT_PERM,
    SALES_MANAGE_PERM,
    SALES_REPORTS_PERM,
)
from users.mixins import PermissionRequiredMixin

from core_settings.models import ProductOption
from customers.models import Customer

from services.whatsapp_status_prompt import (
    build_whatsapp_sales_created_prompt,
    build_whatsapp_sales_status_prompt,
    pop_whatsapp_status_prompt_queue,
    queue_whatsapp_status_prompts,
)

from .forms import SalesLeadForm
from .models import SalesLead


def _completed_leads():
    return SalesLead.objects.filter(status=SalesLead.STATUS_COMPLETED)


def _lead_queryset():
    return (
        SalesLead.objects.select_related('customer', 'assigned_to')
        .prefetch_related(
            'products',
            'interim_payments',
            'product_lines__product',
            'product_lines__color',
            'customer__products',
            'customer__service_records',
        )
    )


def _products_catalog():
    products = ProductOption.objects.prefetch_related('color_options').order_by('name')
    return [
        {
            'id': p.id,
            'name': p.name,
            'color': p.color_hex,
            'colors': [
                {'id': c.id, 'name': c.name, 'color': c.color_hex}
                for c in p.color_options.all()
            ],
        }
        for p in products
    ]


class SalesLeadDashboardView(PermissionRequiredMixin, TemplateView):
    permission_required = 'access.accounting'
    template_name = 'sales_lead/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        month_start = today.replace(day=1)
        completed = _completed_leads()

        context['total_sales'] = completed.count()
        context['month_sales'] = completed.filter(sale_date__gte=month_start).count()
        context['month_amount'] = completed.filter(sale_date__gte=month_start).aggregate(
            total=Sum('sale_amount')
        )['total'] or Decimal('0')
        context['total_amount'] = completed.aggregate(total=Sum('sale_amount'))['total'] or Decimal('0')
        context['total_customers'] = Customer.objects.count()
        context['pending_sales'] = SalesLead.objects.filter(status=SalesLead.STATUS_PENDING).count()

        days = [today - timedelta(days=i) for i in range(29, -1, -1)]
        context['trend_labels'] = json.dumps([d.strftime('%d.%m') for d in days], ensure_ascii=False)
        context['trend_counts'] = json.dumps([
            completed.filter(sale_date=d).count() for d in days
        ])

        product_stats = (
            completed.filter(customer__products__isnull=False)
            .values('customer__products__name')
            .annotate(total=Count('id', distinct=True))
            .order_by('-total')[:8]
        )
        context['product_labels'] = json.dumps([p['customer__products__name'] or '—' for p in product_stats], ensure_ascii=False)
        context['product_counts'] = json.dumps([p['total'] for p in product_stats])

        rep_stats = (
            completed.filter(assigned_to__isnull=False)
            .values('assigned_to__username', 'assigned_to__first_name', 'assigned_to__last_name')
            .annotate(total=Count('id'), amount=Sum('sale_amount'))
            .order_by('-total')[:6]
        )
        context['rep_stats'] = rep_stats
        context['recent_sales'] = _lead_queryset()[:8]
        return context


class SalesLeadListView(PermissionRequiredMixin, ListView):
    permission_required = 'access.accounting'
    model = SalesLead
    template_name = 'sales_lead/sales_lead_list.html'
    context_object_name = 'sales_leads'
    paginate_by = 25

    def get_queryset(self):
        queryset = _lead_queryset()
        q = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '').strip()
        product = self.request.GET.get('product', '').strip()

        if q:
            queryset = queryset.filter(
                Q(customer__name__icontains=q)
                | Q(customer__phone__icontains=q)
                | Q(customer__region__icontains=q)
                | Q(project__icontains=q)
                | Q(notes__icontains=q)
            )
        if status:
            queryset = queryset.filter(status=status)
        if product and product.isdigit():
            queryset = queryset.filter(
                Q(product_lines__product_id=int(product)) | Q(products__id=int(product))
            ).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = ProductOption.objects.order_by('name')
        context['status_choices'] = SalesLead.STATUS_CHOICES
        context['whatsapp_prompt_queue'] = pop_whatsapp_status_prompt_queue(self.request)
        return context


class SalesLeadCreateView(PermissionRequiredMixin, View):
    permission_required = SALES_MANAGE_PERM
    template_name = 'sales_lead/sales_lead_form.html'

    def get(self, request):
        customer = None
        customer_id = request.GET.get('customer')
        if customer_id and str(customer_id).isdigit():
            customer = Customer.objects.filter(pk=int(customer_id)).first()
        initial = {'sale_date': timezone.localdate(), 'status': SalesLead.STATUS_COMPLETED}
        if customer:
            initial['use_existing_customer'] = True
            initial['existing_customer'] = customer.pk
        form = SalesLeadForm(initial=initial, add_project_for_customer=customer)
        return self._render(request, form, customer=customer)

    def post(self, request):
        customer = None
        customer_id = request.POST.get('existing_customer') or request.GET.get('customer')
        if customer_id and str(customer_id).isdigit():
            customer = Customer.objects.filter(pk=int(customer_id)).first()
        form = SalesLeadForm(request.POST, add_project_for_customer=customer)
        if form.is_valid():
            lead = form.save()
            prompt = build_whatsapp_sales_created_prompt(lead)
            queue_whatsapp_status_prompts(request, prompt)
            messages.success(request, f'Proje kaydı oluşturuldu: {lead.customer.name} — {lead.project}')
            return redirect('sales_lead_list')
        return self._render(request, form, customer=customer)

    def _render(self, request, form, customer=None):
        from django.shortcuts import render
        customer_projects = []
        if customer:
            customer_projects = _lead_queryset().filter(customer=customer).order_by('-sale_date')
        elif form.instance:
            customer_projects = _lead_queryset().filter(customer=form.instance.customer).exclude(pk=form.instance.pk).order_by('-sale_date')
        return render(request, self.template_name, {
            'form': form,
            'is_edit': False,
            'add_project_mode': customer is not None,
            'customer_projects': customer_projects,
            'selected_customer': customer,
            'sales_lead_form_js': {
                'products': _products_catalog(),
                'interimPayments': form.interim_payments_initial,
                'productLines': form.product_lines_initial,
            },
        })


class SalesLeadUpdateView(PermissionRequiredMixin, View):
    permission_required = SALES_MANAGE_PERM
    template_name = 'sales_lead/sales_lead_form.html'

    def get(self, request, pk):
        lead = get_object_or_404(SalesLead, pk=pk)
        form = SalesLeadForm(instance=lead)
        return self._render(request, form, lead)

    def post(self, request, pk):
        lead = get_object_or_404(SalesLead, pk=pk)
        prev_status = lead.status
        form = SalesLeadForm(request.POST, instance=lead)
        if form.is_valid():
            lead = form.save()
            if prev_status != lead.status:
                prompt = build_whatsapp_sales_status_prompt(lead, prev_status)
                queue_whatsapp_status_prompts(request, prompt)
            messages.success(request, f'Satış kaydı güncellendi: {lead.customer.name}')
            return redirect('sales_lead_list')
        return self._render(request, form, lead)

    def _render(self, request, form, lead):
        from django.shortcuts import render
        customer_projects = (
            _lead_queryset()
            .filter(customer=lead.customer)
            .exclude(pk=lead.pk)
            .order_by('-sale_date')
        )
        return render(request, self.template_name, {
            'form': form,
            'is_edit': True,
            'lead': lead,
            'customer_projects': customer_projects,
            'selected_customer': lead.customer,
            'sales_lead_form_js': {
                'products': _products_catalog(),
                'interimPayments': form.interim_payments_initial,
                'productLines': form.product_lines_initial,
            },
        })


class SalesLeadDeleteView(PermissionRequiredMixin, View):
    permission_required = SALES_DELETE_PERM
    def post(self, request, pk):
        lead = get_object_or_404(SalesLead, pk=pk)
        name = lead.customer.name
        lead.delete()
        messages.success(request, f'Satış kaydı silindi: {name}')
        return redirect('sales_lead_list')


class SalesLeadReportsView(PermissionRequiredMixin, TemplateView):
    permission_required = SALES_REPORTS_PERM
    template_name = 'sales_lead/reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        completed = _completed_leads()
        today = timezone.localdate()

        monthly = []
        month_cursor = today.replace(day=1)
        for i in range(5, -1, -1):
            month = month_cursor - relativedelta(months=i)
            next_month = month + relativedelta(months=1)
            qs = completed.filter(sale_date__gte=month, sale_date__lt=next_month)
            monthly.append({
                'label': month.strftime('%m.%Y'),
                'count': qs.count(),
                'amount': qs.aggregate(total=Sum('sale_amount'))['total'] or Decimal('0'),
            })
        context['monthly_stats'] = monthly

        context['region_stats'] = (
            completed.exclude(customer__region__isnull=True)
            .exclude(customer__region='')
            .values('customer__region')
            .annotate(total=Count('id'), amount=Sum('sale_amount'))
            .order_by('-total')[:10]
        )
        context['status_breakdown'] = (
            SalesLead.objects.values('status')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        report_leads = list(_lead_queryset().order_by('-sale_date', '-created_at'))
        max_interim = max((lead.interim_payments.count() for lead in report_leads), default=0)
        col_count = max(max_interim, 1)
        for lead in report_leads:
            payments = list(lead.interim_payments.all())
            lead.report_interim_cells = [
                payments[i].amount if i < len(payments) else None
                for i in range(col_count)
            ]
        context['report_leads'] = report_leads
        context['max_interim_count'] = max_interim
        context['interim_column_count'] = col_count
        context['interim_column_indices'] = list(range(col_count))
        return context


class SalesLeadExportCsvView(PermissionRequiredMixin, View):
    permission_required = SALES_EXPORT_PERM
    def get(self, request):
        leads = list(_lead_queryset())
        status = request.GET.get('status', '').strip()
        if status:
            leads = [l for l in leads if l.status == status]

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        report_mode = request.GET.get('format') == 'report'
        filename = 'satis-raporu.csv' if report_mode else 'satis-kayitlari.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write('\ufeff')
        writer = csv.writer(response, delimiter=';')

        max_interim = max((lead.interim_payments.count() for lead in leads), default=0)
        if report_mode:
            header = [
                'AD SOYAD', 'TELEFON', 'YER', 'PROJE', 'TARİH',
                'TOPLAM', 'PEŞİNAT',
            ]
            for i in range(1, max(max_interim, 1) + 1):
                header.append(f'ARA ÖDEME {i}' if max_interim > 1 else 'ARA ÖDEME')
            header.extend(['KALAN', 'NOT', 'ÜRÜNLER'])
            writer.writerow(header)
        else:
            writer.writerow([
                'AD SOYAD', 'TELEFON', 'YER', 'PROJE', 'TARİH',
                'TOPLAM', 'PEŞİNAT', 'ARA ÖDEME', 'KALAN', 'NOT', 'ÜRÜNLER',
            ])

        for lead in leads:
            payments = list(lead.interim_payments.all())
            product_desc = '; '.join(
                f'{line.product.name}×{line.quantity}'
                + (f' ({line.color.name})' if line.color else '')
                + (f' — {line.note}' if line.note else '')
                for line in lead.product_lines.all()
            ) or '-'

            row = [
                lead.customer.name,
                lead.customer.phone or '-',
                lead.customer.region or '-',
                lead.project_display,
                lead.sale_date.strftime('%d.%m.%Y'),
                lead.sale_amount if lead.sale_amount is not None else '-',
                lead.down_payment if lead.down_payment is not None else '-',
            ]
            if report_mode:
                for i in range(max(max_interim, 1)):
                    if i < len(payments):
                        row.append(payments[i].amount)
                    else:
                        row.append('-')
            else:
                row.append(lead.interim_payments_total or '-')
            row.extend([
                lead.remaining_balance,
                lead.notes or '-',
                product_desc,
            ])
            writer.writerow(row)
        return response
