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
        from common.module_catalog import MODULES, MODULE_STATUS_ACTIVE, MODULE_STATUS_ROADMAP, all_verticals

        context = super().get_context_data(**kwargs)
        context['landing_verticals'] = [v for v in all_verticals() if v['slug'] != 'universal']
        from common.module_catalog import MODULE_STATUS_BETA
        context['landing_active_modules'] = [
            m for m in MODULES
            if m['status'] in (MODULE_STATUS_ACTIVE, MODULE_STATUS_BETA)
        ]
        context['landing_roadmap_modules'] = [m for m in MODULES if m['status'] == MODULE_STATUS_ROADMAP]
        return context


class HomeView(TemplateView):
    """Giriş sonrası modül kısayolları."""

    template_name = 'home.html'

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
        from common.module_runtime import module_available_for_nav
        if module_available_for_nav(user, 'agency_suite'):
            from analytics.agency_summary import build_agency_panel_context
            context.update(build_agency_panel_context(user))
        from common.module_runtime import (
            build_module_hub_context,
            get_primary_vertical_slug,
            panel_section_visible,
            recommended_modules_for_vertical,
            vertical_by_slug,
        )
        vertical = self.request.GET.get('vertical') or get_primary_vertical_slug()
        if not vertical_by_slug(vertical):
            vertical = get_primary_vertical_slug()
        hub_ctx = build_module_hub_context(user, vertical_filter=None)
        context.update(hub_ctx)
        context['panel_vertical'] = vertical_by_slug(vertical)
        context['panel_vertical_recommended'] = recommended_modules_for_vertical(vertical)
        context['panel_show_contact'] = panel_section_visible('contact')
        context['panel_show_services'] = panel_section_visible('services')
        context['panel_show_accounting'] = panel_section_visible('accounting')
        context['panel_show_outreach'] = panel_section_visible('outreach')
        context['panel_show_agency'] = panel_section_visible('agency')
        return context


class ModuleHubView(TemplateView):
    """Odoo tarzı modül merkezi — sektör filtresi ve kurulum aç/kapa."""

    template_name = 'common/module_hub.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from common.module_runtime import build_module_hub_context

        context = super().get_context_data(**kwargs)
        vertical = self.request.GET.get('vertical', 'all')
        query = self.request.GET.get('q', '')
        context.update(build_module_hub_context(self.request.user, vertical_filter=vertical, query=query))
        context['can_manage_modules'] = (
            self.request.user.is_superuser
            or self.request.user.has_perm_codename('access.settings')
        )
        return context

    def post(self, request, *args, **kwargs):
        from common.module_catalog import (
            module_by_slug,
            vertical_by_slug,
            MODULE_STATUS_ACTIVE,
            MODULE_STATUS_BETA,
            vertical_preset_modules,
        )
        from common.module_runtime import apply_vertical_preset, get_enabled_module_slugs

        if not (request.user.is_superuser or request.user.has_perm_codename('access.settings')):
            messages.error(request, 'Modül ayarları için yetkiniz yok.')
            return redirect('module_hub')

        settings = SiteSettings.objects.first()
        if not settings:
            settings = SiteSettings.objects.create()

        redirect_qs = ''
        if request.GET.get('vertical'):
            redirect_qs = f'?vertical={request.GET.get("vertical")}'
        if request.GET.get('q'):
            redirect_qs += ('&' if redirect_qs else '?') + f'q={request.GET.get("q")}'

        if 'apply_vertical_preset' in request.POST:
            slug = request.POST.get('vertical_slug', '').strip()
            if vertical_by_slug(slug):
                applied = apply_vertical_preset(slug)
                names = ', '.join(applied)
                messages.success(
                    request,
                    f'{vertical_by_slug(slug)["name"]} paketi uygulandı: {names}',
                )
            else:
                messages.error(request, 'Geçersiz sektör.')
        elif 'set_primary_vertical' in request.POST:
            slug = request.POST.get('vertical_slug', '').strip()
            if vertical_by_slug(slug):
                settings.primary_vertical_slug = slug
                settings.save(update_fields=['primary_vertical_slug'])
                preset = vertical_preset_modules(slug)
                messages.success(
                    request,
                    f'Birincil sektör güncellendi. Önerilen paket: {", ".join(preset)}',
                )
            else:
                messages.error(request, 'Geçersiz sektör.')
        elif 'toggle_module' in request.POST:
            slug = request.POST.get('module_slug', '').strip()
            mod = module_by_slug(slug)
            if not mod or mod['status'] not in (MODULE_STATUS_ACTIVE, MODULE_STATUS_BETA):
                messages.error(request, 'Bu modül henüz kurulamaz.')
            else:
                enabled = list(get_enabled_module_slugs())
                if slug in enabled:
                    if len(enabled) <= 1:
                        messages.error(request, 'En az bir modül açık kalmalı.')
                    else:
                        enabled.remove(slug)
                        settings.enabled_module_slugs = enabled
                        settings.save(update_fields=['enabled_module_slugs'])
                        messages.info(request, f'{mod["name"]} modülü kapatıldı (panelden gizlenir).')
                else:
                    if slug not in enabled:
                        enabled.append(slug)
                    settings.enabled_module_slugs = enabled
                    settings.save(update_fields=['enabled_module_slugs'])
                    messages.success(request, f'{mod["name"]} modülü açıldı.')

        from django.urls import reverse
        return redirect(f"{reverse('module_hub')}{redirect_qs}")


class AgencyHubView(TemplateView):
    """Ajans retainer / proje çalışma alanı."""

    template_name = 'agency/hub.html'

    def dispatch(self, request, *args, **kwargs):
        from common.module_runtime import is_module_enabled, module_available_for_nav

        if not request.user.is_authenticated:
            return redirect('login')
        if not is_module_enabled('agency_suite'):
            messages.warning(request, 'Ajans Çalışma Alanı kurulu değil. Modül Merkezi\'nden açın.')
            return redirect('module_hub')
        if not module_available_for_nav(request.user, 'agency_suite'):
            messages.error(request, 'Ajans alanı için Rehber, İletişim veya Muhasebe erişiminiz olmalı.')
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from analytics.agency_summary import build_agency_panel_context
        from analytics.models import AgencyProject
        from customers.models import Customer
        from sales_leads.models import SalesLead

        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.update(build_agency_panel_context(user))

        from django.db.models import Q
        qs = AgencyProject.objects.select_related('customer', 'owner').all()
        if not user.is_superuser:
            qs = qs.filter(Q(owner=user) | Q(owner__isnull=True))
        context['agency_projects'] = qs
        context['agency_customers'] = Customer.objects.order_by('name')[:200]
        context['agency_status_choices'] = AgencyProject.Status.choices
        if user.has_perm_codename('access.accounting') or user.is_superuser:
            context['agency_pipeline_open'] = SalesLead.objects.filter(
                status=SalesLead.STATUS_PENDING,
            ).count()
        else:
            context['agency_pipeline_open'] = None
        return context

    def post(self, request, *args, **kwargs):
        from analytics.models import AgencyProject
        from customers.models import Customer

        action = request.POST.get('action', 'create')
        if action == 'delete':
            proj = get_object_or_404(AgencyProject, pk=request.POST.get('project_id'))
            if not request.user.is_superuser and proj.owner_id and proj.owner_id != request.user.id:
                messages.error(request, 'Bu projeyi silme yetkiniz yok.')
            else:
                name = proj.name
                proj.delete()
                messages.success(request, f'"{name}" silindi.')
            return redirect('agency_hub')

        name = (request.POST.get('name') or '').strip()
        if not name:
            messages.error(request, 'Proje adı zorunludur.')
            return redirect('agency_hub')

        status = request.POST.get('status', AgencyProject.Status.LEAD)
        if status not in dict(AgencyProject.Status.choices):
            status = AgencyProject.Status.LEAD

        retainer_raw = (request.POST.get('monthly_retainer') or '').strip().replace(',', '.')
        monthly_retainer = None
        if retainer_raw:
            try:
                monthly_retainer = Decimal(retainer_raw)
            except InvalidOperation:
                messages.error(request, 'Retainer tutarı geçersiz.')
                return redirect('agency_hub')

        customer = None
        cid = request.POST.get('customer_id')
        if cid:
            customer = Customer.objects.filter(pk=cid).first()

        start_date = parse_date(request.POST.get('start_date') or '') or None
        end_date = parse_date(request.POST.get('end_date') or '') or None
        notes = (request.POST.get('notes') or '').strip()

        if action == 'update':
            proj = get_object_or_404(AgencyProject, pk=request.POST.get('project_id'))
            if not request.user.is_superuser and proj.owner_id and proj.owner_id != request.user.id:
                messages.error(request, 'Bu projeyi düzenleme yetkiniz yok.')
                return redirect('agency_hub')
            proj.name = name
            proj.status = status
            proj.monthly_retainer = monthly_retainer
            proj.customer = customer
            proj.start_date = start_date
            proj.end_date = end_date
            proj.notes = notes
            proj.save()
            messages.success(request, f'"{proj.name}" güncellendi.')
        else:
            AgencyProject.objects.create(
                name=name,
                status=status,
                monthly_retainer=monthly_retainer,
                customer=customer,
                start_date=start_date,
                end_date=end_date,
                notes=notes,
                owner=request.user,
            )
            messages.success(request, f'"{name}" eklendi.')
        return redirect('agency_hub')


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
