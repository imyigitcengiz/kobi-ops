import csv
import json

from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from core_settings.forms import WhatsappCloudSettingsForm
from core_settings.models import SiteSettings
from users.mixins import PermissionRequiredMixin
from tools.whatsapp_cloud_client import cloud_api_status

from tools.firm_memory import enrich_search_results, register_scrape, serialize_firm
from tools.google_maps_search import GoogleMapsSearchError, search_businesses
from tools.models import FirmTag, MapsScrapedFirm
from tools.outreach_memory import CUSTOMER_SHADOW_NOTE, memory_stats, messaged_firm_count
from tools.phone_utils import is_whatsapp_eligible, is_turkish_landline, whatsapp_url


class ToolsHubView(TemplateView):
    template_name = 'tools/index.html'


class FirmalarView(TemplateView):
    """Birleşik firma rehberi: manuel kayıt, kazınan, çözüm ortağı, bayi, iş ortağı."""
    template_name = 'crm/firms_hub.html'

    def get_context_data(self, **kwargs):
        from tools.models import MapsScrapedFirm
        from core_settings.models import SolutionPartnerType

        context = super().get_context_data(**kwargs)
        view = (self.request.GET.get('view') or '').strip().lower()
        context['active_panel'] = 'maps' if view == 'maps' else 'rehber'
        context['memory_count'] = MapsScrapedFirm.objects.count()
        context['messaged_count'] = messaged_firm_count()
        context['partner_types'] = list(
            SolutionPartnerType.objects.filter(is_active=True).order_by('name').values('id', 'name')
        )
        context['kind_counts'] = {
            'all': MapsScrapedFirm.objects.count(),
            'scraped': MapsScrapedFirm.objects.filter(firm_kind=MapsScrapedFirm.KIND_SCRAPED).count(),
            'partner': MapsScrapedFirm.objects.filter(firm_kind=MapsScrapedFirm.KIND_PARTNER).count(),
            'dealer': MapsScrapedFirm.objects.filter(firm_kind=MapsScrapedFirm.KIND_DEALER).count(),
            'business': MapsScrapedFirm.objects.filter(firm_kind=MapsScrapedFirm.KIND_BUSINESS).count(),
        }
        return context


class FirmaBulView(FirmalarView):
    """Google Maps araması — tek panel içinde maps sekmesi."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_panel'] = 'maps'
        return context


FirmaKaziView = FirmaBulView  # geriye dönük


class TagManagerView(TemplateView):
    template_name = 'settings/tag_manager.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tag_count'] = FirmTag.objects.count()
        return context


class GoogleMapsFirmaBulmaView(FirmalarView):
    """Geriye dönük uyumluluk — Firmalar rehberine yönlendirilir."""


class WhatsappBaglanView(TemplateView):
    template_name = 'tools/whatsapp_baglan.html'

    def get_context_data(self, **kwargs):
        import sys
        from django.conf import settings as django_settings
        from tools.whatsapp_bridge_runner import bridge_spawn_allowed

        context = super().get_context_data(**kwargs)
        from urllib.parse import urlparse

        bridge_url = getattr(django_settings, 'WHATSAPP_BRIDGE_URL', 'http://127.0.0.1:3939')
        context['whatsapp_bridge_url'] = bridge_url
        context['whatsapp_bridge_can_spawn'] = bridge_spawn_allowed()
        context['whatsapp_bridge_is_windows'] = sys.platform == 'win32'
        host = (urlparse(bridge_url).hostname or '').lower()
        context['whatsapp_bridge_url_is_local'] = host in ('127.0.0.1', 'localhost', '::1')
        if not context['whatsapp_bridge_can_spawn']:
            context['whatsapp_bridge_url_docker'] = 'http://whatsapp_bridge:3939'
        from core_settings.whatsapp_print import get_whatsapp_location_request_template

        context['whatsapp_location_request_template'] = get_whatsapp_location_request_template()
        return context


class WhatsappApiSettingsView(PermissionRequiredMixin, View):
    permission_required = 'tools.whatsapp'
    template_name = 'tools/whatsapp_api_ayarlari.html'

    def _settings(self):
        settings = SiteSettings.objects.first()
        if not settings:
            settings = SiteSettings.objects.create()
        return settings

    def get(self, request):
        from django.shortcuts import render

        return render(request, self.template_name, {
            'form': WhatsappCloudSettingsForm(instance=self._settings()),
            'api_status': cloud_api_status(),
        })

    def post(self, request):
        from django.shortcuts import render

        settings = self._settings()
        form = WhatsappCloudSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'WhatsApp Business API ayarları kaydedildi.')
            return redirect('tools_whatsapp_api_settings')
        return render(request, self.template_name, {
            'form': form,
            'api_status': cloud_api_status(),
        })


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return None


def _apply_template(template: str, firm=None, *, name: str = '', phone: str = '', region: str = '') -> str:
    """Kampanya şablonu — {firma}, {telefon}, {bolge}, {adres}, {puan} yer tutucuları."""
    text = template or ''
    firm_name = name or (firm.name if firm else '') or 'Firma'
    replacements = {
        '{firma}': firm_name,
        '{telefon}': phone or (firm.phone if firm else '') or '',
        '{bolge}': region or (firm.region if firm else '') or '',
        '{adres}': (firm.address if firm and getattr(firm, 'address', None) else '') or '',
        '{puan}': str(getattr(firm, 'rating', '') or '') if firm else '',
    }
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text.strip()


@require_http_methods(['POST'])
def google_maps_search(request):
    body = _json_body(request)
    if body is None:
        return JsonResponse({'ok': False, 'error': 'Geçersiz istek gövdesi.'}, status=400)

    query = (body.get('query') or '').strip()
    location = (body.get('location') or '').strip()
    max_results = body.get('max_results') or 20
    phone_filter = (body.get('phone_filter') or 'all').strip()
    if phone_filter not in ('all', 'mobile', 'landline'):
        phone_filter = 'all'
    tag_ids = []
    for raw in body.get('tag_ids') or []:
        try:
            tag_ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    scrape_region = (body.get('scrape_region') or location or '').strip()[:80]

    if not query:
        return JsonResponse({'ok': False, 'error': 'Arama ifadesi girin.'}, status=400)

    try:
        raw_results = search_businesses(query, location, max_results)
        results = enrich_search_results(
            raw_results,
            phone_filter=phone_filter,
            tag_ids=tag_ids,
            scrape_region=scrape_region,
        )
    except GoogleMapsSearchError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=502)
    except Exception:
        return JsonResponse({
            'ok': False,
            'error': 'Arama sırasında bir hata oluştu. Lütfen bir süre sonra tekrar deneyin.',
        }, status=502)

    new_count = sum(1 for r in results if r.get('saved_to_memory') and not r.get('already_in_memory'))
    memory_count = sum(1 for r in results if r.get('already_in_memory'))
    saved_count = sum(1 for r in results if r.get('saved_to_memory'))
    stats = memory_stats()
    return JsonResponse({
        'ok': True,
        'count': len(results),
        'new_count': new_count,
        'memory_count': memory_count,
        'saved_count': saved_count,
        'phone_filter': phone_filter,
        'results': results,
        **stats,
    })


@require_http_methods(['GET'])
def firms_memory_list(request):
    q = (request.GET.get('q') or '').strip()
    tag_id = request.GET.get('tag_id')
    region = (request.GET.get('region') or '').strip()
    whatsapp_only = request.GET.get('whatsapp_only') in ('1', 'true', 'yes')
    page = max(int(request.GET.get('page') or 1), 1)
    page_size = min(max(int(request.GET.get('page_size') or 50), 1), 200)

    kind = (request.GET.get('kind') or '').strip()
    qs = (
        MapsScrapedFirm.objects.prefetch_related('tags', 'solution_partner__partner_type')
        .exclude(notes=CUSTOMER_SHADOW_NOTE)
        .order_by('-last_scraped_at')
    )
    if kind and kind != 'all':
        qs = qs.filter(firm_kind=kind)
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(phone__icontains=q)
            | Q(address__icontains=q)
            | Q(notes__icontains=q)
            | Q(region__icontains=q)
        )
    if region:
        qs = qs.filter(region__iexact=region)
    if tag_id:
        try:
            qs = qs.filter(tags__id=int(tag_id))
        except (TypeError, ValueError):
            pass

    total = qs.count()
    start = (page - 1) * page_size
    page_firms = list(qs[start:start + page_size])
    if whatsapp_only:
        page_firms = [f for f in page_firms if is_whatsapp_eligible(f.phone, f.phone_normalized)]
    items = [serialize_firm(f) for f in page_firms]
    stats = memory_stats()
    regions = list(
        MapsScrapedFirm.objects.exclude(region='')
        .values_list('region', flat=True)
        .distinct()
        .order_by('region')
    )
    return JsonResponse({
        'ok': True,
        'total': total,
        'page': page,
        'page_size': page_size,
        'results': items,
        'regions': regions,
        **stats,
    })


@require_http_methods(['POST'])
def google_maps_export_csv(request):
    body = _json_body(request)
    if body is None:
        return JsonResponse({'ok': False, 'error': 'Geçersiz veri.'}, status=400)

    rows = body.get('results') or []
    if not rows:
        return JsonResponse({'ok': False, 'error': 'Dışa aktarılacak kayıt yok.'}, status=400)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="google-maps-firma-listesi.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Firma Adı', 'Adres', 'Telefon', 'WhatsApp', 'Web Sitesi', 'Puan', 'Yorum',
        'Hafızada', 'Mesaj Gönderildi', 'Place ID', 'Maps URL',
    ])
    for row in rows:
        phone = row.get('phone', '-')
        writer.writerow([
            row.get('name', '-'),
            row.get('address', '-'),
            phone,
            row.get('whatsapp_url') or whatsapp_url(phone),
            row.get('website', '-'),
            row.get('rating', '-'),
            row.get('reviews', '-'),
            'Evet' if row.get('already_in_memory') else 'Hayır',
            row.get('messages_sent', 0),
            row.get('place_id', ''),
            row.get('maps_url', '-'),
        ])
    return response
