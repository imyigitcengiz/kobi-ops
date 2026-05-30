from decimal import Decimal, InvalidOperation

from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.views.generic import TemplateView
from django.db.models import Count, Q
from django.utils.dateparse import parse_date
from services.models import ServiceRecord
from customers.models import Customer
from core_settings.models import SiteSettings, StatusOption, PriorityOption
from django.utils import timezone
from datetime import timedelta
import json
from django.http import JsonResponse
import logging

import openai
from django.views.decorators.http import require_POST

from common.decorators import json_auth_required, permission_required
from .service_report import build_service_dashboard_report

logger = logging.getLogger(__name__)

class PublicLandingView(TemplateView):
    """Herkese açık tanıtım sayfası — girişten önce."""

    template_name = 'landing.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from common.landing_content import DEFAULT_LANDING_VERTICAL, LANDING_VERTICAL_COPY
        from common.module_catalog import installation_verticals
        from common.profile_apps import profile_apps_for_vertical, profile_integrations_for_vertical

        context = super().get_context_data(**kwargs)
        verticals = installation_verticals()
        selected = self.request.GET.get('v', DEFAULT_LANDING_VERTICAL)
        if not any(v['slug'] == selected for v in verticals):
            selected = DEFAULT_LANDING_VERTICAL

        apps_by_vertical = {}
        for v in verticals:
            slug = v['slug']
            apps = profile_apps_for_vertical(slug) + profile_integrations_for_vertical(slug)
            apps.sort(key=lambda a: (a.get('sort', 99), a['name']))
            apps_by_vertical[slug] = apps

        context['landing_verticals'] = verticals
        context['landing_selected_vertical'] = selected
        context['landing_vertical_copy'] = LANDING_VERTICAL_COPY.get(
            selected, LANDING_VERTICAL_COPY[DEFAULT_LANDING_VERTICAL],
        )
        context['landing_apps_by_vertical'] = apps_by_vertical
        context['landing_apps'] = apps_by_vertical.get(selected, [])
        return context


class HomeView(TemplateView):
    """Giriş sonrası modül kısayolları."""

    template_name = 'home.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            from common.module_runtime import is_profile_setup_complete, user_can_manage_profile_setup
            if user_can_manage_profile_setup(request.user) and not is_profile_setup_complete():
                return redirect('profile_setup')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from common.permissions import can_access_accounting
        from core_settings.accounting_summary import build_accounting_panel_context
        from analytics.panel_summary import build_services_panel_context, build_outreach_panel_context

        context = super().get_context_data(**kwargs)
        user = self.request.user
        if not user.is_authenticated:
            return context
        if can_access_accounting(user):
            context.update(build_accounting_panel_context(user))
        if user.has_perm_codename('access.services'):
            context.update(build_services_panel_context(user))
        if user.has_perm_codename('access.outreach'):
            context.update(build_outreach_panel_context(user))
        from common.module_runtime import (
            build_profile_hub_context,
            build_profile_panel_apps,
            get_primary_vertical_slug,
            is_profile_app_enabled,
            panel_section_visible,
            profile_app_available_for_nav,
            vertical_by_slug,
        )
        from agency.summary import build_agency_panel_context

        vertical = get_primary_vertical_slug()
        context.update(build_profile_hub_context(user, query=''))
        context['panel_vertical'] = vertical_by_slug(vertical)
        context['profile_panel_apps'] = build_profile_panel_apps(user)
        context['can_manage_modules'] = (
            user.is_superuser or user.has_perm_codename('access.settings')
        )
        if (
            vertical == 'agency'
            and is_profile_app_enabled('app.agency.retainer_studio')
            and profile_app_available_for_nav(user, 'app.agency.retainer_studio')
        ):
            context.update(build_agency_panel_context(user))
        if can_access_accounting(user) and panel_section_visible('accounting'):
            context.update(build_accounting_panel_context(user))
        if panel_section_visible('services') and user.has_perm_codename('access.services'):
            context.update(build_services_panel_context(user))
        if panel_section_visible('outreach') and user.has_perm_codename('access.outreach'):
            context.update(build_outreach_panel_context(user))
        return context


class ModuleHubView(TemplateView):
    """Odoo tarzı modül merkezi — sektör filtresi ve kurulum aç/kapa."""

    template_name = 'common/module_hub.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from common.module_runtime import build_profile_hub_context

        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '')
        context.update(build_profile_hub_context(self.request.user, query=query))
        context['can_manage_modules'] = (
            self.request.user.is_superuser
            or self.request.user.has_perm_codename('access.settings')
        )
        return context

    def post(self, request, *args, **kwargs):
        from common.module_catalog import is_installation_vertical, vertical_by_slug
        from common.profile_apps import profile_app_by_slug
        from common.module_runtime import apply_vertical_preset, get_enabled_profile_slugs

        if not (request.user.is_superuser or request.user.has_perm_codename('access.settings')):
            messages.error(request, 'Modül ayarları için yetkiniz yok.')
            return redirect('module_hub')

        settings = SiteSettings.objects.first()
        if not settings:
            settings = SiteSettings.objects.create()

        redirect_qs = ''
        if request.GET.get('q'):
            redirect_qs = f'?q={request.GET.get("q")}'

        if 'apply_vertical_preset' in request.POST:
            slug = request.POST.get('vertical_slug', '').strip()
            if is_installation_vertical(slug) and vertical_by_slug(slug):
                applied = apply_vertical_preset(slug)
                messages.success(
                    request,
                    f'{vertical_by_slug(slug)["name"]} uygulama paketi kuruldu ({len(applied)} uygulama).',
                )
            else:
                messages.error(request, 'Geçersiz profil. Yalnızca KOBİ veya Ajans seçilebilir.')
        elif 'set_primary_vertical' in request.POST:
            slug = request.POST.get('vertical_slug', '').strip()
            if is_installation_vertical(slug) and vertical_by_slug(slug):
                apply_vertical_preset(slug)
                messages.success(
                    request,
                    f'Kurulum profili "{vertical_by_slug(slug)["name"]}" olarak ayarlandı.',
                )
            else:
                messages.error(request, 'Geçersiz profil. Yalnızca KOBİ veya Ajans seçilebilir.')
        elif 'toggle_profile_app' in request.POST:
            slug = request.POST.get('app_slug', '').strip()
            app = profile_app_by_slug(slug)
            if not app:
                messages.error(request, 'Geçersiz uygulama.')
            else:
                enabled = list(get_enabled_profile_slugs())
                if slug in enabled:
                    if len(enabled) <= 1:
                        messages.error(request, 'En az bir uygulama açık kalmalı.')
                    else:
                        enabled.remove(slug)
                        settings.enabled_module_slugs = enabled
                        settings.save(update_fields=['enabled_module_slugs'])
                        messages.info(request, f'"{app["name"]}" kapatıldı.')
                else:
                    enabled.append(slug)
                    settings.enabled_module_slugs = enabled
                    settings.save(update_fields=['enabled_module_slugs'])
                    messages.success(request, f'"{app["name"]}" açıldı.')
        elif 'toggle_module' in request.POST or 'toggle_particle' in request.POST:
            messages.info(request, 'Lütfen uygulama kartlarından aç/kapa kullanın.')

        from django.urls import reverse
        return redirect(f"{reverse('module_hub')}{redirect_qs}")


class ProfileSetupView(TemplateView):
    """İlk kurulum — sektör profili ve uygulama paketi seçimi."""

    template_name = 'common/profile_setup.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        from common.module_runtime import is_profile_setup_complete, user_can_manage_profile_setup
        if not user_can_manage_profile_setup(request.user):
            messages.info(request, 'Kurulum profili yalnızca yönetici tarafından ayarlanır.')
            return redirect('home')
        if is_profile_setup_complete() and request.method != 'POST':
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from common.module_catalog import installation_verticals
        from common.profile_apps import profile_apps_for_vertical, profile_integrations_for_vertical

        context = super().get_context_data(**kwargs)
        verticals = []
        preview = {}
        for v in installation_verticals():
            slug = v['slug']
            apps = profile_apps_for_vertical(slug) + profile_integrations_for_vertical(slug)
            apps.sort(key=lambda a: (a.get('sort', 99), a['name']))
            preview[slug] = apps
            vd = dict(v)
            vd['app_count'] = len(apps)
            verticals.append(vd)
        context['setup_verticals'] = verticals
        context['setup_apps_preview'] = preview
        context['setup_selected'] = self.request.GET.get('v', 'kobi')
        return context

    def post(self, request, *args, **kwargs):
        from common.module_catalog import is_installation_vertical, vertical_by_slug
        from common.module_runtime import apply_vertical_preset, mark_profile_setup_complete

        slug = (request.POST.get('vertical_slug') or 'kobi').strip()
        if not is_installation_vertical(slug):
            messages.error(request, 'Geçersiz kurulum profili.')
            return redirect('profile_setup')
        v = vertical_by_slug(slug)
        apply_vertical_preset(slug)
        mark_profile_setup_complete()
        messages.success(request, f'{v["name"]} profili uygulandı. Uygulamalarınız hazır.')
        return redirect('home')


class ProfileAppHubView(TemplateView):
    """Profil uygulaması mini hub — KPI + hızlı bağlantılar."""

    template_name = 'common/profile_app_hub.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        from common.profile_apps import profile_app_by_slug
        from common.module_runtime import is_profile_app_enabled, user_can_access_profile_app

        app_slug = kwargs.get('app_slug', '')
        app = profile_app_by_slug(app_slug)
        if not app or not is_profile_app_enabled(app_slug):
            messages.warning(request, 'Bu uygulama kurulu değil veya kapalı.')
            return redirect('module_hub')
        if not user_can_access_profile_app(request.user, app):
            messages.error(request, 'Bu uygulamaya erişim yetkiniz yok.')
            return redirect('home')
        self.profile_app = app
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from common.module_catalog import vertical_by_slug
        from common.module_runtime import build_profile_app_record, get_primary_vertical_slug
        from common.profile_app_hub import build_profile_app_hub_metrics, profile_app_quick_links

        context = super().get_context_data(**kwargs)
        app = self.profile_app
        user = self.request.user
        record = build_profile_app_record(user, app)
        context['app'] = record
        context['app_metrics'] = build_profile_app_hub_metrics(user, app)
        context['app_quick_links'] = profile_app_quick_links(app, user)
        context['panel_vertical'] = vertical_by_slug(get_primary_vertical_slug())
        return context


class DashboardView(TemplateView):
    template_name = 'services_dashboard/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report = build_service_dashboard_report()
        context.update(report)
        context['total_customers'] = Customer.objects.count()
        context['statuses'] = StatusOption.objects.order_by('sort_order', 'name')
        context['priorities'] = PriorityOption.objects.order_by('name')
        context['monthly_chart'] = json.dumps({
            'labels': report['monthly_labels'],
            'active': report['monthly_active'],
            'pending': report['monthly_pending'],
            'closed': report['monthly_closed'],
            'cancelled': report['monthly_cancelled'],
            'total': report['monthly_total'],
        }, ensure_ascii=False)
        context['product_chart'] = json.dumps({
            'labels': report['product_labels'],
            'counts': report['product_counts'],
            'colors': report['product_colors'],
        }, ensure_ascii=False)
        return context

class AIPanelView(TemplateView):
    template_name = 'services_dashboard/analytics/ai_panel.html'

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

@require_POST
@json_auth_required
@permission_required('tools.ai')
def ai_chat_view(request):
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '')
        
        settings = SiteSettings.objects.first()
        if not settings or not settings.ai_chat_enabled:
            return JsonResponse({'error': 'AI Chat is disabled'}, status=403)
            
        # Prepare context for AI
        total_customers = Customer.objects.count()
        total_services = ServiceRecord.objects.count()
        recent_services = ServiceRecord.objects.order_by('-created_at')[:5]
        service_summary = "\n".join([f"- {s.customer.name}: {s.status.name} ({s.priority.name})" for s in recent_services])
        
        system_context = f"""
        {settings.ai_system_prompt}
        
        Sistem Bilgileri:
        - Toplam Müşteri: {total_customers}
        - Toplam Servis Kaydı: {total_services}
        
        Son Servis Kayıtları:
        {service_summary}
        
        Kullanıcıya yardımcı ol, verileri analiz et ve istendiğinde tavsiyelerde bulun.
        """
        
        response_text = ""
        
        # Try Google AI (Gemini) first if key exists
        if settings.google_api_key:
            try:
                from google import genai

                client = genai.Client(api_key=settings.google_api_key)
                chat_response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=f"{system_context}\n\nKullanıcı: {user_message}",
                )
                response_text = chat_response.text
            except Exception as e:
                logger.warning('Gemini error: %s', e)
                
        # If Gemini failed or no key, try OpenAI
        if not response_text and settings.openai_api_key:
            try:
                client = openai.OpenAI(api_key=settings.openai_api_key)
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_context},
                        {"role": "user", "content": user_message}
                    ]
                )
                response_text = completion.choices[0].message.content
            except Exception as e:
                logger.warning('OpenAI error: %s', e)
                
        if not response_text:
            return JsonResponse({'error': 'AI providers failed or keys missing'}, status=500)
            
        return JsonResponse({'message': response_text})
        
    except Exception:
        logger.exception('AI chat request failed')
        return JsonResponse({'error': 'AI isteği işlenemedi.'}, status=500)
