from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from common.decorators import permission_required
from tools.media_library import CATEGORY_LABELS, delete_media_item, scan_media_library


class ToolsMediaLibraryView(TemplateView):
    template_name = 'tools/media_library.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '')
        category = self.request.GET.get('category', '')
        kind = self.request.GET.get('kind', '')
        try:
            page = int(self.request.GET.get('page', '1'))
        except ValueError:
            page = 1

        data = scan_media_library(
            query=query,
            category=category,
            kind=kind,
            page=page,
        )
        context.update(data)
        context['filter_q'] = query
        context['filter_category'] = category
        context['filter_kind'] = kind
        context['categories'] = CATEGORY_LABELS
        context['can_delete_media'] = (
            self.request.user.is_superuser
            or self.request.user.has_perm_codename('tools.media_delete')
        )
        return context


class ToolsMediaDeleteView(View):
    @permission_required('tools.media_delete')
    def post(self, request):
        relpath = (request.POST.get('relpath') or '').strip()
        record_type = (request.POST.get('record_type') or '').strip() or None
        record_id_raw = request.POST.get('record_id', '').strip()
        record_id = int(record_id_raw) if record_id_raw.isdigit() else None

        if not relpath:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': False, 'error': 'Dosya yolu gerekli.'}, status=400)
            messages.error(request, 'Dosya yolu gerekli.')
            return redirect('tools_media_library')

        ok, msg = delete_media_item(
            record_type=record_type,
            record_id=record_id,
            relpath=relpath,
        )
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': ok, 'message': msg}, status=200 if ok else 400)

        if ok:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
        return redirect(request.POST.get('next') or 'tools_media_library')
