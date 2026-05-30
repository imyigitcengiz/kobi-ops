from django.urls import path
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(url='/muhasebe/satis/', permanent=False), name='sales_lead_dashboard_legacy'),
    path('kayitlar/', RedirectView.as_view(url='/muhasebe/satis/kayitlar/', permanent=False)),
    path('yeni/', RedirectView.as_view(url='/muhasebe/satis/yeni/', permanent=False)),
    path('raporlar/', RedirectView.as_view(url='/muhasebe/satis/raporlar/', permanent=False)),
    path('raporlar/export-csv/', RedirectView.as_view(url='/muhasebe/satis/raporlar/export-csv/', permanent=False)),
    path('musteriler/', RedirectView.as_view(url='/contact/musteriler/', permanent=False)),
    path('musteriler/<path:rest>', RedirectView.as_view(url='/contact/musteriler/%(rest)s', permanent=False)),
    path('<int:pk>/duzenle/', RedirectView.as_view(url='/muhasebe/satis/%(pk)s/duzenle/', permanent=False)),
    path('<int:pk>/sil/', RedirectView.as_view(url='/muhasebe/satis/%(pk)s/sil/', permanent=False)),
]
