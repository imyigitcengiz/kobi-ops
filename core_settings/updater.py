"""Uygulama güncelleme kontrolü ve uygulama (n8n tarzı panel içi güncelleme)."""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

CACHE_FILENAME = '.kobiops_update_cache.json'


@dataclass
class UpdateStatus:
    ok: bool = True
    checked_at: str = ''
    update_available: bool = False
    local_version: str = ''
    local_commit: str = ''
    local_commit_full: str = ''
    remote_commit: str = ''
    remote_commit_full: str = ''
    remote_message: str = ''
    remote_date: str = ''
    branch: str = 'main'
    repo: str = ''
    apply_mode: str = 'none'  # git | webhook | none
    can_apply: bool = False
    message: str = ''
    error: str = ''

    def to_dict(self):
        return asdict(self)


def _repo_root() -> Path:
    return Path(settings.BASE_DIR)


def _data_dir() -> Path | None:
    data = os.environ.get('DATA_DIR', '').strip()
    if data:
        return Path(data)
    return None


def _cache_path() -> Path | None:
    root = _data_dir()
    if not root:
        return None
    return root / CACHE_FILENAME


def _read_version_file() -> str:
    path = _repo_root() / 'VERSION'
    if not path.is_file():
        return ''
    return path.read_text(encoding='utf-8').strip().splitlines()[0].strip()


def _read_build_commit() -> str:
    env = os.environ.get('KOBIOPS_BUILD_COMMIT', '').strip()
    if env and env != 'unknown':
        return env
    path = _repo_root() / '.build_commit'
    if path.is_file():
        return path.read_text(encoding='utf-8').strip()
    return ''


def _run_git(args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess | None:
    git_dir = _repo_root() / '.git'
    if not git_dir.exists():
        return None
    try:
        return subprocess.run(
            ['git', *args],
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning('git komutu başarısız: %s', exc)
        return None


def local_git_commit() -> tuple[str, str]:
    proc = _run_git(['rev-parse', 'HEAD'])
    if not proc or proc.returncode != 0:
        return '', ''
    full_sha = (proc.stdout or '').strip()
    short = full_sha[:7] if full_sha else ''
    return short, full_sha


def local_branch() -> str:
    proc = _run_git(['rev-parse', '--abbrev-ref', 'HEAD'])
    if proc and proc.returncode == 0:
        return (proc.stdout or '').strip() or settings.KOBIOPS_UPDATE_BRANCH
    return settings.KOBIOPS_UPDATE_BRANCH


def _github_request(url: str) -> dict | None:
    headers = {
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'KobiOps-Updater',
    }
    token = settings.KOBIOPS_GITHUB_TOKEN
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError) as exc:
        logger.warning('GitHub API hatası (%s): %s', url, exc)
        return None


def fetch_remote_commit() -> tuple[str, str, str, str]:
    repo = settings.KOBIOPS_UPDATE_REPO
    branch = settings.KOBIOPS_UPDATE_BRANCH
    url = f'https://api.github.com/repos/{repo}/commits/{branch}'
    data = _github_request(url)
    if not data:
        return '', '', '', ''
    full_sha = data.get('sha', '')
    short = full_sha[:7] if full_sha else ''
    commit = data.get('commit') or {}
    message = (commit.get('message') or '').splitlines()[0].strip()
    date_raw = commit.get('author', {}).get('date', '')
    return short, full_sha, message, date_raw


def resolve_apply_mode() -> str:
    if settings.KOBIOPS_DEPLOY_WEBHOOK_URL:
        return 'webhook'
    if (_repo_root() / '.git').exists() and _run_git(['--version']) is not None:
        return 'git'
    return 'none'


def check_for_updates(*, force: bool = False) -> UpdateStatus:
    cache_file = _cache_path()
    interval = max(60, int(settings.KOBIOPS_UPDATE_CHECK_INTERVAL))

    if not force and cache_file and cache_file.is_file():
        try:
            cached = json.loads(cache_file.read_text(encoding='utf-8'))
            checked_at = cached.get('checked_at', '')
            if checked_at:
                ts = datetime.fromisoformat(checked_at.replace('Z', '+00:00'))
                age = (datetime.now(timezone.utc) - ts).total_seconds()
                if age < interval and cached.get('ok'):
                    status = UpdateStatus(**{k: v for k, v in cached.items() if k in UpdateStatus.__dataclass_fields__})
                    return status
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    status = UpdateStatus(
        checked_at=datetime.now(timezone.utc).isoformat(),
        local_version=_read_version_file(),
        branch=settings.KOBIOPS_UPDATE_BRANCH,
        repo=settings.KOBIOPS_UPDATE_REPO,
        apply_mode=resolve_apply_mode(),
    )

    short, full = local_git_commit()
    if short:
        status.local_commit = short
        status.local_commit_full = full
    else:
        build = _read_build_commit()
        if build:
            status.local_commit = build[:7]
            status.local_commit_full = build

    r_short, r_full, r_msg, r_date = fetch_remote_commit()
    if not r_full:
        status.ok = False
        status.error = 'GitHub üzerinden sürüm bilgisi alınamadı. İnternet veya repo ayarlarını kontrol edin.'
        _write_cache(status)
        return status

    status.remote_commit = r_short
    status.remote_commit_full = r_full
    status.remote_message = r_msg
    status.remote_date = r_date

    if status.local_commit_full and status.local_commit_full == r_full:
        status.update_available = False
        status.message = 'Uygulama güncel.'
    elif status.local_commit_full:
        status.update_available = True
        status.message = 'Yeni sürüm mevcut.'
    else:
        status.update_available = True
        status.message = 'Uzak depoda yeni commit var (yerel commit bilinmiyor — güncellemeyi uygulayabilirsiniz).'

    status.can_apply = status.update_available and status.apply_mode != 'none'
    if status.apply_mode == 'none' and status.update_available:
        status.message += ' Güncelleme için git deposu veya KOBIOPS_DEPLOY_WEBHOOK_URL tanımlayın.'

    _write_cache(status)
    return status


def _write_cache(status: UpdateStatus) -> None:
    path = _cache_path()
    if not path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(status.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError as exc:
        logger.warning('Güncelleme önbelleği yazılamadı: %s', exc)


def _run_manage(cmd: list[str], *, timeout: int = 300) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ['python', 'manage.py', *cmd],
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        out = (proc.stdout or '') + (proc.stderr or '')
        return proc.returncode == 0, out.strip()[-2000:]
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, str(exc)


def apply_git_update() -> tuple[bool, str, list[str]]:
    steps: list[str] = []
    branch = settings.KOBIOPS_UPDATE_BRANCH

    ok, out = _run_manage(['guard_persistent_data', '--phase', 'backup'])
    steps.append('Otomatik veritabanı yedeği' + (' ✓' if ok else ' ✗'))
    if not ok:
        return False, f'Yedek alınamadı: {out}', steps

    fetch = _run_git(['fetch', 'origin', branch], timeout=120)
    if not fetch or fetch.returncode != 0:
        err = (fetch.stderr if fetch else '') or 'git fetch başarısız'
        steps.append('git fetch ✗')
        return False, err.strip(), steps
    steps.append('git fetch ✓')

    pull = _run_git(['pull', '--ff-only', 'origin', branch], timeout=180)
    if not pull or pull.returncode != 0:
        err = (pull.stderr if pull else '') or 'git pull başarısız'
        steps.append('git pull ✗')
        return False, err.strip(), steps
    steps.append('git pull ✓')

    for label, cmd in (
        ('migrate', ['migrate', '--noinput']),
        ('collectstatic', ['collectstatic', '--noinput']),
        ('sync_permissions', ['sync_permissions']),
    ):
        ok, out = _run_manage(cmd)
        steps.append(f'{label}' + (' ✓' if ok else ' ✗'))
        if not ok:
            return False, f'{label} hatası: {out}', steps

    return True, 'Güncelleme tamamlandı. Uygulama yeniden başlatılıyor…', steps


def apply_webhook_update() -> tuple[bool, str, list[str]]:
    url = settings.KOBIOPS_DEPLOY_WEBHOOK_URL
    if not url:
        return False, 'Webhook URL tanımlı değil.', []
    steps = ['Deploy webhook tetikleniyor…']
    req = urllib.request.Request(url, method='POST', data=b'')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.getcode()
        if 200 <= code < 300:
            steps.append(f'Webhook ✓ (HTTP {code})')
            return True, 'Deploy tetiklendi. Panel birkaç dakika içinde yeni sürümle ayağa kalkacak.', steps
        steps.append(f'Webhook ✗ (HTTP {code})')
        return False, f'Webhook HTTP {code} döndü.', steps
    except urllib.error.URLError as exc:
        steps.append('Webhook ✗')
        return False, str(exc.reason if hasattr(exc, 'reason') else exc), steps


def apply_update() -> tuple[bool, str, list[str], bool]:
    """Güncellemeyi uygula. Dönüş: ok, mesaj, adımlar, restart_gerekli."""
    mode = resolve_apply_mode()
    if mode == 'git':
        ok, msg, steps = apply_git_update()
        return ok, msg, steps, ok
    if mode == 'webhook':
        ok, msg, steps = apply_webhook_update()
        return ok, msg, steps, False
    return False, 'Güncelleme yöntemi yapılandırılmamış.', [], False


def schedule_restart(delay_seconds: float = 2.5) -> None:
    """Docker restart policy için süreci sonlandır."""

    def _exit():
        time.sleep(delay_seconds)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=_exit, daemon=True).start()
