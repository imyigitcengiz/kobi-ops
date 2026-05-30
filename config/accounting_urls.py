from django.urls import path

from core_settings.views import AccountingHubView, AccountingPayrollView, AccountingFinanceView

urlpatterns = [
    path('', AccountingHubView.as_view(), name='accounting_hub'),
    path('maas-avans/', AccountingPayrollView.as_view(), name='accounting_payroll'),
    path('gelir-gider/', AccountingFinanceView.as_view(), name='accounting_finance'),
]
