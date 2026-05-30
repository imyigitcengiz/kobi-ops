"""Ajans çalışma alanı panel özeti."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Sum

from analytics.models import AgencyProject


def build_agency_panel_context(user) -> dict:
    from django.db.models import Q

    qs = AgencyProject.objects.all()
    if not user.is_superuser:
        qs = qs.filter(Q(owner=user) | Q(owner__isnull=True))

    active = qs.filter(status=AgencyProject.Status.ACTIVE)
    retainer_sum = active.aggregate(total=Sum('monthly_retainer'))['total'] or Decimal('0')

    by_status = dict(
        qs.values('status').annotate(c=Count('id')).values_list('status', 'c')
    )

    return {
        'agency_project_count': qs.count(),
        'agency_active_count': by_status.get(AgencyProject.Status.ACTIVE, 0),
        'agency_lead_count': by_status.get(AgencyProject.Status.LEAD, 0),
        'agency_retainer_monthly': retainer_sum,
        'agency_recent_projects': list(qs.select_related('customer', 'owner')[:5]),
    }
