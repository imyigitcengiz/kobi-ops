/**
 * Canlı senkron: gereksiz tam sayfa yenilemesini engeller; katalog güncellemelerini hedefler.
 */
(function () {
  const WS_PATH = '/ws/live-sync/';
  let reloadTimer = null;
  let lastEventKey = '';
  let lastEventAt = 0;

  function getWsUrl() {
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${scheme}://${window.location.host}${WS_PATH}`;
  }

  function getMeId() {
    return window.GY_USER_ID != null ? Number(window.GY_USER_ID) : null;
  }

  function markLocalSave() {
    window.__gyLastLocalSave = Date.now();
  }

  window.GY_MARK_LOCAL_SAVE = markLocalSave;

  function isFormPage() {
    const p = window.location.pathname;
    if (/\/services-dashboard\/services\/(new|\d+\/edit)\/?$/.test(p)) return true;
    if (p.includes('/services-dashboard/settings') || p.startsWith('/ayarlar/')) return true;
    if (document.getElementById('serviceRecordForm')) return true;
    return false;
  }

  function isBlockingOverlayOpen() {
    const ids = [
      'quickOptionModal',
      'customerModal',
      'customerInfoModal',
      'aiChatWindow',
    ];
    for (const id of ids) {
      const el = document.getElementById(id);
      if (el && !el.classList.contains('hidden')) return true;
    }
    const aiWrap = document.getElementById('aiChatWindow');
    if (aiWrap && !aiWrap.classList.contains('hidden')) return true;
    return false;
  }

  function shouldBlockReload(payload) {
    if (window.__gyLastLocalSave && Date.now() - window.__gyLastLocalSave < 5000) {
      return true;
    }
    const me = getMeId();
    if (me && payload?.user_id != null && Number(payload.user_id) === me) {
      return true;
    }
    if (isBlockingOverlayOpen()) return true;
    if (isFormPage() && document.activeElement) {
      const tag = (document.activeElement.tagName || '').toUpperCase();
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) return true;
    }
    return false;
  }

  function showToast(message) {
    const toast = document.createElement('div');
    toast.className =
      'fixed bottom-20 left-4 z-[230] max-w-xs px-4 py-2 rounded-xl text-xs font-semibold shadow-lg border bg-slate-900 text-white border-slate-700';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3200);
  }

  async function refreshOptionsCatalog() {
    const base = window.AYARLAR_BASE || '/ayarlar';
    try {
      const res = await fetch(`${base}/api/options/catalog/`);
      const data = await res.json();
      if (!data.products) return;

      const script = document.getElementById('optionsCatalogData');
      if (script) script.textContent = JSON.stringify(data);

      if (window.serviceFormCatalog) {
        Object.assign(window.serviceFormCatalog, data);
      }
      if (typeof window.refreshServiceTypesForProducts === 'function') {
        window.refreshServiceTypesForProducts();
      }
      showToast('Seçenek listesi güncellendi.');
    } catch (e) {
      /* ignore */
    }
  }

  function shouldAutoReload(path) {
    return (
      path.startsWith('/services-dashboard/') ||
      path.startsWith('/contact/') ||
      path.startsWith('/crm/') ||
      path.startsWith('/sales-lead/')
    );
  }

  function scheduleReload(payload) {
    const path = window.location.pathname;
    if (!shouldAutoReload(path)) return;
    if (shouldBlockReload(payload)) {
      showToast('Liste arka planda güncellendi. İşiniz bitince sayfayı yenileyebilirsiniz.');
      return;
    }
    const key = `${payload.kind}:${payload.id}:${payload.action}`;
    const now = Date.now();
    if (key === lastEventKey && now - lastEventAt < 1500) return;
    lastEventKey = key;
    lastEventAt = now;

    if (reloadTimer) clearTimeout(reloadTimer);
    reloadTimer = setTimeout(() => window.location.reload(), 1200);
  }

  function handlePayload(payload) {
    if (!payload || !payload.kind) return;

    if (payload.kind === 'options') {
      refreshOptionsCatalog();
      return;
    }

    if (['customer', 'service', 'sales_lead'].includes(payload.kind)) {
      scheduleReload(payload);
    }
  }

  let reconnectDelay = 1000;

  function connect() {
    let socket;
    try {
      socket = new WebSocket(getWsUrl());
    } catch (e) {
      return;
    }

    socket.onopen = () => {
      reconnectDelay = 1000;
    };

    socket.onmessage = (event) => {
      try {
        handlePayload(JSON.parse(event.data));
      } catch (e) {
        /* ignore */
      }
    };

    socket.onclose = () => {
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 12000);
    };
  }

  window.GY_LIVE_SYNC = { markLocalSave, refreshOptionsCatalog };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', connect);
  } else {
    connect();
  }
})();
