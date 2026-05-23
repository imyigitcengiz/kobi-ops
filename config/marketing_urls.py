from django.urls import path

from tools.marketing_views import MarketingMessagesView

urlpatterns = [
    path(
        'kampanya-mesajlari/',
        MarketingMessagesView.as_view(),
        {'scope_key': 'kampanya'},
        name='marketing_campaign_messages',
    ),
    path(
        'firma-mesajlari/',
        MarketingMessagesView.as_view(),
        {'scope_key': 'firma'},
        name='marketing_firm_messages',
    ),
    path(
        'musteri-mesajlari/',
        MarketingMessagesView.as_view(),
        {'scope_key': 'musteri'},
        name='marketing_customer_messages',
    ),
    path(
        'personel-mesajlari/',
        MarketingMessagesView.as_view(),
        {'scope_key': 'personel'},
        name='marketing_personnel_messages',
    ),
    path(
        '',
        MarketingMessagesView.as_view(),
        {'scope_key': 'kampanya'},
        name='marketing_messages',
    ),
]
