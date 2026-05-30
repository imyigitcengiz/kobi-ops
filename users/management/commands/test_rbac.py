"""RBAC senaryo testleri — rol bazlı URL erişim matrisi."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.test import Client

from users.models import Role

User = get_user_model()

SCENARIOS = [
    {
        'slug': 'accounting',
        'username': '_rbac_muhasebe',
        'checks': [
            ('GET', '/contact/musteriler/', 200, 'Muhasebe müşteri listesini görebilmeli'),
            ('GET', '/contact/musteriler/yeni/', 302, 'Muhasebe müşteri oluşturamaz'),
            ('GET', '/contact/personel/', 302, 'Muhasebe personel sayfasına giremez'),
            ('GET', '/muhasebe/', 200, 'Muhasebe modülüne erişebilmeli'),
            ('GET', '/muhasebe/maas-avans/', 200, 'Muhasebe maaş/avans sayfasına erişebilmeli'),
            ('GET', '/muhasebe/gelir-gider/', 200, 'Muhasebe gelir/gider sayfasına erişebilmeli'),
            ('GET', '/services-dashboard/services/', 302, 'Muhasebe servis modülüne giremez'),
            ('GET', '/sales-lead/', 302, 'Muhasebe satış modülüne giremez'),
        ],
    },
    {
        'slug': 'sales',
        'username': '_rbac_satis',
        'checks': [
            ('GET', '/contact/musteriler/', 200, 'Satış müşteri listesini görebilmeli'),
            ('GET', '/contact/musteriler/yeni/', 200, 'Satış müşteri oluşturabilmeli'),
            ('GET', '/contact/personel/', 302, 'Satış personel/maaş sayfasına giremez'),
            ('GET', '/muhasebe/', 302, 'Satış muhasebe modülüne giremez'),
            ('GET', '/sales-lead/kayitlar/', 302, 'Satış kayıtları yönlendirmesi (modül kapalı)'),
            ('GET', '/services-dashboard/services/', 302, 'Satış servis modülüne giremez'),
        ],
    },
    {
        'slug': 'service',
        'username': '_rbac_servis',
        'checks': [
            ('GET', '/services-dashboard/services/', 200, 'Servis personeli servis listesini görebilmeli'),
            ('GET', '/contact/musteriler/', 200, 'Servis personeli müşteri listesini görebilmeli'),
            ('GET', '/contact/personel/', 302, 'Servis personeli personel sayfasına giremez'),
            ('GET', '/muhasebe/', 302, 'Servis personeli muhasebe modülüne giremez'),
            ('GET', '/sales-lead/', 302, 'Servis personeli satış modülüne giremez'),
        ],
    },
    {
        'slug': 'operation',
        'username': '_rbac_operasyon',
        'checks': [
            ('GET', '/services-dashboard/services/', 200, 'Operasyon servis listesine erişebilmeli'),
            ('GET', '/contact/ekip/', 200, 'Operasyon ekip sayfasına erişebilmeli'),
            ('GET', '/contact/personel/', 200, 'Operasyon personel kayıtlarına erişebilmeli'),
            ('GET', '/muhasebe/', 302, 'Operasyon muhasebe modülüne giremez'),
            ('GET', '/contact/musteriler/', 200, 'Operasyon müşteri listesine erişebilmeli'),
        ],
    },
]


class Command(BaseCommand):
    help = 'Rol bazlı erişim senaryolarını test eder (RBAC matrisi).'

    def handle(self, *args, **options):
        passed = 0
        failed = 0
        client = Client()

        self.stdout.write(self.style.MIGRATE_HEADING('RBAC Senaryo Testleri'))
        self.stdout.write('')

        for scenario in SCENARIOS:
            role = Role.objects.filter(slug=scenario['slug']).first()
            if not role:
                self.stdout.write(self.style.ERROR(f"  Rol bulunamadı: {scenario['slug']}"))
                failed += len(scenario['checks'])
                continue

            user, _ = User.objects.get_or_create(
                username=scenario['username'],
                defaults={'is_active': True},
            )
            user.set_password('test1234')
            user.role = role
            user.is_superuser = False
            user.is_staff = False
            user.save()

            perms = sorted(user.get_permission_codenames())
            self.stdout.write(f"[{role.name}] {user.username}")
            self.stdout.write(f"  İzinler: {', '.join(perms)}")

            client.force_login(user)
            for method, path, expected, label in scenario['checks']:
                if method == 'GET':
                    response = client.get(path)
                else:
                    response = client.post(path)

                ok = response.status_code == expected
                if ok:
                    passed += 1
                    self.stdout.write(self.style.SUCCESS(f"  OK {label} -> {response.status_code}"))
                else:
                    failed += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"  FAIL {label} -> beklenen {expected}, alinan {response.status_code} ({path})"
                        )
                    )
            self.stdout.write('')

        total = passed + failed
        if failed:
            self.stdout.write(self.style.ERROR(f'Sonuc: {passed}/{total} gecti, {failed} basarisiz'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Sonuc: {passed}/{total} gecti — tum senaryolar OK'))

        if failed:
            raise SystemExit(1)
