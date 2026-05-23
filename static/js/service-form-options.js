(function () {
  const catalogEl = document.getElementById('optionsCatalogData');
  if (!catalogEl) return;

  const sync = window.GyProductServiceTypeSync;
  if (!sync) return;

  const catalog = JSON.parse(catalogEl.textContent);
  const initialProducts = JSON.parse(document.getElementById('initialProductIds')?.textContent || '[]');
  const initialServiceTypes = JSON.parse(document.getElementById('initialServiceTypeIds')?.textContent || '[]');

  const productContainer = document.getElementById('productCheckboxesContainer');
  const serviceTypeContainer = document.getElementById('serviceTypeCheckboxesContainer');
  const serviceTypeHint = document.getElementById('serviceTypeFilterHint');
  const statusSelect = document.querySelector('select[name="status"]');
  const prioritySelect = document.querySelector('select[name="priority"]');

  let selectedServiceTypeIds = new Set(initialServiceTypes.map(Number));

  function getCheckedProductIds() {
    return sync.collectProductIds(document, 'input[name="products"]:checked');
  }

  function mergeServiceTypeIntoCatalog(item) {
    const idx = catalog.service_types.findIndex((x) => x.id === item.id);
    const merged = {
      ...(idx >= 0 ? catalog.service_types[idx] : {}),
      ...item,
      product_ids: item.product_ids || catalog.service_types[idx]?.product_ids || [],
    };
    if (idx >= 0) catalog.service_types[idx] = merged;
    else catalog.service_types.push(merged);
    return merged;
  }

  function linkServiceTypeToProducts(serviceTypeId, productIds) {
    productIds.forEach((pid) => {
      const product = catalog.products.find((p) => p.id === pid);
      if (!product) return;
      if (!product.service_type_ids) product.service_type_ids = [];
      if (!product.service_type_ids.includes(serviceTypeId)) {
        product.service_type_ids.push(serviceTypeId);
      }
    });
  }

  function renderServiceTypes() {
    sync.renderFilteredServiceTypes({
      catalog,
      productRoot: document,
      productSelector: 'input[name="products"]:checked',
      serviceTypeContainer,
      serviceTypeCheckboxClass: 'service-type-cb',
      serviceTypeName: 'service_types',
      hintEl: serviceTypeHint,
      selectedServiceTypeIds,
    });
    attachServiceTypeEditButtons();
  }

  function attachServiceTypeEditButtons() {
    serviceTypeContainer?.querySelectorAll('label').forEach((label) => {
      const cb = label.querySelector('.service-type-cb');
      if (!cb || label.querySelector('.service-type-edit-btn')) return;
      const id = parseInt(cb.value, 10);
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className =
        'service-type-edit-btn ml-auto p-1 text-slate-400 hover:text-brand-600 hover:bg-white rounded-lg opacity-70 group-hover:opacity-100 transition-all shrink-0';
      btn.title = 'Arıza tipini düzenle';
      btn.setAttribute('aria-label', 'Düzenle');
      btn.innerHTML =
        '<i data-lucide="pencil" class="w-3.5 h-3.5 pointer-events-none"></i>';
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const item = catalog.service_types.find((s) => s.id === id);
        if (item) openQuickModal('service_type', item);
      });
      label.appendChild(btn);
    });
    if (window.lucide) lucide.createIcons();
  }

  function bindServiceTypeContainer() {
    serviceTypeContainer?.addEventListener('change', (e) => {
      if (e.target.classList.contains('service-type-cb')) {
        const id = parseInt(e.target.value, 10);
        if (e.target.checked) selectedServiceTypeIds.add(id);
        else selectedServiceTypeIds.delete(id);
      }
    });
  }

  function refreshSelectOptions(selectEl, items, currentValue) {
    if (!selectEl) return;
    const val = currentValue || selectEl.value;
    selectEl.innerHTML = '';
    items.forEach((item) => {
      const opt = document.createElement('option');
      opt.value = item.id;
      opt.textContent = item.name;
      if (String(item.id) === String(val)) opt.selected = true;
      selectEl.appendChild(opt);
    });
  }

  const quickLabels = {
    status: 'durum',
    priority: 'öncelik',
    product: 'ürün',
    service_type: 'arıza / servis tipi',
  };

  function setQuickModalColor(hex) {
    const hidden = document.querySelector('#quickOptionModal .color-picker-value');
    if (hidden) hidden.value = hex || '#3b82f6';
    const hexInput = document.querySelector('#quickOptionModal .cp-hex');
    const native = document.querySelector('#quickOptionModal .cp-native');
    if (hexInput) hexInput.value = (hex || '#3b82f6').toUpperCase();
    if (native) native.value = hex || '#3b82f6';
    const preview = document.querySelector('#quickOptionModal .cp-preview');
    if (preview) preview.style.backgroundColor = hex || '#3b82f6';
  }

  function fillServiceTypeProductCheckboxes(item = null) {
    const box = document.getElementById('quickServiceTypeProducts');
    if (!box) return;
    const checkedProductIds = getCheckedProductIds();
    const selectedProductIds = new Set(item?.product_ids || []);
    const products = catalog.products.filter((p) => checkedProductIds.includes(p.id));

    if (!products.length) {
      box.innerHTML =
        '<p class="text-xs text-amber-700 py-1">Önce formda en az bir ürün seçin; ardından bu tipi ürünlere bağlayabilirsiniz.</p>';
      return;
    }

    box.innerHTML = products
      .map(
        (p) => `<label class="flex items-center gap-2 text-sm py-1">
        <input type="checkbox" class="quick-st-product-cb rounded" value="${p.id}" ${
          selectedProductIds.has(p.id) || (!item && checkedProductIds.includes(p.id))
            ? 'checked'
            : ''
        }>
        <span class="w-2 h-2 rounded-full shrink-0" style="background-color:${p.color}"></span>${p.name}</label>`
      )
      .join('');
  }

  function openQuickModal(kind, item = null) {
    const modal = document.getElementById('quickOptionModal');
    const title = document.getElementById('quickOptionModalTitle');
    const colorWrap = document.getElementById('quickOptionColorWrap');
    const productStWrap = document.getElementById('quickOptionProductTypesWrap');
    const serviceTypeProductsWrap = document.getElementById('quickOptionServiceTypeProductsWrap');
    document.getElementById('quickOptionType').value = kind;
    document.getElementById('quickOptionId').value = item ? String(item.id) : '';
    document.getElementById('quickOptionName').value = item ? item.name : '';

    const label = quickLabels[kind] || 'seçenek';
    title.textContent = item ? `${label} düzenle` : `Yeni ${label}`;
    colorWrap.classList.toggle('hidden', kind === 'whatsapp');
    productStWrap.classList.toggle('hidden', kind !== 'product');
    serviceTypeProductsWrap?.classList.toggle('hidden', kind !== 'service_type');

    if (kind === 'product') {
      const box = document.getElementById('quickProductServiceTypes');
      const selectedSt = item?.service_type_ids || [];
      box.innerHTML = catalog.service_types
        .map(
          (st) => `<label class="flex items-center gap-2 text-sm py-1">
        <input type="checkbox" class="quick-product-st-cb rounded" value="${st.id}" ${selectedSt.includes(st.id) ? 'checked' : ''}>
        <span class="w-2 h-2 rounded-full" style="background-color:${st.color}"></span>${st.name}</label>`
        )
        .join('');
    }

    if (kind === 'service_type') {
      fillServiceTypeProductCheckboxes(item);
    }

    setQuickModalColor(item?.color || '#3b82f6');
    if (window.initColorPickers) window.initColorPickers(modal);
    modal.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
  }

  function openQuickEdit(kind) {
    let item = null;
    if (kind === 'status') {
      const id = parseInt(statusSelect?.value, 10);
      item = catalog.statuses.find((s) => s.id === id);
      if (!item) return alert('Önce düzenlemek istediğiniz durumu seçin.');
    } else if (kind === 'priority') {
      const id = parseInt(prioritySelect?.value, 10);
      item = catalog.priorities.find((p) => p.id === id);
      if (!item) return alert('Önce düzenlemek istediğiniz önceliği seçin.');
    } else if (kind === 'product') {
      const checked = document.querySelectorAll('input[name="products"]:checked');
      if (checked.length !== 1) {
        return alert('Ürün düzenlemek için tam olarak bir ürün işaretleyin.');
      }
      const id = parseInt(checked[0].value, 10);
      item = catalog.products.find((p) => p.id === id);
    } else if (kind === 'service_type') {
      const checkedBoxes = serviceTypeContainer?.querySelectorAll('.service-type-cb:checked') || [];
      if (checkedBoxes.length === 1) {
        const id = parseInt(checkedBoxes[0].value, 10);
        item = catalog.service_types.find((s) => s.id === id);
      } else if (selectedServiceTypeIds.size === 1) {
        item = catalog.service_types.find((s) => s.id === [...selectedServiceTypeIds][0]);
      }
      if (!item) {
        return alert(
          'Arıza tipi düzenlemek için listeden bir tip işaretleyin veya satırdaki kalem simgesine tıklayın.'
        );
      }
    }
    if (!item) return alert('Kayıt bulunamadı.');
    openQuickModal(kind, item);
  }

  async function saveQuickOption() {
    const kind = document.getElementById('quickOptionType').value;
    const id = document.getElementById('quickOptionId').value;
    const name = document.getElementById('quickOptionName').value.trim();
    const color =
      document.querySelector('#quickOptionModal .color-picker-value')?.value || '#3b82f6';
    if (!name) return alert('İsim girin');

    const body = { type: kind, name, color };
    if (kind === 'product') {
      body.service_type_ids = Array.from(
        document.querySelectorAll('.quick-product-st-cb:checked')
      ).map((cb) => parseInt(cb.value, 10));
    }
    if (kind === 'service_type') {
      body.product_ids = Array.from(
        document.querySelectorAll('.quick-st-product-cb:checked')
      ).map((cb) => parseInt(cb.value, 10));
    }

    const base = window.AYARLAR_BASE || '/ayarlar';
    const url = id ? `${base}/api/options/quick-update/` : `${base}/api/options/quick-create/`;
    if (id) {
      body.id = parseInt(id, 10);
    }

    const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!data.ok) {
      alert(data.error || 'Kayıt başarısız');
      return;
    }

    if (window.GY_MARK_LOCAL_SAVE) window.GY_MARK_LOCAL_SAVE();

    const item = data.item;
    const catalogKey = {
      status: 'statuses',
      priority: 'priorities',
      product: 'products',
      service_type: 'service_types',
    }[kind];

    if (id && catalogKey) {
      const list = catalog[catalogKey];
      const idx = list.findIndex((x) => x.id === item.id);
      if (idx >= 0) list[idx] = { ...list[idx], ...item };
      else list.push(item);
    } else if (kind === 'status') {
      catalog.statuses.push(item);
    } else if (kind === 'priority') {
      catalog.priorities.push(item);
    } else if (kind === 'product') {
      catalog.products.push(item);
    } else if (kind === 'service_type') {
      mergeServiceTypeIntoCatalog(item);
    }

    if (kind === 'service_type' && body.product_ids?.length) {
      linkServiceTypeToProducts(item.id, body.product_ids);
    }

    const script = document.getElementById('optionsCatalogData');
    if (script) script.textContent = JSON.stringify(catalog);

    if (kind === 'status') {
      refreshSelectOptions(statusSelect, catalog.statuses, item.id);
    } else if (kind === 'priority') {
      refreshSelectOptions(prioritySelect, catalog.priorities, item.id);
    } else if (kind === 'product' || kind === 'service_type') {
      if (kind === 'service_type' && !id) {
        selectedServiceTypeIds.add(item.id);
      }
      renderServiceTypes();
    }

    document.getElementById('quickOptionModal').classList.add('hidden');
    if (typeof updateProductStyling === 'function') updateProductStyling();
    if (window.lucide) lucide.createIcons();
  }

  function updateProductCheckboxLabel(product) {
    const cb = document.querySelector(`input[name="products"][value="${product.id}"]`);
    if (!cb) return;
    const label = cb.closest('label');
    const nameSpan = label?.querySelector('span.text-sm, span:last-child');
    const dot = label?.querySelector('.product-color-dot');
    if (dot) dot.style.backgroundColor = product.color;
    if (nameSpan) nameSpan.textContent = product.name;
  }

  function enrichProductCheckboxes() {
    document.querySelectorAll('#productCheckboxesContainer input[name="products"]').forEach((cb) => {
      const product = catalog.products.find((p) => p.id === parseInt(cb.value, 10));
      if (!product) return;
      const label = cb.closest('label');
      if (!label || label.querySelector('.product-color-dot')) return;
      const dot = document.createElement('span');
      dot.className = 'w-2.5 h-2.5 rounded-full shrink-0 product-color-dot';
      dot.style.backgroundColor = product.color;
      const textSpan = label.querySelector('span.text-sm') || label.querySelector('span');
      if (textSpan) label.insertBefore(dot, textSpan);
      else label.appendChild(dot);
    });
  }

  productContainer?.addEventListener('change', (e) => {
    if (e.target.name === 'products') {
      renderServiceTypes();
      if (typeof updateProductStyling === 'function') updateProductStyling();
    }
  });

  bindServiceTypeContainer();
  enrichProductCheckboxes();
  renderServiceTypes();

  document.querySelectorAll('[data-quick-add]').forEach((btn) => {
    btn.addEventListener('click', () => openQuickModal(btn.dataset.quickAdd));
  });
  document.querySelectorAll('[data-quick-edit]').forEach((btn) => {
    btn.addEventListener('click', () => openQuickEdit(btn.dataset.quickEdit));
  });
  document.getElementById('quickOptionSaveBtn')?.addEventListener('click', saveQuickOption);
  document.getElementById('quickOptionCancelBtn')?.addEventListener('click', () => {
    document.getElementById('quickOptionModal').classList.add('hidden');
  });

  window.serviceFormCatalog = catalog;
  window.refreshServiceTypesForProducts = renderServiceTypes;
})();
