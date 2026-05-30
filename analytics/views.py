from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.db.models import Count, Q
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
