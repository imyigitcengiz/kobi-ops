from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import TemplateView

from core_settings.backup import (
    backup_status_summary,
    export_backup_response,
    export_sqlite_response,
    import_backup_file,
    import_sqlite_file,
)
from core_settings.forms import AISettingsForm
from core_settings.models import SiteSettings
from customers.models import Customer
from services.models import ServiceRecord


class SettingsAISettingsView(TemplateView):
    template_name = 'settings/ai_settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        settings = SiteSettings.objects.first()
        context['ai_form'] = AISettingsForm(instance=settings)
        context['ai_enabled'] = bool(settings and settings.ai_chat_enabled)
        return context

    def post(self, request, *args, **kwargs):
        settings = SiteSettings.objects.first()
        if not settings:
            settings = SiteSettings.objects.create(site_name='CoolOPS')
        form = AISettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'AI ayarları kaydedildi.')
        else:
            messages.error(request, f'Ayarlar kaydedilemedi: {form.errors.as_text()}')
        return redirect('settings_ai_settings')


class SettingsAIReportingView(TemplateView):
    template_name = 'settings/ai_reporting.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        settings = SiteSettings.objects.first()
        context['site_settings'] = settings
        context['stats'] = {
            'total_customers': Customer.objects.count(),
            'total_services': ServiceRecord.objects.count(),
            'product_count': ServiceRecord.objects.values('products').distinct().count(),
        }
        return context


class SettingsSystemBackupView(TemplateView):
    template_name = 'settings/system_backup.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['backup_status'] = backup_status_summary()
        return context

    def post(self, request, *args, **kwargs):
        if 'export_backup' in request.POST:
            try:
                return export_backup_response()
            except Exception as exc:
                messages.error(request, f'Yedekleme sırasında hata oluştu: {exc}')
                return redirect('settings_system_backup')

        if 'import_backup' in request.POST:
            ok, msg = import_backup_file(request.FILES.get('backup_file'))
            if ok:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            return redirect('settings_system_backup')

        if 'export_sqlite' in request.POST:
            try:
                return export_sqlite_response()
            except Exception as exc:
                messages.error(request, f'SQLite indirme hatası: {exc}')
                return redirect('settings_system_backup')

        if 'import_sqlite' in request.POST:
            ok, msg = import_sqlite_file(request.FILES.get('sqlite_file'))
            if ok:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            return redirect('settings_system_backup')

        return redirect('settings_system_backup')
