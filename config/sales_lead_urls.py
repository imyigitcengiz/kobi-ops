from django.urls import path
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/contact/', permanent=False), name='sales_lead_dashboard'),
    path('kayitlar/', RedirectView.as_view(url='/contact/', permanent=False), name='sales_lead_list'),
    path('yeni/', RedirectView.as_view(url='/contact/', permanent=False), name='sales_lead_create'),
    path('raporlar/', RedirectView.as_view(url='/contact/', permanent=False), name='sales_lead_reports'),
    path('raporlar/export-csv/', RedirectView.as_view(url='/contact/', permanent=False), name='sales_lead_export_csv'),
    path('musteriler/', RedirectView.as_view(url='/contact/musteriler/', permanent=False)),
    path('musteriler/<path:rest>', RedirectView.as_view(url='/contact/musteriler/%(rest)s', permanent=False)),
    path('<int:pk>/duzenle/', RedirectView.as_view(url='/contact/', permanent=False), name='sales_lead_edit'),
    path('<int:pk>/sil/', RedirectView.as_view(url='/contact/', permanent=False), name='sales_lead_delete'),
]
