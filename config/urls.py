import os

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from analytics.views import HomeView, PublicLandingView, ModuleHubView, AgencyHubView
from common.media_views import serve_media_file
from common.views import healthz

urlpatterns = [
    path('healthz/', healthz, name='healthz'),
    path('admin/', admin.site.urls),
    path('', PublicLandingView.as_view(), name='landing'),
    path('panel/', HomeView.as_view(), name='home'),
    path('panel/moduller/', ModuleHubView.as_view(), name='module_hub'),
    path('panel/ajans/', AgencyHubView.as_view(), name='agency_hub'),
    path('', include('users.urls')),
    path('services-dashboard/', include('config.services_dashboard_urls')),
    path('tools/', include('config.tools_urls')),
    path('sales-lead/', include('config.sales_lead_urls')),
    path('contact/', include('config.contact_urls')),
    path('iletisim/', include('config.outreach_urls')),
    path('muhasebe/', include('config.accounting_urls')),
    path('crm/', include('config.crm_urls')),
    path('ortak/', include('config.ortak_urls')),
    path('chat/', include('chat.urls')),
    path('ayarlar/', include('config.site_settings_urls')),
]

_serve_media = os.environ.get('DJANGO_SERVE_MEDIA', '1').lower() not in ('0', 'false', 'no')
if _serve_media:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve_media_file, name='serve_media'),
    ]
elif settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
