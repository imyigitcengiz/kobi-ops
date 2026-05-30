"""Kapsamlı smoke test — python scripts/smoke_test.py"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django

django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from core_settings.models import ProductOption, ProductColorOption, StatusOption, PriorityOption
from customers.models import Customer
from sales_leads.models import SalesLead

User = get_user_model()
admin = User.objects.filter(is_superuser=True).first() or User.objects.filter(username='admin').first()
client = Client()
client.force_login(admin)
errors = []


def test(label, fn):
    try:
        fn()
    except Exception as exc:
        errors.append(f'{label}: {exc}')
        errors.append(traceback.format_exc()[-800:])


def hit_get(path):
    r = client.get(path)
    if r.status_code >= 500:
        raise RuntimeError(f'GET {path} -> {r.status_code}\n{r.content.decode()[:600]}')
    if r.status_code not in (200, 302):
        raise RuntimeError(f'GET {path} -> {r.status_code}')


def hit_post(path, data):
    r = client.post(path, data)
    if r.status_code >= 500:
        raise RuntimeError(f'POST {path} -> {r.status_code}\n{r.content.decode()[:800]}')
    return r


# Sayfalar
for path in [
    '/',
    '/services-dashboard/services/',
    '/services-dashboard/services/new/',
    '/contact/musteriler/',
    '/muhasebe/satis/kayitlar/',
    '/muhasebe/satis/yeni/',
    '/tools/',
]:
    test(f'page {path}', lambda p=path: hit_get(p))

customer = Customer.objects.first()
status = StatusOption.objects.first()
priority = PriorityOption.objects.first()
product = ProductOption.objects.first()

# Servis oluştur (tam alanlar)
if customer and status and priority:
    def create_service():
        r = hit_post('/services-dashboard/services/new/', {
            'customer': str(customer.pk),
            'status': str(status.pk),
            'priority': str(priority.pk),
            'warranty_status': 'active',
            'notes': 'smoke',
        })
        if r.status_code == 302:
            loc = r.get('Location', '')
            if 'new' in loc:
                raise RuntimeError(f'service validation failed redirect {loc}')
        elif r.status_code == 200 and b'errorlist' in r.content:
            raise RuntimeError('service form validation errors')
    test('service create full', create_service)

# Satış — yeni müşteri
def sales_new_customer():
    r = hit_post('/muhasebe/satis/yeni/', {
        'name': 'Smoke Test Müşteri',
        'phone': '+905559998877',
        'region': 'İzmir',
        'project': 'Smoke Proje 1',
        'sale_date': timezone.localdate().isoformat(),
        'status': 'completed',
        'sale_amount': '10000',
        'down_payment': '2000',
        'interim_payment_amount': ['3000', '1000'],
        'product_line_product': [str(product.pk)] if product else [],
        'product_line_quantity': ['2'],
        'product_line_color': [''],
        'product_line_note': ['test not'],
    })
    if r.status_code not in (200, 302):
        raise RuntimeError(f'sales new -> {r.status_code}')
    if r.status_code == 200 and b'errorlist' in r.content:
        raise RuntimeError('sales form validation errors on new customer')
test('sales new customer + products', sales_new_customer)

# Satış — mevcut müşteri
if customer:
    def sales_existing():
        r = hit_post('/muhasebe/satis/yeni/', {
            'use_existing_customer': 'on',
            'existing_customer': str(customer.pk),
            'name': customer.name,
            'project': 'Smoke Proje Mevcut',
            'sale_date': timezone.localdate().isoformat(),
            'status': 'completed',
        })
        if r.status_code == 200 and b'errorlist' in r.content:
            raise RuntimeError('sales existing customer validation failed')
    test('sales existing customer', sales_existing)

# WhatsApp onay API
if customer and status:
    from services.models import ServiceRecord
    svc = ServiceRecord.objects.select_related('customer', 'status').prefetch_related('service_types').order_by('-id').first()
    if svc:
        def wa_confirm():
            import json
            r = client.post(
                '/services-dashboard/services/whatsapp/durum-onay/',
                data=json.dumps({
                    'prompt_type': 'service_created',
                    'service_id': svc.id,
                    'template_ids': [],
                }),
                content_type='application/json',
            )
            if r.status_code >= 500:
                raise RuntimeError(f'wa confirm {r.status_code} {r.content.decode()[:300]}')
            data = r.json()
            if not data.get('ok'):
                raise RuntimeError(f'wa confirm not ok: {data}')
        test('whatsapp confirm api', wa_confirm)

# Ürün rengi + satır
if product:
    color = ProductColorOption.objects.filter(product=product).first()
    if color:
        lead = SalesLead.objects.order_by('-id').first()
        if lead:
            def color_line():
                from sales_leads.models import SalesLeadProductLine
                SalesLeadProductLine.objects.create(
                    sales_lead=lead,
                    product=product,
                    quantity=1,
                    color=color,
                    note='renk test',
                )
            test('product line with color', color_line)

if errors:
    print('FAILURES:')
    for e in errors:
        print(e)
        print('---')
    sys.exit(1)
print('OK — extended smoke test passed')
