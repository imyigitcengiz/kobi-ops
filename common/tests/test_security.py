"""Güvenlik regresyon testleri — kimlik doğrulama, CSRF, izinler."""

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from users.models import Permission, Role

User = get_user_model()


class SecurityApiTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.admin_role = Role.objects.create(slug='test-admin', name='Test Admin', is_system=False)
        for codename in (
            'access.settings',
            'access.services',
            'services.manage',
            'tools.whatsapp',
            'tools.ai',
        ):
            perm, _ = Permission.objects.get_or_create(
                codename=codename,
                defaults={'name': codename, 'module': 'Test', 'kind': 'action', 'sort_order': 0},
            )
            self.admin_role.permissions.add(perm)
        self.user = User.objects.create_user(
            username='secuser',
            password='test-pass-123',
            role=self.admin_role,
        )

    def test_settings_api_requires_login(self):
        res = self.client.get('/ayarlar/api/settings/')
        self.assertEqual(res.status_code, 401)
        data = res.json()
        self.assertFalse(data.get('ok', True))

    def test_settings_api_post_requires_csrf(self):
        self.client.login(username='secuser', password='test-pass-123')
        res = self.client.post(
            '/ayarlar/api/settings/',
            data=json.dumps({'site_name': 'X'}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 403)

    def test_settings_api_post_with_csrf(self):
        self.client.login(username='secuser', password='test-pass-123')
        self.client.get('/ayarlar/genel/')
        csrf = self.client.cookies['csrftoken'].value
        res = self.client.post(
            '/ayarlar/api/settings/',
            data=json.dumps({'site_name': 'Güvenli Test'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertIn(res.status_code, (200, 400))

    def test_whatsapp_bridge_spawn_requires_permission(self):
        limited_role = Role.objects.create(slug='limited-tools', name='Limited', is_system=False)
        perm, _ = Permission.objects.get_or_create(
            codename='access.tools',
            defaults={'name': 'Tools', 'module': 'Test', 'kind': 'access', 'sort_order': 0},
        )
        limited_role.permissions.add(perm)
        limited = User.objects.create_user(
            username='limited',
            password='test-pass-123',
            role=limited_role,
        )
        self.client.login(username='limited', password='test-pass-123')
        self.client.get('/tools/')
        csrf = self.client.cookies['csrftoken'].value
        res = self.client.post(
            '/tools/whatsapp/kopru/baslat/',
            data='{}',
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(res.status_code, 403)

    def test_options_catalog_requires_auth(self):
        res = self.client.get('/ayarlar/api/options/catalog/')
        self.assertEqual(res.status_code, 401)


@override_settings(WHATSAPP_BRIDGE_CAN_SPAWN=False)
class BridgeSpawnGuardTests(TestCase):
    def setUp(self):
        self.client = Client()
        role = Role.objects.create(slug='wa-role', name='WA', is_system=False)
        perm, _ = Permission.objects.get_or_create(
            codename='tools.whatsapp',
            defaults={'name': 'WA', 'module': 'Test', 'kind': 'action', 'sort_order': 0},
        )
        role.permissions.add(perm)
        self.user = User.objects.create_user(
            username='wauser',
            password='test-pass-123',
            role=role,
        )

    def test_spawn_blocked_when_disabled(self):
        self.client.login(username='wauser', password='test-pass-123')
        res = self.client.post(
            '/tools/whatsapp/kopru/baslat/',
            data='{}',
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json().get('reason'), 'spawn_disabled')
