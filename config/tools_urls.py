from django.urls import path
from django.views.generic import RedirectView

from analytics.views import ai_chat_view
from tools.media_views import ToolsMediaDeleteView, ToolsMediaLibraryView
from tools.views import ToolsHubView, WhatsappBaglanView, WhatsappApiSettingsView
from tools.whatsapp_connection_views import (
    whatsapp_bridge_auto_start_api,
    whatsapp_bridge_ui_log_api,
    whatsapp_connections_api,
    whatsapp_connection_detail_api,
    whatsapp_connection_status_api,
    whatsapp_connection_connect_api,
    whatsapp_connection_disconnect_api,
    whatsapp_location_request_template_api,
)
from tools.whatsapp_send_views import whatsapp_ready_connections_api, whatsapp_send_api
from tools.whatsapp_template_views import (
    whatsapp_scenario_meta_api,
    whatsapp_scenario_template_detail_api,
    whatsapp_scenario_templates_api,
)

urlpatterns = [
    path('', ToolsHubView.as_view(), name='tools_hub'),
    path('whatsapp-baglan/', WhatsappBaglanView.as_view(), name='tools_whatsapp_baglan'),
    path('whatsapp-api/', WhatsappApiSettingsView.as_view(), name='tools_whatsapp_api_settings'),
    path('whatsapp-mesaj-gonderici/', RedirectView.as_view(url='/tools/whatsapp-baglan/', permanent=False)),
    path('toplu-whatsapp-mesaj/', RedirectView.as_view(url='/tools/whatsapp-baglan/', permanent=False)),
    path('google-maps-firma-bulma/', RedirectView.as_view(url='/contact/firma-bul/', permanent=False)),
    path('whatsapp/kopru/baslat/', whatsapp_bridge_auto_start_api, name='tools_whatsapp_bridge_auto_start'),
    path('whatsapp/kopru/gunluk/', whatsapp_bridge_ui_log_api, name='tools_whatsapp_bridge_ui_log'),
    path('whatsapp/baglantilar/', whatsapp_connections_api, name='tools_whatsapp_connections'),
    path('whatsapp/baglantilar/<int:pk>/', whatsapp_connection_detail_api, name='tools_whatsapp_connection_detail'),
    path('whatsapp/baglantilar/<int:pk>/status/', whatsapp_connection_status_api, name='tools_whatsapp_connection_status'),
    path('whatsapp/baglantilar/<int:pk>/connect/', whatsapp_connection_connect_api, name='tools_whatsapp_connection_connect'),
    path('whatsapp/baglantilar/<int:pk>/disconnect/', whatsapp_connection_disconnect_api, name='tools_whatsapp_connection_disconnect'),
    path('whatsapp/baglantilar/hazir/', whatsapp_ready_connections_api, name='tools_whatsapp_ready_connections'),
    path('whatsapp/gonder/', whatsapp_send_api, name='tools_whatsapp_send'),
    path(
        'whatsapp/yazdirma-konum-mesaji/',
        whatsapp_location_request_template_api,
        name='tools_whatsapp_location_request_template',
    ),
    path('whatsapp/senaryolar/meta/', whatsapp_scenario_meta_api, name='tools_whatsapp_scenario_meta'),
    path('whatsapp/senaryolar/', whatsapp_scenario_templates_api, name='tools_whatsapp_scenario_templates'),
    path('whatsapp/senaryolar/<int:pk>/', whatsapp_scenario_template_detail_api, name='tools_whatsapp_scenario_template_detail'),
    path('ai/ayarlar/', RedirectView.as_view(pattern_name='settings_ai_settings', permanent=False)),
    path('ai/panel/', RedirectView.as_view(pattern_name='settings_ai_reporting', permanent=False)),
    path('yedekler/', RedirectView.as_view(pattern_name='admin_system_backup', permanent=False)),
    path('medya/', ToolsMediaLibraryView.as_view(), name='tools_media_library'),
    path('medya/sil/', ToolsMediaDeleteView.as_view(), name='tools_media_delete'),
    path('api/ai-chat/chat/', ai_chat_view, name='ai_chat'),
]
