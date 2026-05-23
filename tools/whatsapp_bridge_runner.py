"""WhatsApp Node köprüsünü başlatma — Windows'ta görünür konsol, port çakışması ve yönetici modu."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from django.conf import settings

_LAST_SPAWN_MONO = 0.0
_DEBOUNCE_SEC = 8.0
_DEPS_INSTALL_LOCK = threading.Lock()


def _bridge_base_url() -> str:
    return getattr(settings, 'WHATSAPP_BRIDGE_URL', 'http://127.0.0.1:3939').rstrip('/')


def _bridge_port() -> int:
    u = urlparse(_bridge_base_url())
    if u.port:
        return u.port
    return 3939


def _bridge_dir() -> Path:
    return Path(settings.BASE_DIR) / 'tools' / 'whatsapp_bridge'


def _log_path() -> Path:
    return _bridge_dir() / 'bridge_ui.log'


def _append_spawn_log(message: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] [spawn] {message}\n"
    try:
        _log_path().parent.mkdir(parents=True, exist_ok=True)
        with open(_log_path(), 'a', encoding='utf-8') as fh:
            fh.write(line)
    except OSError:
        pass


def _is_local_bridge_url() -> bool:
    host = (urlparse(_bridge_base_url()).hostname or '').lower()
    return host in ('127.0.0.1', 'localhost', '::1')


def bridge_spawn_allowed() -> bool:
    """Yerel Node süreci Django tarafından başlatılabilir mi (geliştirme / Windows)."""
    if not getattr(settings, 'WHATSAPP_BRIDGE_CAN_SPAWN', True):
        return False
    return _is_local_bridge_url()


def _offline_detail_local() -> str:
    if bridge_spawn_allowed():
        return 'Köprü kapalı. Birkaç saniye bekleyin veya "Köprüyü başlat"a basın — Django otomatik açar.'
    return (
        'Köprü bu sunucuda otomatik başlatılmıyor. '
        'whatsapp-bridge servisini çalıştırın ve WHATSAPP_BRIDGE_URL ayarlayın '
        '(DEPLOY.md).'
    )


def _offline_detail_remote(base: str, err: str | None = None) -> str:
    msg = f'Köprüye ulaşılamıyor ({base}).'
    if err:
        short = err.replace('\n', ' ')[:160]
        msg += f' Hata: {short}'
    msg += ' whatsapp-bridge konteynerinin/sürecinin çalıştığını doğrulayın.'
    return msg


def probe_bridge(timeout: float = 0.6) -> dict:
    """Köprü durumu: none | legacy | modern | blocked."""
    base = _bridge_base_url()
    port = _bridge_port()
    local = _is_local_bridge_url()
    can_spawn = bridge_spawn_allowed()
    out = {
        'state': 'none',
        'legacy': False,
        'modern': False,
        'detail': '',
        'can_spawn': can_spawn,
        'bridge_url': base,
        'is_local': local,
    }

    if local and not _port_is_listening(port):
        out['detail'] = _offline_detail_local()
        return out

    try:
        r_modern = requests.get(f'{base}/api/connections', timeout=timeout)
        if r_modern.ok:
            out.update(state='modern', modern=True, detail='Köprü çalışıyor.')
            return out
    except requests.RequestException as exc:
        if not local:
            out['detail'] = _offline_detail_remote(base, str(exc))
            return out

    try:
        r_legacy = requests.get(f'{base}/api/status', timeout=timeout)
        if r_legacy.ok:
            out.update(
                state='legacy',
                legacy=True,
                detail='Eski köprü sürümü algılandı; yeniden başlatın.',
            )
            return out
    except requests.RequestException:
        pass

    if local:
        if _port_is_listening(port):
            out.update(
                state='blocked',
                detail=(
                    f'Port {port} dolu ama köprü yanıt vermiyor — '
                    'süreç kapatılıp yeniden açılacak.'
                ),
            )
        else:
            out['detail'] = _offline_detail_local()
        return out

    out['detail'] = _offline_detail_remote(base)
    return out


def bridge_reachable(timeout: float = 0.8) -> bool:
    return probe_bridge(timeout).get('modern') is True


def _resolve_node_executable() -> str | None:
    configured = (getattr(settings, 'WHATSAPP_BRIDGE_NODE', '') or '').strip()
    if configured and Path(configured).is_file():
        return configured

    candidates = [
        Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'nodejs' / 'node.exe',
        Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'nodejs' / 'node.exe',
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'node' / 'node.exe',
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    found = shutil.which('node') or shutil.which('node.exe')
    if not found:
        return None
    low = found.lower()
    if 'cursor' in low and 'helpers' in low:
        return None
    return found


def _resolve_npm_executable(node_exe: str | None = None) -> str | None:
    if node_exe:
        npm_name = 'npm.cmd' if sys.platform == 'win32' else 'npm'
        sibling = Path(node_exe).parent / npm_name
        if sibling.is_file():
            return str(sibling)
    return shutil.which('npm.cmd') or shutil.which('npm')


def _bridge_deps_ready(bridge_dir: Path) -> bool:
    node_modules = bridge_dir / 'node_modules'
    if not node_modules.is_dir():
        return False
    return (node_modules / 'express').exists()


def _try_install_node_linux() -> bool:
    if sys.platform == 'win32':
        return False
    if not getattr(settings, 'WHATSAPP_BRIDGE_AUTO_INSTALL_NODE', True):
        return False
    try:
        if hasattr(os, 'geteuid') and os.geteuid() != 0:
            _append_spawn_log('Node yok; sistem paketi kurulumu için root gerekir (apt/dnf).')
            return False
    except AttributeError:
        return False

    if shutil.which('apt-get'):
        _append_spawn_log('Node.js kuruluyor (apt-get)…')
        try:
            r1 = subprocess.run(
                ['apt-get', 'update', '-qq'],
                capture_output=True,
                text=True,
                timeout=300,
            )
            r2 = subprocess.run(
                ['apt-get', 'install', '-y', '--no-install-recommends', 'nodejs', 'npm'],
                capture_output=True,
                text=True,
                timeout=600,
            )
            if r1.returncode == 0 and r2.returncode == 0 and _resolve_node_executable():
                return True
            tail = ((r2.stderr or '') + (r2.stdout or ''))[-400:]
            _append_spawn_log(f'apt node kurulumu başarısız: {tail}')
        except (OSError, subprocess.TimeoutExpired) as exc:
            _append_spawn_log(f'apt node kurulumu hatası: {exc}')

    if shutil.which('dnf'):
        _append_spawn_log('Node.js kuruluyor (dnf)…')
        try:
            r = subprocess.run(
                ['dnf', 'install', '-y', 'nodejs', 'npm'],
                capture_output=True,
                text=True,
                timeout=600,
            )
            if r.returncode == 0 and _resolve_node_executable():
                return True
        except (OSError, subprocess.TimeoutExpired) as exc:
            _append_spawn_log(f'dnf node kurulumu hatası: {exc}')

    return False


def _run_npm_install(bridge_dir: Path, node_exe: str) -> tuple[bool, str]:
    npm = _resolve_npm_executable(node_exe)
    if not npm:
        return False, 'npm bulunamadı (Node.js kurulumunu kontrol edin).'

    lock = bridge_dir / 'package-lock.json'
    if lock.is_file():
        cmd = [npm, 'ci', '--omit=dev', '--no-audit', '--no-fund', '--loglevel=error']
    else:
        cmd = [npm, 'install', '--omit=dev', '--no-audit', '--no-fund', '--loglevel=error']

    env = os.environ.copy()
    node_dir = str(Path(node_exe).parent)
    env['PATH'] = node_dir + os.pathsep + env.get('PATH', '')

    _append_spawn_log(f'Köprü bağımlılıkları kuruluyor: {" ".join(cmd)}')
    flags = {}
    if sys.platform == 'win32':
        flags['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

    try:
        r = subprocess.run(
            cmd,
            cwd=str(bridge_dir),
            capture_output=True,
            text=True,
            timeout=int(getattr(settings, 'WHATSAPP_BRIDGE_NPM_TIMEOUT', 600)),
            env=env,
            **flags,
        )
    except subprocess.TimeoutExpired:
        return False, 'npm install zaman aşımına uğradı (ilk kurulum uzun sürebilir).'
    except OSError as exc:
        return False, str(exc)

    if r.returncode != 0:
        tail = ((r.stderr or '') + '\n' + (r.stdout or '')).strip()[-500:]
        return False, f'npm install başarısız: {tail or "bilinmeyen hata"}'

    if not _bridge_deps_ready(bridge_dir):
        return False, 'npm install bitti ama node_modules eksik görünüyor.'

    _append_spawn_log('Köprü bağımlılıkları hazır (node_modules).')
    return True, ''


def ensure_bridge_environment(*, install_node: bool = True) -> dict:
    """
    Yerel köprü için Node + npm bağımlılıklarını hazırlar.
    Sunucuda spawn kapalıysa no-op.
    """
    if not bridge_spawn_allowed():
        return {'ok': True, 'skipped': True}

    bridge_dir = _bridge_dir()
    if not (bridge_dir / 'server.js').is_file():
        return {'ok': False, 'reason': 'missing_dir', 'message': 'tools/whatsapp_bridge/server.js bulunamadı.'}

    node_exe = _resolve_node_executable()
    if not node_exe and install_node:
        _try_install_node_linux()
        node_exe = _resolve_node_executable()

    if not node_exe:
        return {
            'ok': False,
            'reason': 'no_node',
            'message': (
                'Node.js bulunamadı. Windows: https://nodejs.org kurun veya '
                'WHATSAPP_BRIDGE_NODE ayarlayın. Linux sunucu (root): Django apt ile kurmayı dener.'
            ),
        }

    if _bridge_deps_ready(bridge_dir):
        return {'ok': True, 'node': node_exe, 'deps_installed': False}

    if not getattr(settings, 'WHATSAPP_BRIDGE_AUTO_NPM_INSTALL', True):
        return {
            'ok': False,
            'reason': 'no_node_modules',
            'message': 'Köprü bağımlılıkları eksik; DJANGO_WHATSAPP_BRIDGE_AUTO_NPM_INSTALL=1 yapın.',
            'node': node_exe,
        }

    with _DEPS_INSTALL_LOCK:
        if _bridge_deps_ready(bridge_dir):
            return {'ok': True, 'node': node_exe, 'deps_installed': False}
        ok, msg = _run_npm_install(bridge_dir, node_exe)
        if not ok:
            return {'ok': False, 'reason': 'npm_failed', 'message': msg, 'node': node_exe}
        return {'ok': True, 'node': node_exe, 'deps_installed': True}


def _port_is_listening(port: int) -> bool:
    if sys.platform == 'win32':
        try:
            out = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                timeout=8,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        needle = f':{port}'
        for line in out.stdout.splitlines():
            if 'LISTENING' not in line.upper():
                continue
            if needle in line:
                return True
        return False

    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(('127.0.0.1', port)) == 0


def _pid_on_port(port: int) -> int | None:
    if sys.platform != 'win32':
        return None
    try:
        out = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    pattern = re.compile(rf':{port}\s+.*?LISTENING\s+(\d+)', re.IGNORECASE)
    for line in out.stdout.splitlines():
        m = pattern.search(line.replace('\t', ' '))
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                continue
    return None


def _kill_pid(pid: int) -> bool:
    if pid <= 0:
        return False
    _append_spawn_log(f'Port {_bridge_port()} üzerindeki süreç sonlandırılıyor: PID {pid}')
    try:
        if sys.platform == 'win32':
            r = subprocess.run(
                ['taskkill', '/PID', str(pid), '/F', '/T'],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
            return r.returncode == 0
        os.kill(pid, 9)
        return True
    except OSError as exc:
        _append_spawn_log(f'taskkill başarısız: {exc}')
        return False


def _ensure_start_script(node_exe: str, bridge_dir: Path) -> Path:
    bat = bridge_dir / 'start_bridge.cmd'
    content = f'''@echo off
chcp 65001 >nul
title GY WhatsApp Bridge
cd /d "{bridge_dir}"
echo [%date% %time%] Köprü baslatiliyor...
echo Node: "{node_exe}"
"{node_exe}" server.js
if errorlevel 1 (
  echo.
  echo HATA: Köprü kapandi. Yukaridaki kirmizi mesaji okuyun.
  echo node_modules yoksa: npm install
  pause
)
'''
    bat.write_text(content, encoding='utf-8')
    return bat


def _spawn_windows(node_exe: str, bridge_dir: Path, bat_path: Path, *, as_admin: bool) -> None:
    bat_quoted = str(bat_path).replace("'", "''")
    work_quoted = str(bridge_dir).replace("'", "''")

    if as_admin:
        ps = (
            f"Start-Process -FilePath '{bat_quoted}' "
            f"-WorkingDirectory '{work_quoted}' -Verb RunAs"
        )
        _append_spawn_log('Yönetici olarak başlatılıyor (UAC penceresi gelebilir)…')
        subprocess.Popen(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps],
            cwd=str(bridge_dir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        return

    _append_spawn_log('Görünür CMD penceresinde başlatılıyor…')
    subprocess.Popen(
        ['cmd', '/c', 'start', 'GY WhatsApp Bridge', '/D', str(bridge_dir), str(bat_path)],
        cwd=str(bridge_dir),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def try_spawn_bridge_process(*, force: bool = False, as_admin: bool | None = None) -> dict:
    global _LAST_SPAWN_MONO

    probe = probe_bridge()

    if not bridge_spawn_allowed():
        return {
            'spawned': False,
            'reason': 'spawn_disabled',
            'message': probe.get('detail') or _offline_detail_local(),
            'probe': probe,
        }

    now = time.monotonic()
    if not force and now - _LAST_SPAWN_MONO < _DEBOUNCE_SEC:
        return {
            'spawned': False,
            'reason': 'recent',
            'message': 'Az önce başlatma denendi; birkaç saniye bekleyin.',
            'probe': probe,
        }

    if probe['modern']:
        return {'spawned': False, 'reason': 'already_running', 'message': None, 'probe': probe}

    if not _is_local_bridge_url():
        return {
            'spawned': False,
            'reason': 'not_localhost',
            'message': 'WHATSAPP_BRIDGE_URL yerel adres değil; otomatik başlatılamıyor.',
            'probe': probe,
        }

    bridge_dir = _bridge_dir()
    server_js = bridge_dir / 'server.js'
    if not server_js.is_file():
        return {
            'spawned': False,
            'reason': 'missing_dir',
            'message': 'tools/whatsapp_bridge/server.js bulunamadı.',
            'probe': probe,
        }

    env_result = ensure_bridge_environment()
    if not env_result.get('ok'):
        return {
            'spawned': False,
            'reason': env_result.get('reason') or 'env_failed',
            'message': env_result.get('message'),
            'probe': probe,
            'deps_installed': env_result.get('deps_installed'),
        }

    node_exe = env_result.get('node') or _resolve_node_executable()
    if not node_exe:
        return {
            'spawned': False,
            'reason': 'no_node',
            'message': 'Node.js bulunamadı. https://nodejs.org kurun veya WHATSAPP_BRIDGE_NODE ayarlayın.',
            'probe': probe,
        }

    port = _bridge_port()
    killed_pid = None
    if probe['state'] in ('legacy', 'blocked') or (probe['state'] == 'none' and _port_is_listening(port)):
        pid = _pid_on_port(port)
        if pid:
            if not _kill_pid(pid):
                return {
                    'spawned': False,
                    'reason': 'port_blocked',
                    'message': (
                        f'Port {port} meşgul (PID {pid}). '
                        'Görev Yöneticisi\'nden node.exe sürecini kapatın veya Django\'yu yönetici olarak çalıştırın.'
                    ),
                    'probe': probe,
                    'pid': pid,
                }
            killed_pid = pid
            time.sleep(1.0)

    if as_admin is None:
        as_admin = bool(force and getattr(settings, 'WHATSAPP_BRIDGE_RUN_AS_ADMIN', False))

    _LAST_SPAWN_MONO = now
    bat_path = _ensure_start_script(node_exe, bridge_dir)
    _append_spawn_log(f'Başlat: node={node_exe} admin={as_admin} port={port} killed={killed_pid}')

    try:
        if sys.platform == 'win32':
            _spawn_windows(node_exe, bridge_dir, bat_path, as_admin=as_admin)
        else:
            subprocess.Popen(
                [node_exe, str(server_js)],
                cwd=str(bridge_dir),
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
    except OSError as exc:
        _append_spawn_log(f'Popen hatası: {exc}')
        return {
            'spawned': False,
            'reason': 'exec_error',
            'message': str(exc),
            'probe': probe,
        }

    return {
        'spawned': True,
        'reason': None,
        'message': None,
        'probe': probe,
        'killed_pid': killed_pid,
        'as_admin': as_admin,
        'node': node_exe,
        'deps_installed': env_result.get('deps_installed'),
    }
