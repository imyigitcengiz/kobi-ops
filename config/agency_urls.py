from django.urls import path

from agency.views import (
    AgencyCampaignsView,
    AgencyClientsView,
    AgencyFinanceView,
    AgencyFirmsView,
    AgencyFreelancersView,
    AgencyHubView,
    AgencyPipelineView,
)

urlpatterns = [
    path('', AgencyHubView.as_view(), name='agency_hub'),
    path('musteriler/', AgencyClientsView.as_view(), name='agency_clients'),
    path('freelancer/', AgencyFreelancersView.as_view(), name='agency_freelancers'),
    path('firmalar/', AgencyFirmsView.as_view(), name='agency_firms'),
    path('pipeline/', AgencyPipelineView.as_view(), name='agency_pipeline'),
    path('finans/', AgencyFinanceView.as_view(), name='agency_finance'),
    path('kampanya/', AgencyCampaignsView.as_view(), name='agency_campaigns'),
]
