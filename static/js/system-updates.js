(function () {
  const root = document.getElementById('systemUpdatesRoot');
  if (!root) return;

  const statusUrl = root.dataset.statusUrl;
  const applyUrl = root.dataset.applyUrl;
  let initial = {};
  try {
    const el = document.getElementById('initialUpdateStatus');
    if (el) initial = JSON.parse(el.textContent);
  } catch (e) {
    initial = {};
  }

  function csrfToken() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }

  function $(id) {
    return document.getElementById(id);
  }

  function formatCheckedAt(iso) {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleString('tr-TR');
    } catch (e) {
      return iso;
    }
  }

  function applyModeLabel(mode) {
    if (mode === 'git') return 'Git (pull + migrate)';
    if (mode === 'webhook') return 'Deploy webhook (Coolify)';
    return 'Yapılandırılmamış';
  }

  function render(data) {
    const version = data.local_version ? `v${data.local_version}` : '—';
    if ($('localVersion')) $('localVersion').textContent = version;
    if ($('localCommit')) $('localCommit').textContent = data.local_commit || '—';
    if ($('localChecked')) $('localChecked').textContent = `Son kontrol: ${formatCheckedAt(data.checked_at)}`;
    if ($('remoteCommit')) $('remoteCommit').textContent = data.remote_commit || '—';
    if ($('remoteMessage')) $('remoteMessage').textContent = data.remote_message || '';
    if ($('remoteDate')) $('remoteDate').textContent = data.remote_date ? new Date(data.remote_date).toLocaleString('tr-TR') : '';
    if ($('statusMessage')) $('statusMessage').textContent = data.message || data.error || '';
    if ($('applyModeLabel')) $('applyModeLabel').textContent = applyModeLabel(data.apply_mode);

    const badge = $('statusBadge');
    const banner = $('updateAlertBanner');
    const btnApply = $('btnApplyUpdate');

    if (data.error && !data.ok) {
      badge.textContent = 'Kontrol hatası';
      badge.className = 'px-2.5 py-1 rounded-lg text-xs font-bold bg-red-100 text-red-800';
      banner?.classList.add('hidden');
      btnApply?.setAttribute('disabled', 'disabled');
      return;
    }

    if (data.update_available) {
      badge.textContent = 'Güncelleme var';
      badge.className = 'px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-100 text-amber-800';
      banner?.classList.remove('hidden');
      if ($('updateAlertSubtitle')) {
        $('updateAlertSubtitle').textContent = data.remote_message || `Commit ${data.remote_commit}`;
      }
      if (data.can_apply) {
        btnApply?.removeAttribute('disabled');
      } else {
        btnApply?.setAttribute('disabled', 'disabled');
      }
    } else {
      badge.textContent = 'Güncel';
      badge.className = 'px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-100 text-emerald-800';
      banner?.classList.add('hidden');
      btnApply?.setAttribute('disabled', 'disabled');
    }

    const navBadge = document.getElementById('navUpdateBadge');
    if (data.update_available) navBadge?.classList.remove('hidden');
    else navBadge?.classList.add('hidden');
  }

  async function fetchStatus(force) {
    const url = force ? `${statusUrl}?force=1` : statusUrl;
    const res = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
    const data = await res.json();
    render(data);
    return data;
  }

  async function applyUpdate() {
    const stepsEl = $('applySteps');
    const btnApply = $('btnApplyUpdate');
    const btnCheck = $('btnCheckUpdates');
    if (!confirm('Güncelleme uygulanacak. Veritabanı yedeği alınır (git modunda). Devam edilsin mi?')) {
      return;
    }
    btnApply?.setAttribute('disabled', 'disabled');
    btnCheck?.setAttribute('disabled', 'disabled');
    if (stepsEl) {
      stepsEl.classList.remove('hidden');
      stepsEl.innerHTML = '<li>Güncelleme başlatılıyor…</li>';
    }
    try {
      const res = await fetch(applyUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          Accept: 'application/json',
          'X-CSRFToken': csrfToken(),
        },
      });
      const data = await res.json();
      if (stepsEl && data.steps?.length) {
        stepsEl.innerHTML = data.steps.map((s) => `<li>${s}</li>`).join('');
      }
      if (data.ok) {
        if ($('statusMessage')) $('statusMessage').textContent = data.message;
        if (data.restarting) {
          if (stepsEl) stepsEl.innerHTML += '<li class="text-amber-700 font-semibold">Sunucu yeniden başlatılıyor — sayfa birkaç saniye içinde yenilenecek…</li>';
          setTimeout(() => window.location.reload(), 8000);
        } else {
          await fetchStatus(true);
        }
      } else {
        alert(data.error || data.message || 'Güncelleme başarısız.');
      }
    } catch (err) {
      alert(err?.message || 'Güncelleme isteği başarısız.');
    } finally {
      btnCheck?.removeAttribute('disabled');
      await fetchStatus(false);
    }
  }

  $('btnCheckUpdates')?.addEventListener('click', () => fetchStatus(true));
  $('btnApplyUpdate')?.addEventListener('click', applyUpdate);

  render(initial);
  if (window.lucide) lucide.createIcons();
})();
