"""Site genel ayarları — tüm modüllerden bağımsız (/ayarlar/)."""

from django.urls import path
from django.views.generic import RedirectView

from core_settings.system_views import (
    SettingsAIReportingView,
    SettingsAISettingsView,
    SettingsSystemBackupView,
)
from core_settings.views import (
    SiteSettingsView,
    settings_api,
    options_catalog_api,
    service_types_for_products_api,
    quick_option_create_api,
    quick_option_update_api,
)

_urunler = SiteSettingsView.as_view(section='urunler')
_ariza = SiteSettingsView.as_view(section='ariza-tipleri')
_durum = SiteSettingsView.as_view(section='durumlar')
_oncelik = SiteSettingsView.as_view(section='oncelikler')
_cozum = SiteSettingsView.as_view(section='cozum-turleri')

urlpatterns = [
    path('', RedirectView.as_view(url='/ayarlar/genel/', permanent=False), name='site_general_settings'),
    path('genel/', SiteSettingsView.as_view(section='genel'), name='settings_genel'),
    path('urunler/', _urunler, name='settings_products'),
    path('ariza-tipleri/', _ariza, name='settings_service_types'),
    path('durumlar/', _durum, name='settings_statuses'),
    path('oncelikler/', _oncelik, name='settings_priorities'),
    path('cozum-turleri/', _cozum, name='settings_partner_types'),
    # Eski hash yolları → sayfa
    path('urunler', RedirectView.as_view(pattern_name='settings_products', permanent=True)),
    path('ariza-tipleri', RedirectView.as_view(pattern_name='settings_service_types', permanent=True)),
    path('durumlar', RedirectView.as_view(pattern_name='settings_statuses', permanent=True)),
    path('oncelikler', RedirectView.as_view(pattern_name='settings_priorities', permanent=True)),
    path('cozum-turleri', RedirectView.as_view(pattern_name='settings_partner_types', permanent=True)),

    path('ai/ayarlar/', SettingsAISettingsView.as_view(), name='settings_ai_settings'),
    path('ai/raporlama/', SettingsAIReportingView.as_view(), name='settings_ai_reporting'),
    path('ai/panel/', RedirectView.as_view(pattern_name='settings_ai_reporting', permanent=False), name='ai_panel'),
    path('yedekler/', SettingsSystemBackupView.as_view(), name='settings_system_backup'),

    path('api/settings/', settings_api, name='settings_api'),
    path('api/options/catalog/', options_catalog_api, name='options_catalog_api'),
    path('api/options/service-types/', service_types_for_products_api, name='service_types_for_products_api'),
    path('api/options/quick-create/', quick_option_create_api, name='quick_option_create_api'),
    path('api/options/quick-update/', quick_option_update_api, name='quick_option_update_api'),
]
