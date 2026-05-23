/**
 * Ürün seçimine göre arıza/servis tipi listesini filtreler (paylaşımlı katalog).
 */
(function (global) {
  function resolveAllowedServiceTypeIds(catalog, productIds) {
    if (!productIds.length) {
      return { ids: null, mode: 'none', message: 'Önce en az bir ürün seçin.' };
    }
    const union = new Set();
    let anyMapping = false;
    for (const pid of productIds) {
      const product = catalog.products.find((p) => p.id === pid);
      if (!product?.service_type_ids?.length) {
        return {
          ids: null,
          mode: 'all_fallback',
          message:
            'Seçili ürünlerden en az birinde arıza tipi tanımlı değil; tüm tipler gösteriliyor.',
        };
      }
      anyMapping = true;
      product.service_type_ids.forEach((id) => union.add(id));
    }
    if (!anyMapping) {
      return {
        ids: null,
        mode: 'all_fallback',
        message: 'Seçili ürünlerde tanımlı arıza tipi yok; tüm tipler gösteriliyor.',
      };
    }
    return {
      ids: union,
      mode: 'filtered',
      message: `${union.size} arıza tipi bu ürün(ler) için tanımlı.`,
    };
  }

  function getServiceTypeColor(catalog, serviceTypeId, selectedProductIds) {
    for (const pid of selectedProductIds) {
      const product = catalog.products.find((p) => p.id === pid);
      if (product?.service_type_ids?.includes(serviceTypeId)) return product.color;
    }
    const fallbackProduct = catalog.products.find((p) =>
      p.service_type_ids?.includes(serviceTypeId)
    );
    if (fallbackProduct) return fallbackProduct.color;
    return catalog.service_types.find((st) => st.id === serviceTypeId)?.color || '#3b82f6';
  }

  function collectProductIds(root, selector) {
    return Array.from(root.querySelectorAll(selector))
      .filter((el) => el.type !== 'checkbox' || el.checked)
      .map((el) => parseInt(el.value, 10))
      .filter((n) => !Number.isNaN(n));
  }

  function renderFilteredServiceTypes(opts) {
    const {
      catalog,
      productRoot = document,
      productSelector = 'input[name="products"]:checked',
      serviceTypeContainer,
      serviceTypeCheckboxClass,
      serviceTypeName = 'service_types',
      hintEl,
      selectedServiceTypeIds,
      labelClass = 'flex items-center gap-2 p-2 hover:bg-white rounded-lg transition-colors cursor-pointer group border border-transparent hover:border-slate-200',
      emptyClass = 'col-span-full text-sm text-amber-600 font-medium py-2',
    } = opts;

    if (!serviceTypeContainer || !catalog) return;

    const pids = collectProductIds(productRoot, productSelector);
    const { ids, mode, message } = resolveAllowedServiceTypeIds(catalog, pids);

    let list = catalog.service_types;
    if (ids && mode === 'filtered') {
      list = catalog.service_types.filter((st) => ids.has(st.id));
    }

    const validIds = new Set(list.map((st) => st.id));
    [...selectedServiceTypeIds].forEach((id) => {
      if (!validIds.has(id)) selectedServiceTypeIds.delete(id);
    });

    serviceTypeContainer.innerHTML = '';
    if (!pids.length) {
      serviceTypeContainer.innerHTML = `<p class="${emptyClass}">Arıza tipleri için önce ürün seçin.</p>`;
    } else if (!list.length) {
      serviceTypeContainer.innerHTML =
        '<p class="col-span-full text-sm text-slate-500 py-2">Gösterilecek arıza tipi yok.</p>';
    } else {
      list.forEach((st) => {
        const label = document.createElement('label');
        label.className = labelClass;
        const checked = selectedServiceTypeIds.has(st.id);
        const dotColor = getServiceTypeColor(catalog, st.id, pids);
        label.innerHTML = `
          <input type="checkbox" class="${serviceTypeCheckboxClass} rounded border-slate-300 text-brand-600"
            name="${serviceTypeName}" value="${st.id}" ${checked ? 'checked' : ''}>
          <span class="w-2 h-2 rounded-full shrink-0" style="background-color:${dotColor}"></span>
          <span class="text-sm text-slate-600">${st.name}</span>`;
        serviceTypeContainer.appendChild(label);
      });
    }

    if (hintEl) {
      hintEl.textContent = message;
      hintEl.className =
        'text-xs font-medium ' + (mode === 'none' ? 'text-amber-600' : 'text-slate-500');
    }
  }

  global.GyProductServiceTypeSync = {
    resolveAllowedServiceTypeIds,
    getServiceTypeColor,
    renderFilteredServiceTypes,
    collectProductIds,
  };
})(window);
