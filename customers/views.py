from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404
from django.db.models import Count, Max, Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from common.decorators import permission_required
from common.permissions import (
    CUSTOMERS_DELETE_PERM,
    CUSTOMERS_EDIT_PERM,
    CUSTOMERS_VIEW_PERM,
)
from core_settings.models import ProductOption
from users.mixins import PermissionRequiredMixin

from services.whatsapp_status_prompt import (
    build_whatsapp_customer_created_prompt,
    pop_whatsapp_status_prompt_queue,
    queue_whatsapp_status_prompts,
)

from .models import Customer
from .forms import CustomerForm
from .return_url import get_safe_return_url


class CustomerListView(PermissionRequiredMixin, ListView):
    permission_required = (CUSTOMERS_VIEW_PERM, CUSTOMERS_EDIT_PERM)
    permission_any = True
    model = Customer
    template_name = 'crm/customers/customer_list.html'
    context_object_name = 'customers'
    ordering = []

    def get_queryset(self):
        queryset = (
            Customer.objects.prefetch_related('products', 'sales_leads')
            .annotate(
                sales_count=Count('sales_leads', distinct=True),
                last_sale_date=Max('sales_leads__sale_date'),
                service_count=Count('service_records', distinct=True),
            )
            .order_by('-last_sale_date', 'name')
        )
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q)
                | Q(phone__icontains=q)
                | Q(region__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = ProductOption.objects.order_by('name')
        context['whatsapp_prompt_queue'] = pop_whatsapp_status_prompt_queue(self.request)
        return context


class CustomerCreateView(PermissionRequiredMixin, CreateView):
    permission_required = CUSTOMERS_EDIT_PERM
    model = Customer
    form_class = CustomerForm
    template_name = 'crm/customers/customer_form.html'
    success_url = reverse_lazy('customers')

    def form_valid(self, form):
        response = super().form_valid(form)
        prompt = build_whatsapp_customer_created_prompt(self.object)
        queue_whatsapp_status_prompts(self.request, prompt)
        return response


class CustomerUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = CUSTOMERS_EDIT_PERM
    model = Customer
    form_class = CustomerForm
    template_name = 'crm/customers/customer_form.html'
    success_url = reverse_lazy('customers')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['can_upload_media'] = True
        context['return_url'] = get_safe_return_url(self.request)
        context['focus_products'] = (
            self.request.GET.get('focus') == 'products' or self.request.GET.get('focus') == 'urunler'
        )
        return context

    def get_success_url(self):
        return get_safe_return_url(self.request) or str(reverse_lazy('customers'))

    def form_valid(self, form):
        response = super().form_valid(form)
        from customers.media_utils import ingest_customer_media_uploads
        from customers.models import CustomerMedia

        ingest_customer_media_uploads(
            self.request,
            customer=self.object,
            scope=(self.request.POST.get('media_scope') or CustomerMedia.SCOPE_CUSTOMER),
            field_names=('customer_media', 'media_files'),
        )
        return response


class CustomerDeleteView(PermissionRequiredMixin, DeleteView):
    permission_required = CUSTOMERS_DELETE_PERM
    model = Customer
    success_url = reverse_lazy('customers')


@permission_required(CUSTOMERS_DELETE_PERM)
def bulk_delete_customers(request):
    if request.method == 'POST':
        ids = request.POST.getlist('ids')
        Customer.objects.filter(id__in=ids).delete()
    return redirect('customers')


@require_http_methods(["POST"])
@permission_required(CUSTOMERS_EDIT_PERM)
def bulk_manage_customers(request):
    ids = [int(x) for x in request.POST.getlist('ids') if str(x).isdigit()]
    action = (request.POST.get('bulk_action') or '').strip()
    queryset = Customer.objects.filter(id__in=ids)

    if not ids:
        return JsonResponse({'ok': False, 'error': 'Toplu işlem için müşteri seçin.'}, status=400)
    if not action:
        return JsonResponse({'ok': False, 'error': 'Toplu işlem türü seçin.'}, status=400)

    if action == 'delete':
        count = queryset.count()
        queryset.delete()
        return JsonResponse({'ok': True, 'message': f'{count} müşteri silindi.'})

    if action == 'set_region':
        region = request.POST.get('bulk_region', '').strip()
        queryset.update(region=region or None)
        return JsonResponse({'ok': True, 'message': f'{queryset.count()} müşterinin bölgesi güncellendi.'})

    if action == 'set_contract_date':
        contract_date = request.POST.get('bulk_contract_date', '').strip()
        queryset.update(contract_date=contract_date or None)
        return JsonResponse({'ok': True, 'message': f'{queryset.count()} müşterinin sözleşme tarihi güncellendi.'})

    if action == 'add_product':
        product_id = request.POST.get('bulk_product_id')
        if not product_id or not str(product_id).isdigit():
            return JsonResponse({'ok': False, 'error': 'Ürün seçin.'}, status=400)
        product = get_object_or_404(ProductOption, pk=int(product_id))
        for customer in queryset:
            customer.products.add(product)
        return JsonResponse({'ok': True, 'message': f'{queryset.count()} müşteriye {product.name} eklendi.'})

    if action == 'remove_product':
        product_id = request.POST.get('bulk_product_id')
        if not product_id or not str(product_id).isdigit():
            return JsonResponse({'ok': False, 'error': 'Ürün seçin.'}, status=400)
        product = get_object_or_404(ProductOption, pk=int(product_id))
        for customer in queryset:
            customer.products.remove(product)
        return JsonResponse({'ok': True, 'message': f'{queryset.count()} müşteriden {product.name} kaldırıldı.'})

    return JsonResponse({'ok': False, 'error': 'Geçersiz toplu işlem.'}, status=400)


@permission_required(CUSTOMERS_EDIT_PERM)
def quick_customer_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        region = request.POST.get('region')
        location_link = request.POST.get('location_link')
        contract_date = request.POST.get('contract_date')
        if name:
            customer = Customer.objects.create(
                name=name, phone=phone, region=region,
                location_link=location_link, contract_date=contract_date or None
            )
            return JsonResponse({'id': customer.id, 'name': customer.name})
    return JsonResponse({'error': 'Geçersiz veri'}, status=400)


@permission_required(CUSTOMERS_VIEW_PERM, CUSTOMERS_EDIT_PERM, any_perm=True)
def customer_detail_api(request, pk):
    try:
        c = Customer.objects.prefetch_related('products').get(pk=pk)
        customer_products = list(c.products.order_by('name'))
        return JsonResponse({
            'name': c.name,
            'phone': c.phone or '-',
            'whatsapp_link': c.whatsapp_link or '',
            'region': c.region or '-',
            'address': c.address or '-',
            'location_link': c.location_link or '',
            'contract_date': c.contract_date.strftime('%d.%m.%Y') if c.contract_date else '-',
            'contract_age': f"({c.contract_age} önce)" if c.contract_age else '',
            'product_ids': [p.id for p in customer_products],
            'product_names': [p.name for p in customer_products],
            'products': [
                {'id': p.id, 'name': p.name, 'color': p.color_hex}
                for p in customer_products
            ],
        })
    except Customer.DoesNotExist:
        return JsonResponse({'error': 'Müşteri bulunamadı'}, status=404)


@require_http_methods(["POST"])
@permission_required(CUSTOMERS_EDIT_PERM)
def update_customer_products(request, pk):
    import json
    data = json.loads(request.body)
    product_ids = data.get('product_ids', [])
    c = Customer.objects.get(pk=pk)
    c.products.set(product_ids)
    return JsonResponse({'status': 'ok'})


@require_http_methods(["GET", "POST"])
def customer_quick_edit_api(request, pk):
    user = request.user
    if request.method == 'GET':
        if not user.is_superuser and not user.has_any_perm_codename(
            CUSTOMERS_VIEW_PERM, CUSTOMERS_EDIT_PERM
        ):
            return JsonResponse({'ok': False, 'error': 'Yetkiniz yok.'}, status=403)
    else:
        if not user.is_superuser and not user.has_perm_codename(CUSTOMERS_EDIT_PERM):
            return JsonResponse({'ok': False, 'error': 'Yetkiniz yok.'}, status=403)

    customer = get_object_or_404(Customer.objects.prefetch_related('products'), pk=pk)
    if request.method == 'GET':
        return JsonResponse({
            'ok': True,
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone or '',
                'region': customer.region or '',
                'address': customer.address or '',
                'location_link': customer.location_link or '',
                'contract_date': customer.contract_date.isoformat() if customer.contract_date else '',
                'product_ids': list(customer.products.values_list('id', flat=True)),
            }
        })

    name = request.POST.get('name', '').strip()
    if not name:
        return JsonResponse({'ok': False, 'error': 'Müşteri adı zorunlu.'}, status=400)

    customer.name = name
    customer.phone = request.POST.get('phone', '').strip() or None
    customer.region = request.POST.get('region', '').strip() or None
    customer.address = request.POST.get('address', '').strip() or None
    customer.location_link = request.POST.get('location_link', '').strip() or None
    customer.contract_date = request.POST.get('contract_date', '').strip() or None
    customer.save(update_fields=['name', 'phone', 'region', 'address', 'location_link', 'contract_date', 'updated_at'])

    product_ids = [int(x) for x in request.POST.getlist('product_ids') if str(x).isdigit()]
    customer.products.set(product_ids)

    return JsonResponse({'ok': True})


@require_http_methods(['GET'])
@permission_required(CUSTOMERS_VIEW_PERM, CUSTOMERS_EDIT_PERM, any_perm=True)
def customer_whatsapp_messages_api(request, pk):
    from tools.models import WhatsappOutboundMessage

    customer = get_object_or_404(Customer, pk=pk)
    status = (request.GET.get('status') or 'all').strip()
    page = max(int(request.GET.get('page') or 1), 1)
    page_size = min(max(int(request.GET.get('page_size') or 50), 1), 200)

    phone_keys = _customer_phone_keys(customer)
    qs_filter = Q(customer_id=customer.pk)
    if phone_keys:
        qs_filter |= Q(send_type=WhatsappOutboundMessage.SEND_CUSTOMER, phone_normalized__in=phone_keys)
    else:
        qs_filter |= Q(send_type=WhatsappOutboundMessage.SEND_CUSTOMER)
    qs = WhatsappOutboundMessage.objects.filter(qs_filter).order_by('-sent_at', '-created_at')
    if status and status != 'all':
        qs = qs.filter(status=status)

    total = qs.count()
    start = (page - 1) * page_size
    items = []
    for m in qs[start : start + page_size]:
        items.append({
            'id': m.id,
            'recipient_name': m.recipient_name or customer.name,
            'phone': m.phone_display or m.phone_normalized,
            'message': m.message,
            'status': m.status,
            'status_label': m.get_status_display(),
            'send_type_label': m.get_send_type_display() if m.send_type else 'Müşteri',
            'error_message': m.error_message,
            'sent_at': m.sent_at.isoformat() if m.sent_at else None,
            'created_at': m.created_at.isoformat(),
        })
    return JsonResponse({
        'ok': True,
        'customer': {'id': customer.id, 'name': customer.name},
        'total': total,
        'page': page,
        'page_size': page_size,
        'results': items,
    })


def _customer_phone_keys(customer: Customer) -> list[str]:
    from tools.phone_utils import normalize_phone

    keys = []
    norm = normalize_phone(customer.phone or '')
    if norm and norm != '-':
        keys.append(norm)
        digits = ''.join(ch for ch in norm if ch.isdigit())
        if len(digits) >= 10:
            keys.append(digits[-10:])
    return keys


@require_http_methods(['GET'])
@permission_required(CUSTOMERS_VIEW_PERM, CUSTOMERS_EDIT_PERM, any_perm=True)
def customers_picker_api(request):
    q = (request.GET.get('q') or '').strip()
    include_all = request.GET.get('all') in ('1', 'true', 'yes')
    qs = Customer.objects.prefetch_related('products').order_by('name')
    if not include_all:
        qs = qs.exclude(phone__isnull=True).exclude(phone='')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(region__icontains=q))
    results = []
    for c in qs[:200]:
        phone = (c.phone or '').strip()
        if not include_all and not phone:
            continue
        results.append({
            'id': c.id,
            'name': c.name,
            'phone': phone or '-',
            'region': c.region or '',
            'whatsapp_eligible': bool(phone),
            'product_names': [p.name for p in c.products.all()],
            'contract_date': c.contract_date.strftime('%d.%m.%Y') if c.contract_date else '',
        })
    return JsonResponse({'ok': True, 'results': results, 'count': len(results)})
