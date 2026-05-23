"""Üretim: panel açılmadan önce whatsapp-bridge servisinin hazır olmasını bekler."""

from django.core.management.base import BaseCommand

from tools.whatsapp_bridge_runner import (
    bridge_reachable,
    bridge_spawn_allowed,
    ensure_bridge_environment,
    probe_bridge,
    try_spawn_bridge_process,
)


class Command(BaseCommand):
    help = 'WHATSAPP_BRIDGE_URL adresindeki köprünün /api/connections yanıt vermesini bekler.'

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=120, help='Maksimum bekleme (sn)')
        parser.add_argument('--spawn', action='store_true', help='Yerel ise Node köprüsünü başlatmayı dene')
        parser.add_argument('--interval', type=float, default=2.0, help='Denemeler arası süre (sn)')

    def handle(self, *args, **options):
        import time

        from django.conf import settings

        timeout = max(options['timeout'], 1)
        interval = max(options['interval'], 0.5)
        url = getattr(settings, 'WHATSAPP_BRIDGE_URL', '')
        deadline = time.monotonic() + timeout
        attempt = 0

        self.stdout.write(f'Köprü bekleniyor: {url} (en fazla {timeout}s)')

        if options['spawn'] and bridge_spawn_allowed() and not bridge_reachable(timeout=0.8):
            env = ensure_bridge_environment()
            if not env.get('ok'):
                self.stdout.write(self.style.WARNING(env.get('message') or 'Köprü ortamı hazırlanamadı.'))
            r = try_spawn_bridge_process()
            if r.get('spawned'):
                self.stdout.write(self.style.SUCCESS('Yerel Node köprüsü başlatıldı.'))
            elif r.get('message'):
                self.stdout.write(self.style.WARNING(r['message']))

        while time.monotonic() < deadline:
            attempt += 1
            if bridge_reachable(timeout=1.5):
                self.stdout.write(self.style.SUCCESS(f'Köprü hazır (deneme {attempt}).'))
                return
            probe = probe_bridge(timeout=1.0)
            self.stdout.write(f'  [{attempt}] {probe.get("state")}: {probe.get("detail")}')
            time.sleep(interval)

        self.stdout.write(
            self.style.ERROR(
                f'Köprü {timeout}s içinde yanıt vermedi. '
                'Docker: docker compose ps / logs whatsapp-bridge. '
                'Yerel: Django otomatik başlatır; log: tools/whatsapp_bridge/bridge_ui.log'
            )
        )
        raise SystemExit(1)
