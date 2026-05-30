/** Servis listesi / rapor — durum ve öncelik hızlı güncelleme. */
(function (global) {
  function hexToRgba(hex, alpha) {
    const h = (hex || '#64748b').replace('#', '');
    if (h.length !== 6) return `rgba(100, 116, 139, ${alpha})`;
    const r = parseInt(h.slice(0, 2), 16);
    const g = parseInt(h.slice(2, 4), 16);
    const b = parseInt(h.slice(4, 6), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  function applyBadgeStyles(el, hex) {
    if (!el || !hex) return;
    el.style.backgroundColor = hexToRgba(hex, 0.12);
    el.style.color = hex;
    el.style.borderColor = hexToRgba(hex, 0.35);
  }

  function getCsrfToken() {
    const value = `; ${document.cookie}`;
    const parts = value.split('; csrftoken=');
    if (parts.length === 2) return parts.pop().split(';').shift();
    return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  }

    function closeAllQuickMenus(root) {
    (root || document).querySelectorAll('.quick-update-menu').forEach((m) => {
      m.classList.add('hidden');
    });
  }

  function patchQuickField(serviceId, field, data) {
    const label = data?.label || data?.status_label;
    const color = data?.color || data?.status_color;
    const wrap = document.querySelector(
      `.quick-update-wrap[data-service-id="${serviceId}"][data-field="${field}"]`
    );
    if (!wrap || !label) return false;
    const trigger = wrap.querySelector('.quick-update-trigger');
    if (!trigger) return false;
    if (field === 'priority') {
      trigger.innerHTML = `<span class="w-1.5 h-1.5 rounded-full shrink-0" style="background-color:${color}"></span> ${label}`;
    } else {
      trigger.textContent = label;
    }
    applyBadgeStyles(trigger, color);
    return true;
  }

  async function postQuickUpdate(url, serviceId, field, value) {
    const formData = new FormData();
    formData.append('service_id', String(serviceId));
    formData.append('field', field);
    formData.append('value', String(value));

    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCsrfToken(),
        'X-Requested-With': 'XMLHttpRequest',
        Accept: 'application/json',
      },
      body: formData,
      credentials: 'same-origin',
    });

    let data = {};
    try {
      data = await res.json();
    } catch (_) {
      throw new Error(res.ok ? 'Sunucu yanıtı okunamadı.' : `HTTP ${res.status}`);
    }

    if (!res.ok && data.ok !== true) {
      return {
        ok: false,
        error: data.error || `İstek başarısız (HTTP ${res.status}).`,
      };
    }
    return data;
  }

  function applyQuickUpdateResult(serviceId, field, data, reloadFallback) {
    if (field === 'status' && data.deferred && data.whatsapp_prompt && global.showDeferredServiceStatusChange) {
      global.showDeferredServiceStatusChange(data.whatsapp_prompt, {
        onApplied: (applyData) => {
          const patched = patchQuickField(serviceId, 'status', {
            label: applyData?.status_label,
            color: applyData?.status_color,
          });
          if (patched) {
            if (global.GY_MARK_LOCAL_SAVE) global.GY_MARK_LOCAL_SAVE();
            return;
          }
          if (typeof reloadFallback === 'function') reloadFallback();
        },
        onCancel: () => {},
      });
      return true;
    }

    if (
      field === 'status'
      && global.handleServiceWhatsappStatusResponse
      && global.handleServiceWhatsappStatusResponse(data, reloadFallback)
    ) {
      return true;
    }

    if (global.GY_MARK_LOCAL_SAVE) global.GY_MARK_LOCAL_SAVE();
    if (patchQuickField(serviceId, field, data)) {
      return true;
    }
    if (typeof reloadFallback === 'function') reloadFallback();
    return true;
  }

  function bindQuickUpdateMenus(root, options) {
    const scope = root || document;
    const url = options?.url || global.SERVICE_QUICK_UPDATE_URL;
    if (!url) return;

    scope.querySelectorAll('.quick-update-wrap').forEach((wrap) => {
      if (wrap.dataset.quickUpdateBound === '1') return;
      wrap.dataset.quickUpdateBound = '1';

      const trigger = wrap.querySelector('.quick-update-trigger');
      const menu = wrap.querySelector('.quick-update-menu');
      const serviceId = wrap.dataset.serviceId;
      const field = wrap.dataset.field;

      trigger?.addEventListener('click', (e) => {
        e.stopPropagation();
        const isHidden = menu.classList.contains('hidden');
        closeAllQuickMenus(scope);
        if (isHidden) menu.classList.remove('hidden');
      });

      menu?.querySelectorAll('.quick-update-option').forEach((btn) => {
        btn.addEventListener('click', async () => {
          try {
            const data = await postQuickUpdate(url, serviceId, field, btn.dataset.value);
            if (!data.ok) {
              alert(data.error || 'Güncelleme başarısız.');
              return;
            }
            applyQuickUpdateResult(serviceId, field, data, () => {
              global.location.reload();
            });
          } catch (err) {
            alert(err?.message || 'Hızlı güncelleme sırasında hata oluştu.');
          } finally {
            menu.classList.add('hidden');
          }
        });
      });
    });

    if (!scope.document && !global.__gyQuickUpdateDocClick) {
      global.__gyQuickUpdateDocClick = true;
      document.addEventListener('click', () => closeAllQuickMenus(document));
    }
  }

  function init(options) {
    if (options?.url) {
      global.SERVICE_QUICK_UPDATE_URL = options.url;
    }
    const run = () => bindQuickUpdateMenus(document, options);
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', run);
    } else {
      run();
    }
  }

  global.GyQuickFieldUpdate = {
    init,
    bindQuickUpdateMenus,
    patchQuickField,
    applyBadgeStyles,
    postQuickUpdate,
    applyQuickUpdateResult,
  };
})(window);
