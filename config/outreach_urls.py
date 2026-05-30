"""İletişim Merkezi — kampanya, firma outreach ve mesaj kayıtları."""

from django.urls import path, include
from django.views.generic import RedirectView, TemplateView

from tools.firm_views import sent_messages_api, tags_api
from tools.marketing_views import OutreachCampaignView, OutreachMessagesView
from tools.collection_views import (
    collections_api,
    collection_detail_api,
    collection_clear_api,
    collection_add_members_api,
    collection_remove_member_api,
    collection_queue_api,
)
from tools.views import firms_memory_list
from tools.whatsapp_send_views import (
    whatsapp_cloud_status_api,
    campaign_send_next_api,
    campaign_queue_status_api,
)

urlpatterns = [
    path('', TemplateView.as_view(template_name='outreach/index.html'), name='outreach_hub'),
    path('kampanyalar/', OutreachCampaignView.as_view(), name='outreach_campaigns'),
    path(
        'mesajlar/kampanya/',
        OutreachMessagesView.as_view(),
        {'scope_key': 'kampanya'},
        name='outreach_campaign_messages',
    ),
    path(
        'mesajlar/firma/',
        OutreachMessagesView.as_view(),
        {'scope_key': 'firma'},
        name='outreach_firm_messages',
    ),
    path(
        'mesajlar/musteri/',
        OutreachMessagesView.as_view(),
        {'scope_key': 'musteri'},
        name='outreach_customer_messages',
    ),
    path(
        'mesajlar/personel/',
        OutreachMessagesView.as_view(),
        {'scope_key': 'personel'},
        name='outreach_personnel_messages',
    ),
    path(
        'mesajlar/',
        RedirectView.as_view(pattern_name='outreach_campaign_messages', permanent=False),
        name='outreach_messages',
    ),
    path('api/kampanyalar/', collections_api, name='outreach_collections'),
    path('api/kampanyalar/<int:pk>/', collection_detail_api, name='outreach_collection_detail'),
    path('api/kampanyalar/<int:pk>/temizle/', collection_clear_api, name='outreach_collection_clear'),
    path('api/kampanyalar/<int:pk>/uyeler/', collection_add_members_api, name='outreach_collection_members'),
    path(
        'api/kampanyalar/<int:pk>/uyeler/<int:member_id>/',
        collection_remove_member_api,
        name='outreach_collection_member_detail',
    ),
    path('api/kampanyalar/<int:pk>/kuyruk/', collection_queue_api, name='outreach_collection_queue'),
    path('api/gonder/sonraki/', campaign_send_next_api, name='outreach_send_next'),
    path('api/kuyruk/durum/', campaign_queue_status_api, name='outreach_queue_status'),
    path('api/whatsapp-api/durum/', whatsapp_cloud_status_api, name='outreach_whatsapp_api_status'),
    path('api/mesajlar/', sent_messages_api, name='outreach_sent_messages'),
    path('api/etiketler/', tags_api, name='outreach_tags'),
    path('api/firmalar/hafiza/', firms_memory_list, name='outreach_firms_memory'),
    # Eski yollar
    path('pazarlama/', RedirectView.as_view(pattern_name='outreach_hub', permanent=False)),
    path('pazarlama/<path:rest>', RedirectView.as_view(url='/iletisim/', permanent=False)),
]
