(function () {
  function getCookie(name) {
    const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return m ? decodeURIComponent(m[2]) : '';
  }

  const KIND_ICONS = {
    image: '',
    video: 'video',
    audio: 'music',
    document: 'file-text',
    archive: 'archive',
  };

  function previewHtml(item) {
    const url = item.url;
    const kind = item.kind;
    if (kind === 'image') {
      return `<img src="${url}" alt="" class="w-full h-24 object-cover rounded-xl border border-slate-200">`;
    }
    if (kind === 'video') {
      return `<div class="h-24 rounded-xl border border-slate-800 bg-slate-900 flex items-center justify-center text-white"><i data-lucide="video" class="w-8 h-8"></i></div>`;
    }
    if (kind === 'audio') {
      return `<div class="h-24 rounded-xl border border-violet-200 bg-violet-50 flex items-center justify-center text-violet-600"><i data-lucide="music" class="w-8 h-8"></i></div>`;
    }
    const icon = KIND_ICONS[kind] || 'file';
    return `<div class="h-24 rounded-xl border border-slate-200 bg-slate-100 flex items-center justify-center text-slate-500"><i data-lucide="${icon}" class="w-8 h-8"></i></div>`;
  }

  function initPanel(panel) {
    const serviceId = panel.dataset.serviceId || '';
    const listUrl = panel.dataset.listUrl;
    const uploadUrl = panel.dataset.uploadUrl;
    const canUpload = panel.dataset.canUpload === '1';
    let activeScope = panel.dataset.defaultScope || 'customer';

    const grid = panel.querySelector('[data-media-grid]');
    const emptyEl = panel.querySelector('[data-media-empty]');
    const errEl = panel.querySelector('[data-media-error]');
    const okEl = panel.querySelector('[data-media-success]');
    const fileInput = panel.querySelector('[data-media-file-input]');

    function showMsg(el, text) {
      if (!el) return;
      el.textContent = text || '';
      el.classList.toggle('hidden', !text);
    }

    function scopeButtons() {
      panel.querySelectorAll('.media-scope-btn').forEach((btn) => {
        const on = btn.dataset.scope === activeScope;
        btn.classList.toggle('bg-brand-600', on);
        btn.classList.toggle('text-white', on);
        btn.classList.toggle('border-brand-600', on);
        btn.classList.toggle('border-slate-200', !on);
        btn.classList.toggle('text-slate-600', !on);
      });
    }

    panel.querySelectorAll('[data-scope]').forEach((btn) => {
      btn.addEventListener('click', () => {
        activeScope = btn.dataset.scope;
        scopeButtons();
        loadList();
      });
    });
    scopeButtons();

    function renderItem(item) {
      const label = item.kind_label || item.kind || 'dosya';
      const method = item.compress_method && item.compress_method !== 'none' ? item.compress_method : '';
      const sizeLine = item.saved_percent
        ? ` · %${item.saved_percent} küçültüldü`
        : (method ? ` · ${method}` : '');
      return `
        <div class="relative group border border-slate-200 rounded-2xl p-2 bg-white" data-media-id="${item.id}">
          <a href="${item.url}" target="_blank" rel="noopener">${previewHtml(item)}</a>
          <p class="text-[11px] font-bold text-slate-800 truncate mt-2" title="${item.title}">${item.title}</p>
          <p class="text-[10px] text-slate-400">${item.scope_label} · ${label}${sizeLine} · ${item.created_at}</p>
          <div class="flex gap-2 mt-1">
            ${item.link_url ? `<a href="${item.link_url}" class="text-[10px] font-semibold text-brand-600">Kayıt</a>` : ''}
            ${canUpload ? `<button type="button" data-media-delete="${item.id}" class="text-[10px] font-semibold text-red-600 ml-auto">Sil</button>` : ''}
          </div>
        </div>`;
    }

    async function loadList() {
      if (!listUrl) return;
      showMsg(errEl, '');
      const params = new URLSearchParams({ scope: activeScope });
      if (activeScope === 'service' && serviceId) params.set('service_id', serviceId);
      try {
        const res = await fetch(`${listUrl}?${params}`, {
          headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || `Liste alınamadı (${res.status})`);
        if (!data.ok) throw new Error(data.error || 'Liste alınamadı');
        if (emptyEl) emptyEl.remove();
        if (!data.items.length) {
          grid.innerHTML = '<p class="text-xs text-slate-400 col-span-full">Bu kategoride dosya yok.</p>';
          return;
        }
        grid.innerHTML = data.items.map(renderItem).join('');
        grid.querySelectorAll('[data-media-delete]').forEach((btn) => {
          btn.addEventListener('click', () => deleteItem(btn.dataset.mediaDelete));
        });
        if (window.lucide) lucide.createIcons();
      } catch (e) {
        grid.innerHTML = '';
        showMsg(errEl, e.message || 'Yükleme hatası');
      }
    }

    async function deleteItem(id) {
      if (!confirm('Bu dosya silinsin mi?')) return;
      const res = await fetch(`/contact/musteriler/medya/${id}/sil/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCookie('csrftoken'),
          'X-Requested-With': 'XMLHttpRequest',
        },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        showMsg(errEl, data.error || `Silinemedi (${res.status})`);
        return;
      }
      showMsg(okEl, data.message || 'Silindi');
      loadList();
    }

    async function uploadFiles(fileList) {
      if (!fileList.length) return;
      if (activeScope === 'service' && !serviceId) {
        showMsg(errEl, 'Servis dosyası için önce servisi kaydedin.');
        return;
      }
      const fd = new FormData();
      fd.append('scope', activeScope);
      if (serviceId) fd.append('service_id', serviceId);
      const title = panel.querySelector('[data-media-title]');
      const note = panel.querySelector('[data-media-note]');
      if (title && title.value) fd.append('title', title.value);
      if (note && note.value) fd.append('note', note.value);
      for (const f of fileList) fd.append('files', f);

      showMsg(errEl, '');
      showMsg(okEl, '');
      try {
        const res = await fetch(uploadUrl, {
          method: 'POST',
          body: fd,
          headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest',
            Accept: 'application/json',
          },
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || `Yükleme başarısız (${res.status})`);
        if (!data.ok) throw new Error(data.error || 'Yükleme başarısız');
        let msg = `${data.count} dosya yüklendi.`;
        const compressed = (data.items || []).filter((i) => i.saved_percent);
        if (compressed.length) {
          msg += ` Sunucuda sıkıştırıldı: ${compressed.length} dosya.`;
        }
        if (data.warning) msg += ` ${data.warning}`;
        showMsg(okEl, msg);
        if (fileInput) fileInput.value = '';
        loadList();
      } catch (e) {
        showMsg(errEl, e.message || 'Yükleme hatası');
      }
    }

    if (fileInput) {
      fileInput.addEventListener('change', () => {
        uploadFiles(Array.from(fileInput.files || []));
      });
    }

    loadList();
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.customer-media-panel').forEach(initPanel);
  });
})();
