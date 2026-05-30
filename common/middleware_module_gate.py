"""Kapalı modül URL'lerini engelle — Modül Merkezi'ne yönlendir."""

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from common.module_catalog import MODULE_STATUS_ACTIVE, MODULE_STATUS_BETA, module_by_slug
from common.module_runtime import is_module_enabled, resolve_path_module_slug


class ModuleInstallMiddleware:
    """Kurulu olmayan uygulama route'larına erişimi keser."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_superuser:
            blocked = self._blocked_response(request)
            if blocked is not None:
                return blocked
        return self.get_response(request)

    def _blocked_response(self, request):
        slug = resolve_path_module_slug(request.path)
        if not slug:
            return None
        mod = module_by_slug(slug)
        if not mod or mod['status'] not in (MODULE_STATUS_ACTIVE, MODULE_STATUS_BETA):
            return None
        if is_module_enabled(slug):
            return None
        messages.warning(
            request,
            f'{mod["name"]} modülü kurulu değil. Modül Merkezi\'nden açabilirsiniz.',
        )
        try:
            return redirect(reverse('module_hub') + f'?highlight={slug}')
        except Exception:
            return redirect('module_hub')
