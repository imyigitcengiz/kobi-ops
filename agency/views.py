from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.generic import TemplateView, View

from agency.models import (
    AgencyCampaign,
    AgencyClient,
    AgencyDeal,
    AgencyFinanceEntry,
    AgencyFirm,
    AgencyFreelancer,
    AgencyProject,
)
from agency.summary import build_agency_panel_context
from users.mixins import PermissionRequiredMixin


class AgencyAccessMixin(PermissionRequiredMixin):
    permission_required = 'access.agency'


def _decimal(raw, default=None):
    if raw in (None, ''):
        return default
    try:
        return Decimal(str(raw).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return default


class AgencyHubView(AgencyAccessMixin, TemplateView):
    template_name = 'agency/hub.html'
    agency_nav_active = 'hub'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(build_agency_panel_context(self.request.user))
        context['agency_nav_active'] = self.agency_nav_active
        qs = AgencyProject.objects.select_related('client', 'owner').order_by('-updated_at')
        if not self.request.user.is_superuser:
            qs = qs.filter(Q(owner=self.request.user) | Q(owner__isnull=True))
        context['agency_projects'] = qs[:100]
        context['agency_clients'] = AgencyClient.objects.order_by('name')[:200]
        context['agency_status_choices'] = AgencyProject.Status.choices
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', 'save_project')
        if action == 'delete_project':
            proj = get_object_or_404(AgencyProject, pk=request.POST.get('project_id'))
            name = proj.name
            proj.delete()
            messages.success(request, f'"{name}" silindi.')
            return redirect('agency_hub')

        name = (request.POST.get('name') or '').strip()
        if not name:
            messages.error(request, 'Proje adı gerekli.')
            return redirect('agency_hub')

        status = request.POST.get('status', AgencyProject.Status.LEAD)
        monthly_retainer = _decimal(request.POST.get('monthly_retainer'))
        client_id = request.POST.get('client_id') or None
        client = AgencyClient.objects.filter(pk=client_id).first() if client_id else None
        start_date = parse_date(request.POST.get('start_date') or '')
        end_date = parse_date(request.POST.get('end_date') or '')
        notes = request.POST.get('notes', '')

        project_id = request.POST.get('project_id')
        if project_id:
            proj = get_object_or_404(AgencyProject, pk=project_id)
            proj.name = name
            proj.status = status
            proj.monthly_retainer = monthly_retainer
            proj.client = client
            proj.start_date = start_date
            proj.end_date = end_date
            proj.notes = notes
            proj.save()
            messages.success(request, f'"{proj.name}" güncellendi.')
        else:
            AgencyProject.objects.create(
                name=name,
                status=status,
                monthly_retainer=monthly_retainer,
                client=client,
                start_date=start_date,
                end_date=end_date,
                notes=notes,
                owner=request.user,
            )
            messages.success(request, f'"{name}" eklendi.')
        return redirect('agency_hub')


class AgencyClientsView(AgencyAccessMixin, TemplateView):
    template_name = 'agency/clients.html'
    agency_nav_active = 'clients'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agency_nav_active'] = self.agency_nav_active
        context['items'] = AgencyClient.objects.all()
        context['contract_choices'] = AgencyClient._meta.get_field('contract_type').choices
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'delete':
            obj = get_object_or_404(AgencyClient, pk=request.POST.get('pk'))
            obj.delete()
            messages.success(request, 'Müşteri silindi.')
            return redirect('agency_clients')

        pk = request.POST.get('pk')
        name = (request.POST.get('name') or '').strip()
        if not name:
            messages.error(request, 'Ad gerekli.')
            return redirect('agency_clients')

        data = {
            'name': name,
            'contact_name': request.POST.get('contact_name', ''),
            'email': request.POST.get('email', ''),
            'phone': request.POST.get('phone', ''),
            'contract_type': request.POST.get('contract_type', 'retainer'),
            'notes': request.POST.get('notes', ''),
        }
        if pk:
            AgencyClient.objects.filter(pk=pk).update(**data)
            messages.success(request, 'Müşteri güncellendi.')
        else:
            AgencyClient.objects.create(**data)
            messages.success(request, 'Müşteri eklendi.')
        return redirect('agency_clients')


class AgencyFreelancersView(AgencyAccessMixin, TemplateView):
    template_name = 'agency/freelancers.html'
    agency_nav_active = 'freelancers'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agency_nav_active'] = self.agency_nav_active
        context['items'] = AgencyFreelancer.objects.all()
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'delete':
            get_object_or_404(AgencyFreelancer, pk=request.POST.get('pk')).delete()
            messages.success(request, 'Freelancer silindi.')
            return redirect('agency_freelancers')

        pk = request.POST.get('pk')
        name = (request.POST.get('name') or '').strip()
        if not name:
            messages.error(request, 'Ad gerekli.')
            return redirect('agency_freelancers')

        data = {
            'name': name,
            'specialty': request.POST.get('specialty', ''),
            'hourly_rate': _decimal(request.POST.get('hourly_rate')),
            'email': request.POST.get('email', ''),
            'phone': request.POST.get('phone', ''),
            'is_active': request.POST.get('is_active') == 'on',
            'notes': request.POST.get('notes', ''),
        }
        if pk:
            AgencyFreelancer.objects.filter(pk=pk).update(**data)
            messages.success(request, 'Freelancer güncellendi.')
        else:
            AgencyFreelancer.objects.create(**data)
            messages.success(request, 'Freelancer eklendi.')
        return redirect('agency_freelancers')


class AgencyFirmsView(AgencyAccessMixin, TemplateView):
    template_name = 'agency/firms.html'
    agency_nav_active = 'firms'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agency_nav_active'] = self.agency_nav_active
        context['items'] = AgencyFirm.objects.all()
        context['status_choices'] = AgencyFirm.Status.choices
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'delete':
            get_object_or_404(AgencyFirm, pk=request.POST.get('pk')).delete()
            messages.success(request, 'Firma silindi.')
            return redirect('agency_firms')

        pk = request.POST.get('pk')
        name = (request.POST.get('name') or '').strip()
        if not name:
            messages.error(request, 'Firma adı gerekli.')
            return redirect('agency_firms')

        data = {
            'name': name,
            'city': request.POST.get('city', ''),
            'website': request.POST.get('website', ''),
            'status': request.POST.get('status', AgencyFirm.Status.PROSPECT),
            'notes': request.POST.get('notes', ''),
        }
        if pk:
            AgencyFirm.objects.filter(pk=pk).update(**data)
            messages.success(request, 'Firma güncellendi.')
        else:
            AgencyFirm.objects.create(**data)
            messages.success(request, 'Firma eklendi.')
        return redirect('agency_firms')


class AgencyPipelineView(AgencyAccessMixin, TemplateView):
    template_name = 'agency/pipeline.html'
    agency_nav_active = 'pipeline'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agency_nav_active'] = self.agency_nav_active
        context['items'] = AgencyDeal.objects.select_related('client').all()
        context['clients'] = AgencyClient.objects.order_by('name')
        context['stage_choices'] = AgencyDeal.Stage.choices
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'delete':
            get_object_or_404(AgencyDeal, pk=request.POST.get('pk')).delete()
            messages.success(request, 'Pipeline kaydı silindi.')
            return redirect('agency_pipeline')

        pk = request.POST.get('pk')
        title = (request.POST.get('title') or '').strip()
        if not title:
            messages.error(request, 'Başlık gerekli.')
            return redirect('agency_pipeline')

        client = AgencyClient.objects.filter(pk=request.POST.get('client_id')).first()
        data = {
            'title': title,
            'client': client,
            'amount': _decimal(request.POST.get('amount')),
            'stage': request.POST.get('stage', AgencyDeal.Stage.LEAD),
            'expected_close': parse_date(request.POST.get('expected_close') or ''),
            'notes': request.POST.get('notes', ''),
            'owner': request.user,
        }
        if pk:
            AgencyDeal.objects.filter(pk=pk).update(**{k: v for k, v in data.items() if k != 'owner'})
            messages.success(request, 'Pipeline güncellendi.')
        else:
            AgencyDeal.objects.create(**data)
            messages.success(request, 'Pipeline kaydı eklendi.')
        return redirect('agency_pipeline')


class AgencyFinanceView(AgencyAccessMixin, TemplateView):
    template_name = 'agency/finance.html'
    agency_nav_active = 'finance'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agency_nav_active'] = self.agency_nav_active
        context['items'] = AgencyFinanceEntry.objects.select_related('project').all()[:200]
        context['projects'] = AgencyProject.objects.order_by('name')
        context['kind_choices'] = AgencyFinanceEntry.Kind.choices
        entries = AgencyFinanceEntry.objects.all()
        income = entries.filter(kind=AgencyFinanceEntry.Kind.INCOME).aggregate(s=Sum('amount'))['s'] or 0
        expense = entries.filter(kind=AgencyFinanceEntry.Kind.EXPENSE).aggregate(s=Sum('amount'))['s'] or 0
        context['finance_income'] = income
        context['finance_expense'] = expense
        context['finance_net'] = income - expense
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'delete':
            get_object_or_404(AgencyFinanceEntry, pk=request.POST.get('pk')).delete()
            messages.success(request, 'Kayıt silindi.')
            return redirect('agency_finance')

        pk = request.POST.get('pk')
        title = (request.POST.get('title') or '').strip()
        amount = _decimal(request.POST.get('amount'))
        entry_date = parse_date(request.POST.get('entry_date') or '')
        if not title or amount is None or not entry_date:
            messages.error(request, 'Başlık, tutar ve tarih gerekli.')
            return redirect('agency_finance')

        project = AgencyProject.objects.filter(pk=request.POST.get('project_id')).first()
        data = {
            'title': title,
            'kind': request.POST.get('kind', AgencyFinanceEntry.Kind.INCOME),
            'amount': amount,
            'entry_date': entry_date,
            'project': project,
            'notes': request.POST.get('notes', ''),
        }
        if pk:
            AgencyFinanceEntry.objects.filter(pk=pk).update(**data)
            messages.success(request, 'Finans kaydı güncellendi.')
        else:
            AgencyFinanceEntry.objects.create(**data)
            messages.success(request, 'Finans kaydı eklendi.')
        return redirect('agency_finance')


class AgencyCampaignsView(AgencyAccessMixin, TemplateView):
    template_name = 'agency/campaigns.html'
    agency_nav_active = 'campaigns'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agency_nav_active'] = self.agency_nav_active
        context['items'] = AgencyCampaign.objects.select_related('target_client').all()
        context['clients'] = AgencyClient.objects.order_by('name')
        context['status_choices'] = AgencyCampaign.Status.choices
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('action') == 'delete':
            get_object_or_404(AgencyCampaign, pk=request.POST.get('pk')).delete()
            messages.success(request, 'Kampanya silindi.')
            return redirect('agency_campaigns')

        pk = request.POST.get('pk')
        name = (request.POST.get('name') or '').strip()
        if not name:
            messages.error(request, 'Kampanya adı gerekli.')
            return redirect('agency_campaigns')

        client = AgencyClient.objects.filter(pk=request.POST.get('target_client_id')).first()
        data = {
            'name': name,
            'message_body': request.POST.get('message_body', ''),
            'status': request.POST.get('status', AgencyCampaign.Status.DRAFT),
            'target_client': client,
        }
        if pk:
            AgencyCampaign.objects.filter(pk=pk).update(**data)
            messages.success(request, 'Kampanya güncellendi.')
        else:
            AgencyCampaign.objects.create(**data)
            messages.success(request, 'Kampanya eklendi.')
        return redirect('agency_campaigns')
