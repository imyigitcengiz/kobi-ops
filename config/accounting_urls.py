from django.urls import path

from core_settings.views import (
    AccountingHubView, AccountingReportsHubView, AccountingPayrollView,
    AccountingPayrollReportsView, AccountingPayrollExportView, AccountingFinanceView,
    AccountingPersonnelView,
)
from sales_leads.views import (
    SalesLeadCreateView,
    SalesLeadDashboardView,
    SalesLeadDeleteView,
    SalesLeadExportCsvView,
    SalesLeadListView,
    SalesLeadReportsView,
    SalesLeadUpdateView,
)

urlpatterns = [
    path('', AccountingHubView.as_view(), name='accounting_hub'),
    path('raporlar/', AccountingReportsHubView.as_view(), name='accounting_reports'),
    path('maas-avans/', AccountingPayrollView.as_view(), name='accounting_payroll'),
    path('personel/', AccountingPersonnelView.as_view(), name='accounting_personnel'),
    path('maas-avans/raporlar/', AccountingPayrollReportsView.as_view(), name='accounting_payroll_reports'),
    path('maas-avans/raporlar/export-csv/', AccountingPayrollExportView.as_view(), name='accounting_payroll_export'),
    path('gelir-gider/', AccountingFinanceView.as_view(), name='accounting_finance'),
    path('satis/', SalesLeadDashboardView.as_view(), name='sales_lead_dashboard'),
    path('satis/kayitlar/', SalesLeadListView.as_view(), name='sales_lead_list'),
    path('satis/yeni/', SalesLeadCreateView.as_view(), name='sales_lead_create'),
    path('satis/raporlar/', SalesLeadReportsView.as_view(), name='sales_lead_reports'),
    path('satis/raporlar/export-csv/', SalesLeadExportCsvView.as_view(), name='sales_lead_export_csv'),
    path('satis/<int:pk>/duzenle/', SalesLeadUpdateView.as_view(), name='sales_lead_edit'),
    path('satis/<int:pk>/sil/', SalesLeadDeleteView.as_view(), name='sales_lead_delete'),
]
