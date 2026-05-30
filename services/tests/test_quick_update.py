"""Servis hızlı güncelleme regresyon testleri."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from core_settings.models import PriorityOption, StatusOption
from customers.models import Customer
from services.models import ServiceRecord
from users.models import Permission, Role

User = get_user_model()


class QuickUpdateServiceFieldTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.role = Role.objects.create(slug='svc-manage', name='Svc Manage', is_system=False)
        perm, _ = Permission.objects.get_or_create(
            codename='services.manage',
            defaults={'name': 'Manage', 'module': 'Test', 'kind': 'action', 'sort_order': 0},
        )
        access, _ = Permission.objects.get_or_create(
            codename='access.services',
            defaults={'name': 'Access', 'module': 'Test', 'kind': 'access', 'sort_order': 0},
        )
        self.role.permissions.add(perm, access)
        self.user = User.objects.create_user(username='svcuser', password='test-pass-123', role=self.role)
        self.customer = Customer.objects.create(name='Test Müşteri', phone='5551234567')
        self.status_a = StatusOption.objects.create(name='Aktif', color='#22c55e', sort_order=1)
        self.status_b = StatusOption.objects.create(name='Beklemede', color='#eab308', sort_order=2)
        self.priority_a = PriorityOption.objects.create(name='Normal', color='#64748b')
        self.priority_b = PriorityOption.objects.create(name='Acil', color='#ef4444')
        self.service = ServiceRecord.objects.create(
            customer=self.customer,
            status=self.status_a,
            priority=self.priority_a,
        )

    def _post_quick(self, **extra):
        self.client.login(username='svcuser', password='test-pass-123')
        self.client.get('/services-dashboard/services/')
        csrf = self.client.cookies['csrftoken'].value
        payload = {
            'service_id': str(self.service.id),
            'field': 'priority',
            'value': str(self.priority_b.id),
        }
        payload.update(extra)
        return self.client.post(
            '/services-dashboard/services/quick-update/',
            data=payload,
            HTTP_X_CSRFTOKEN=csrf,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )

    def test_priority_quick_update_ok_json(self):
        res = self._post_quick()
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get('ok'))
        self.assertEqual(data.get('field'), 'priority')
        self.assertEqual(data.get('label'), 'Acil')
        self.service.refresh_from_db()
        self.assertEqual(self.service.priority_id, self.priority_b.id)

    def test_invalid_field_returns_json_error(self):
        res = self._post_quick(field='notes', value='1')
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data.get('ok'))
        self.assertIn('Geçersiz alan', data.get('error', ''))

    def test_same_status_returns_ok_without_change(self):
        self.client.login(username='svcuser', password='test-pass-123')
        self.client.get('/services-dashboard/services/')
        csrf = self.client.cookies['csrftoken'].value
        res = self.client.post(
            '/services-dashboard/services/quick-update/',
            data={
                'service_id': str(self.service.id),
                'field': 'status',
                'value': str(self.status_a.id),
            },
            HTTP_X_CSRFTOKEN=csrf,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get('ok'))

    def test_forbidden_returns_json_not_redirect(self):
        limited = Role.objects.create(slug='svc-view', name='View', is_system=False)
        view_perm, _ = Permission.objects.get_or_create(
            codename='access.services',
            defaults={'name': 'Access', 'module': 'Test', 'kind': 'access', 'sort_order': 0},
        )
        limited.permissions.add(view_perm)
        User.objects.create_user(username='viewer', password='test-pass-123', role=limited)
        self.client.login(username='viewer', password='test-pass-123')
        self.client.get('/services-dashboard/services/')
        csrf = self.client.cookies['csrftoken'].value
        res = self.client.post(
            '/services-dashboard/services/quick-update/',
            data={
                'service_id': str(self.service.id),
                'field': 'priority',
                'value': str(self.priority_b.id),
            },
            HTTP_X_CSRFTOKEN=csrf,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(res.status_code, 403)
        self.assertFalse(res.json().get('ok'))
