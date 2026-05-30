"""Muhasebe paneli ve /panel kısayolları için özet veriler."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from common.permissions import can_manage_finance, can_manage_payroll

from .models import FinanceRecord
from .payroll import build_period_summary, period_label, period_start


def _month_bounds(period: date) -> tuple[date, date]:
    period = period_start(period)
    last = calendar.monthrange(period.year, period.month)[1]
    return period, date(period.year, period.month, last)


def user_can_view_accounting_reports(user) -> bool:
    if not user.is_authenticated:
        return False
    if can_manage_payroll(user):
        return True
    return user.is_superuser or user.has_perm_codename('sales.reports')


def user_can_view_accounting_sales(user) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.has_any_perm_codename('sales.manage', 'sales.reports', 'sales.export')


def build_accounting_panel_context(user) -> dict:
    """Panel ve muhasebe özeti şablonları için ortak bağlam."""
    today = timezone.localdate()
    period = period_start(today)
    month_start, month_end = _month_bounds(period)

    ctx = {
        'accounting_period_label': period_label(period),
        'accounting_period_str': period.strftime('%Y-%m'),
        'accounting_show_payroll': can_manage_payroll(user),
        'accounting_show_finance': can_manage_finance(user),
        'accounting_show_reports': user_can_view_accounting_reports(user),
        'accounting_show_sales': user_can_view_accounting_sales(user),
    }

    if ctx['accounting_show_payroll']:
        summary = build_period_summary(period)
        rows = summary['rows']
        ctx.update({
            'accounting_payroll_pending': sum(1 for r in rows if r['can_pay']),
            'accounting_payroll_paid': summary['paid_count'],
            'accounting_payroll_staff': len(rows),
            'accounting_payroll_gross': summary['total_gross'],
            'accounting_payroll_advances': summary['total_advances'],
        })

    if ctx['accounting_show_finance']:
        month_qs = FinanceRecord.objects.filter(
            record_date__gte=month_start,
            record_date__lte=month_end,
        )
        income = month_qs.filter(record_type=FinanceRecord.TYPE_INCOME).aggregate(
            t=Sum('amount'),
        )['t'] or Decimal('0')
        expense = month_qs.filter(record_type=FinanceRecord.TYPE_EXPENSE).aggregate(
            t=Sum('amount'),
        )['t'] or Decimal('0')
        ctx.update({
            'accounting_finance_income': income,
            'accounting_finance_expense': expense,
            'accounting_finance_net': income - expense,
        })

    return ctx
