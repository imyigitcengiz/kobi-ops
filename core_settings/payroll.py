"""Aylık maaş döngüsü — avans mahsubu ve net ödeme hesabı."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import PersonnelPayment, ServicePersonnel


def period_start(value: date) -> date:
    return value.replace(day=1)


def parse_period(raw: str | None) -> date:
    today = timezone.localdate()
    if not raw:
        return period_start(today)
    raw = raw.strip()
    if len(raw) == 7 and raw[4] == '-':
        year, month = int(raw[:4]), int(raw[5:7])
        return date(year, month, 1)
    if len(raw) >= 10:
        parsed = date.fromisoformat(raw[:10])
        return period_start(parsed)
    return period_start(today)


def period_label(period: date) -> str:
    months = (
        'Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
        'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık',
    )
    return f'{months[period.month - 1]} {period.year}'


def pay_day_from_date(value: date) -> int:
    return int(value.day)


def update_personnel_salary_schedule(personnel: ServicePersonnel, *, pay_date: date | None = None, pay_day: int | None = None):
    """Maaş gününü tam tarihten veya ayın gün numarasından güncelle."""
    if pay_date is not None:
        personnel.salary_pay_day = pay_day_from_date(pay_date)
    elif pay_day is not None:
        if pay_day < 1 or pay_day > 31:
            raise ValueError('Maaş günü 1–31 arasında olmalı.')
        personnel.salary_pay_day = pay_day
    else:
        personnel.salary_pay_day = None
    personnel.save(update_fields=['salary_pay_day'])


def process_cycle_salary(
    *,
    personnel: ServicePersonnel,
    period: date,
    payment_date: date,
    recorded_by,
    notes: str = '',
):
    """Seçili dönem maaşını kaydet; ödeme tarihindeki gün tekrar eden maaş günü olur."""
    update_personnel_salary_schedule(personnel, pay_date=payment_date)
    return create_salary_payment(
        personnel=personnel,
        period=period,
        payment_date=payment_date,
        recorded_by=recorded_by,
        notes=notes,
    )


def salary_due_date(personnel: ServicePersonnel, period: date) -> date | None:
    day = personnel.salary_pay_day
    if not day:
        return None
    period = period_start(period)
    last_day = calendar.monthrange(period.year, period.month)[1]
    return date(period.year, period.month, min(int(day), last_day))


def default_salary_payment_date(personnel: ServicePersonnel, period: date) -> date:
    due = salary_due_date(personnel, period)
    if due:
        return due
    today = timezone.localdate()
    period = period_start(period)
    if today.year == period.year and today.month == period.month:
        return today
    last_day = calendar.monthrange(period.year, period.month)[1]
    return date(period.year, period.month, last_day)


def unsettled_advances(personnel: ServicePersonnel, period: date):
    return PersonnelPayment.objects.filter(
        personnel=personnel,
        payment_type=PersonnelPayment.TYPE_ADVANCE,
        period=period,
        settled_by__isnull=True,
    ).order_by('payment_date', 'created_at')


def advance_total(personnel: ServicePersonnel, period: date) -> Decimal:
    total = unsettled_advances(personnel, period).aggregate(t=Sum('amount'))['t']
    return total or Decimal('0')


def salary_payment_for_period(personnel: ServicePersonnel, period: date):
    return PersonnelPayment.objects.filter(
        personnel=personnel,
        payment_type=PersonnelPayment.TYPE_SALARY,
        period=period,
    ).first()


def build_personnel_period_row(personnel: ServicePersonnel, period: date) -> dict:
    gross = personnel.monthly_salary or Decimal('0')
    advances_qs = unsettled_advances(personnel, period)
    advances_total = advance_total(personnel, period)
    salary_payment = salary_payment_for_period(personnel, period)
    net = (gross - advances_total) if gross else None
    due_date = salary_due_date(personnel, period)
    advances_deducted = advances_total
    if salary_payment and salary_payment.gross_amount:
        advances_deducted = salary_payment.gross_amount - salary_payment.amount
    return {
        'personnel': personnel,
        'gross': gross,
        'salary_pay_day': personnel.salary_pay_day,
        'due_date': due_date,
        'default_pay_date': default_salary_payment_date(personnel, period),
        'advances_total': advances_total,
        'advances_deducted': advances_deducted,
        'advance_items': list(advances_qs),
        'net': net,
        'salary_payment': salary_payment,
        'is_paid': salary_payment is not None,
        'can_pay': (
            gross > 0
            and salary_payment is None
            and (net is None or net >= 0)
        ),
    }


def build_period_summary(period: date, personnel_qs=None):
    if personnel_qs is None:
        personnel_qs = ServicePersonnel.objects.filter(is_active=True).order_by('name')
    rows = [build_personnel_period_row(p, period) for p in personnel_qs]
    return {
        'period': period,
        'period_label': period_label(period),
        'rows': rows,
        'total_gross': sum((r['gross'] for r in rows), Decimal('0')),
        'total_advances': sum((r['advances_total'] for r in rows), Decimal('0')),
        'total_net': sum(
            (r['net'] for r in rows if r['net'] is not None and not r['is_paid']),
            Decimal('0'),
        ),
        'paid_count': sum(1 for r in rows if r['is_paid']),
    }


def create_salary_payment(
    *,
    personnel: ServicePersonnel,
    period: date,
    payment_date: date,
    recorded_by,
    gross_override: Decimal | None = None,
    notes: str = '',
):
    period = period_start(period)
    if salary_payment_for_period(personnel, period):
        raise ValueError('Bu dönem için maaş zaten kaydedilmiş.')

    gross = gross_override if gross_override is not None else personnel.monthly_salary
    if not gross or gross <= 0:
        raise ValueError('Personelin aylık maaşı tanımlı değil.')

    advances = list(unsettled_advances(personnel, period))
    adv_total = sum((a.amount for a in advances), Decimal('0'))
    net = gross - adv_total
    if net < 0:
        raise ValueError('Avans toplamı brüt maaşı aşıyor.')

    auto_note = ''
    if adv_total:
        auto_note = f'Brüt {gross} ₺ — avans {adv_total} ₺ düşüldü, net {net} ₺'
    combined_notes = ' | '.join(filter(None, [auto_note, notes.strip()]))

    payment = PersonnelPayment.objects.create(
        personnel=personnel,
        payment_type=PersonnelPayment.TYPE_SALARY,
        period=period,
        gross_amount=gross,
        amount=net,
        payment_date=payment_date,
        notes=combined_notes,
        recorded_by=recorded_by,
    )
    for adv in advances:
        adv.settled_by = payment
        adv.save(update_fields=['settled_by'])
    return payment


def release_advances_on_salary_delete(salary_payment: PersonnelPayment):
    PersonnelPayment.objects.filter(settled_by=salary_payment).update(settled_by=None)


def iter_period_months(start: date, end: date):
    start = period_start(start)
    end = period_start(end)
    if end < start:
        start, end = end, start
    cur = start
    while cur <= end:
        yield cur
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)


def advances_total_all(personnel: ServicePersonnel, period: date) -> Decimal:
    total = PersonnelPayment.objects.filter(
        personnel=personnel,
        payment_type=PersonnelPayment.TYPE_ADVANCE,
        period=period_start(period),
    ).aggregate(t=Sum('amount'))['t']
    return total or Decimal('0')


def build_payroll_report(period_from: date, period_to: date, personnel_qs=None) -> dict:
    if personnel_qs is None:
        personnel_qs = ServicePersonnel.objects.filter(is_active=True).order_by('name')
    rows = []
    totals = {
        'gross': Decimal('0'),
        'advances': Decimal('0'),
        'net_paid': Decimal('0'),
        'pending_net': Decimal('0'),
    }
    for month in iter_period_months(period_from, period_to):
        for personnel in personnel_qs:
            summary = build_personnel_period_row(personnel, month)
            salary = summary['salary_payment']
            gross = salary.gross_amount if salary and salary.gross_amount else summary['gross']
            all_advances = advances_total_all(personnel, month)
            net_paid = salary.amount if salary else Decimal('0')
            row = {
                'period': month,
                'period_label': period_label(month),
                'personnel': personnel,
                'gross': gross,
                'advances_all': all_advances,
                'advances_open': summary['advances_total'],
                'net_expected': summary['net'],
                'net_paid': net_paid,
                'is_paid': summary['is_paid'],
                'can_pay': summary['can_pay'],
                'status': (
                    'Ödendi' if summary['is_paid']
                    else 'Bekliyor' if summary['can_pay']
                    else 'Tanımsız' if gross <= 0
                    else 'Avans fazla'
                ),
            }
            rows.append(row)
            totals['gross'] += gross or Decimal('0')
            totals['advances'] += all_advances
            totals['net_paid'] += net_paid
            if summary['can_pay'] and summary['net'] is not None:
                totals['pending_net'] += summary['net']
    return {
        'rows': rows,
        'totals': totals,
        'period_from': period_start(period_from),
        'period_to': period_start(period_to),
        'personnel_count': personnel_qs.count(),
    }


def bulk_pay_pending_salaries(period: date, recorded_by) -> dict:
    period = period_start(period)
    paid = []
    skipped = []
    for summary_row in build_period_summary(period)['rows']:
        if not summary_row['can_pay']:
            continue
        personnel = summary_row['personnel']
        try:
            create_salary_payment(
                personnel=personnel,
                period=period,
                payment_date=default_salary_payment_date(personnel, period),
                recorded_by=recorded_by,
            )
            paid.append(personnel.name)
        except ValueError as exc:
            skipped.append((personnel.name, str(exc)))
    return {'paid': paid, 'skipped': skipped}


def default_report_range() -> tuple[date, date]:
    today = timezone.localdate()
    start = date(today.year, 1, 1)
    return start, period_start(today)
