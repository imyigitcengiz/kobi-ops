"""Django açılışında WhatsApp Node köprüsünü arka planda başlatma / uzak köprüyü bekleme."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time

logger = logging.getLogger(__name__)


def is_app_server_process() -> bool:
    """Yönetim komutları ve tek seferlik CLI için köprü başlatma."""
    argv = sys.argv
    if len(argv) < 1:
        return False
    prog = (argv[0] or '').lower()
    if prog.endswith('manage.py') or 'manage.py' in prog:
        skip = (
            'migrate', 'makemigrations', 'test', 'shell', 'collectstatic',
            'createsuperuser', 'flush', 'check', 'wait_whatsapp_bridge',
            'sync_partner_firms', 'ensure_', 'createsuperuser',
        )
        if any(cmd in argv for cmd in skip):
            return False
        if 'runserver' in argv:
            if '--noreload' in argv:
                return True
            return os.environ.get('RUN_MAIN') == 'true'
        return False

    if 'runserver' in argv:
        if '--noreload' in argv:
            return True
        return os.environ.get('RUN_MAIN') == 'true'

    if 'daphne' in argv or prog.endswith('daphne'):
        return True

    if 'gunicorn' in argv or 'uvicorn' in argv:
        return False

    return False


def schedule_bridge_autostart() -> None:
    from django.conf import settings

    if not getattr(settings, 'WHATSAPP_BRIDGE_AUTO_START', False):
        return
    if not is_app_server_process():
        return

    thread = threading.Thread(
        target=_autostart_worker,
        name='gy-whatsapp-bridge-autostart',
        daemon=True,
    )
    thread.start()


def _autostart_worker() -> None:
    from django.conf import settings
    from tools.whatsapp_bridge_runner import (
        bridge_reachable,
        bridge_spawn_allowed,
        probe_bridge,
        try_spawn_bridge_process,
    )

    url = getattr(settings, 'WHATSAPP_BRIDGE_URL', '')
    retries = int(getattr(settings, 'WHATSAPP_BRIDGE_AUTO_START_RETRIES', 15))
    delay = float(getattr(settings, 'WHATSAPP_BRIDGE_AUTO_START_DELAY', 2.0))

    time.sleep(0.8)

    if bridge_reachable(timeout=1.0):
        logger.info('WhatsApp köprüsü zaten çalışıyor (%s).', url)
        return

    if bridge_spawn_allowed():
        result = try_spawn_bridge_process()
        if result.get('spawned'):
            logger.info(
                'WhatsApp köprüsü başlatıldı (node=%s).',
                result.get('node') or '?',
            )
        elif result.get('reason') == 'no_node':
            logger.error('WhatsApp köprüsü: %s', result.get('message'))
            return
        elif result.get('reason') == 'npm_failed':
            logger.error('WhatsApp köprüsü npm kurulumu: %s', result.get('message'))
            return
        elif result.get('reason') not in ('already_running', 'recent'):
            logger.warning(
                'WhatsApp köprüsü başlatılamadı (%s): %s',
                result.get('reason'),
                result.get('message'),
            )

    for attempt in range(1, retries + 1):
        if bridge_reachable(timeout=1.2):
            logger.info('WhatsApp köprüsü hazır (%s), deneme %s.', url, attempt)
            return
        probe = probe_bridge(timeout=1.0)
        logger.info(
            'WhatsApp köprüsü bekleniyor (%s/%s): %s',
            attempt,
            retries,
            probe.get('detail') or probe.get('state'),
        )
        if bridge_spawn_allowed() and attempt in (3, 7, 11):
            try_spawn_bridge_process(force=attempt >= 7)
        time.sleep(delay)

    logger.error(
        'WhatsApp köprüsü %s saniye içinde hazır olmadı. URL=%s — '
        'Coolify/Docker ise whatsapp-bridge servisini kontrol edin; '
        'yerelde Node kurulu mu? Django npm install dener; log: tools/whatsapp_bridge/bridge_ui.log',
        int(retries * delay),
        url,
    )
