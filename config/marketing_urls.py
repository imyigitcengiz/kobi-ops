from django.urls import path
from django.views.generic import RedirectView

from tools.marketing_views import OutreachMessagesView

urlpatterns = [
    path(
        'kampanya-mesajlari/',
        RedirectView.as_view(pattern_name='outreach_campaign_messages', permanent=False),
        name='marketing_campaign_messages',
    ),
    path(
        'firma-mesajlari/',
        RedirectView.as_view(pattern_name='outreach_firm_messages', permanent=False),
        name='marketing_firm_messages',
    ),
    path(
        'musteri-mesajlari/',
        RedirectView.as_view(pattern_name='outreach_customer_messages', permanent=False),
        name='marketing_customer_messages',
    ),
    path(
        'personel-mesajlari/',
        RedirectView.as_view(pattern_name='outreach_personnel_messages', permanent=False),
        name='marketing_personnel_messages',
    ),
    path(
        '',
        RedirectView.as_view(pattern_name='outreach_hub', permanent=False),
        name='marketing_messages',
    ),
]
