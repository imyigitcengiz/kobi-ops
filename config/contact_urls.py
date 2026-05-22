from django.urls import path
from django.views.generic import RedirectView

from common.views import ContactHubView
from customers.views import (
    CustomerListView,
    CustomerCreateView,
    CustomerUpdateView,
    CustomerDeleteView,
    bulk_delete_customers,
    quick_customer_create,
    customer_detail_api,
    update_customer_products,
    customer_quick_edit_api,
    bulk_manage_customers,
    customers_picker_api,
)
from customers.media_views import (
    customer_media_list_api,
    customer_media_upload_api,
    customer_media_delete_api,
)
from core_settings.views import (
    SolutionNetworkView,
    TeamNetworkView,
    PersonnelNetworkView,
)
from tools.views import (
    FirmaKaziView,
    FirmalarView,
    TagManagerView,
    google_maps_search,
    google_maps_export_csv,
    firms_memory_list,
)
from tools.firm_views import (
    tags_api,
    tag_detail_api,
    firms_bulk_api,
    firms_memory_clear_api,
    regions_api,
    sent_messages_api,
)

urlpatterns = [
    path('', ContactHubView.as_view(), name='contact_hub'),
    path('musteriler/', CustomerListView.as_view(), name='customers'),
    path('musteriler/yeni/', CustomerCreateView.as_view(), name='customer_create'),
    path('musteriler/<int:pk>/duzenle/', CustomerUpdateView.as_view(), name='customer_update'),
    path('musteriler/<int:pk>/sil/', CustomerDeleteView.as_view(), name='customer_delete'),
    path('musteriler/toplu-sil/', bulk_delete_customers, name='customer_bulk_delete'),
    path('musteriler/toplu-islem/', bulk_manage_customers, name='customer_bulk_manage'),
    path('musteriler/hizli-ekle/', quick_customer_create, name='customer_quick_add'),
    path('musteriler/api/<int:pk>/', customer_detail_api, name='customer_detail_api'),
    path('musteriler/api/<int:pk>/urunler/', update_customer_products, name='update_customer_products'),
    path('musteriler/<int:pk>/hizli-duzenle/', customer_quick_edit_api, name='customer_quick_edit_api'),
    path('musteriler/secim/', customers_picker_api, name='customers_picker_api'),
    path('musteriler/<int:customer_id>/medya/', customer_media_list_api, name='customer_media_list_api'),
    path('musteriler/<int:customer_id>/medya/yukle/', customer_media_upload_api, name='customer_media_upload_api'),
    path('musteriler/medya/<int:pk>/sil/', customer_media_delete_api, name='customer_media_delete_api'),
    path('cozum-agi/', SolutionNetworkView.as_view(), name='solution_network'),
    path('ekip/', TeamNetworkView.as_view(), name='team_network'),
    path('personel/', PersonnelNetworkView.as_view(), name='personnel_network'),
    path('whatsapp-sablonlari/', RedirectView.as_view(url='/tools/whatsapp-baglan/#senaryolar', permanent=False), name='contact_whatsapp_templates'),
    path('whatsapp-kampanyalar/', RedirectView.as_view(url='/tools/whatsapp-baglan/', permanent=False)),
    path('firma-kazi/', FirmaKaziView.as_view(), name='contact_firma_kazi'),
    path('firma-kazi/search/', google_maps_search, name='contact_google_maps_search'),
    path('firma-kazi/export-csv/', google_maps_export_csv, name='contact_google_maps_export_csv'),
    path('firmalar/', FirmalarView.as_view(), name='contact_firmalar'),
    path('firmalar/hafiza/', firms_memory_list, name='contact_firms_memory'),
    path('firmalar/hafiza/temizle/', firms_memory_clear_api, name='contact_firms_memory_clear'),
    path('firmalar/hafiza/toplu/', firms_bulk_api, name='contact_firms_bulk'),
    path('firmalar/etiketler/', tags_api, name='contact_tags'),
    path('firmalar/etiketler/<int:pk>/', tag_detail_api, name='contact_tag_detail'),
    path('etiketler/', TagManagerView.as_view(), name='contact_tag_manager'),
    path('firmalar/bolgeler/', regions_api, name='contact_regions'),
    path('firmalar/mesajlar/', sent_messages_api, name='contact_sent_messages'),
]
