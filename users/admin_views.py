from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView

from .admin_forms import AdminUserCreateForm, AdminUserUpdateForm, RoleForm
from .mixins import SuperuserRequiredMixin
from .models import Permission, Role

User = get_user_model()


def production_users_queryset():
    """RBAC test hesaplarını yönetim listelerinden gizler."""
    return User.objects.select_related('role').exclude(username__startswith='_rbac_')


class SuperAdminDashboardView(SuperuserRequiredMixin, TemplateView):
    template_name = 'users/yonetim/dashboard.html'

    def get_context_data(self, **kwargs):
        from django.db.models import Count
        context = super().get_context_data(**kwargs)
        context['total_users'] = production_users_queryset().count()
        context['active_users'] = production_users_queryset().filter(is_active=True).count()
        context['total_roles'] = Role.objects.count()
        context['total_permissions'] = Permission.objects.count()
        context['recent_users'] = production_users_queryset().order_by('-date_joined')[:8]
        context['roles'] = Role.objects.annotate(user_count=Count('users')).order_by('name')
        return context


class RoleListView(SuperuserRequiredMixin, ListView):
    model = Role
    template_name = 'users/yonetim/role_list.html'
    context_object_name = 'roles'

    def get_queryset(self):
        from django.db.models import Count
        return Role.objects.annotate(user_count=Count('users')).order_by('name')


class RoleFormMixin:
    def _selected_permission_ids(self):
        if getattr(self, 'object', None) and self.object.pk:
            return set(self.object.permissions.values_list('id', flat=True))
        return set()

    def _permission_ids_from_post(self):
        return [
            int(value)
            for value in self.request.POST.getlist('permissions')
            if str(value).isdigit()
        ]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.method == 'POST':
            kwargs['permission_ids'] = self._permission_ids_from_post()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == 'POST':
            context['selected_permission_ids'] = set(self._permission_ids_from_post())
        else:
            context['selected_permission_ids'] = self._selected_permission_ids()
        access_permissions = Permission.objects.filter(
            kind=Permission.KIND_ACCESS,
        ).order_by('sort_order', 'name')
        action_permissions = Permission.objects.filter(
            kind=Permission.KIND_ACTION,
        ).order_by('module', 'sort_order', 'name')
        action_by_module = {}
        for perm in action_permissions:
            action_by_module.setdefault(perm.module, []).append(perm)
        context['access_permissions'] = access_permissions
        context['action_permissions_by_module'] = action_by_module
        role = getattr(self, 'object', None)
        if role and role.pk:
            context['role_can_delete'] = not role.is_system and not role.users.exists()
            context['role_delete_blocked_reason'] = ''
            if role.is_system:
                context['role_delete_blocked_reason'] = 'Sistem rolleri silinemez.'
            elif role.users.exists():
                context['role_delete_blocked_reason'] = f'Bu role atanmış {role.users.count()} kullanıcı var.'
        else:
            context['role_can_delete'] = False
            context['role_delete_blocked_reason'] = ''
        return context


class RoleCreateView(SuperuserRequiredMixin, RoleFormMixin, CreateView):
    model = Role
    form_class = RoleForm
    template_name = 'users/yonetim/role_form.html'
    success_url = reverse_lazy('admin_roles')

    def form_valid(self, form):
        form.instance.is_system = False
        messages.success(self.request, 'Rol oluşturuldu.')
        return super().form_valid(form)


class RoleUpdateView(SuperuserRequiredMixin, RoleFormMixin, UpdateView):
    model = Role
    form_class = RoleForm
    template_name = 'users/yonetim/role_form.html'
    success_url = reverse_lazy('admin_roles')

    def form_valid(self, form):
        if self.object.is_system:
            form.instance.slug = self.object.slug
        messages.success(self.request, 'Rol güncellendi.')
        return super().form_valid(form)


class RoleDeleteView(SuperuserRequiredMixin, DeleteView):
    model = Role
    template_name = 'users/yonetim/role_confirm_delete.html'
    success_url = reverse_lazy('admin_roles')

    def get_queryset(self):
        return Role.objects.filter(is_system=False)

    def delete(self, request, *args, **kwargs):
        role = self.get_object()
        if role.users.exists():
            messages.error(request, 'Bu role atanmış kullanıcılar var; silinemez.')
            return redirect('admin_roles')
        messages.info(request, f'"{role.name}" rolü silindi.')
        return super().delete(request, *args, **kwargs)


class AdminUserListView(SuperuserRequiredMixin, ListView):
    model = User
    template_name = 'users/yonetim/user_list.html'
    context_object_name = 'users'
    paginate_by = 25

    def get_queryset(self):
        return production_users_queryset().order_by('-date_joined')


class AdminUserCreateView(SuperuserRequiredMixin, CreateView):
    model = User
    form_class = AdminUserCreateForm
    template_name = 'users/yonetim/user_form.html'
    success_url = reverse_lazy('admin_users')

    def form_valid(self, form):
        messages.success(self.request, 'Kullanıcı oluşturuldu.')
        user = form.save()
        from .utils import get_or_create_user_profile
        get_or_create_user_profile(user)
        return redirect(self.success_url)


class AdminUserUpdateView(SuperuserRequiredMixin, UpdateView):
    model = User
    form_class = AdminUserUpdateForm
    template_name = 'users/yonetim/user_form.html'
    success_url = reverse_lazy('admin_users')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['editor'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Kullanıcı güncellendi.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = True
        context.update(_user_delete_context(self.request.user, self.object))
        return context


def _user_delete_context(actor, target):
    can_delete = True
    blocked_reason = ''
    if actor.pk == target.pk:
        can_delete = False
        blocked_reason = 'Kendi hesabınızı silemezsiniz.'
    elif target.is_superuser and User.objects.filter(is_superuser=True).count() <= 1:
        can_delete = False
        blocked_reason = 'Sistemdeki son süper admin silinemez.'
    return {
        'user_can_delete': can_delete,
        'user_delete_blocked_reason': blocked_reason,
    }


class AdminUserDeleteView(SuperuserRequiredMixin, DeleteView):
    model = User
    template_name = 'users/yonetim/user_confirm_delete.html'
    success_url = reverse_lazy('admin_users')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_user_delete_context(self.request.user, self.object))
        return context

    def get(self, request, *args, **kwargs):
        user = self.get_object()
        ctx = _user_delete_context(request.user, user)
        if not ctx['user_can_delete']:
            messages.error(request, ctx['user_delete_blocked_reason'])
            return redirect('admin_users')
        return super().get(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        ctx = _user_delete_context(request.user, user)
        if not ctx['user_can_delete']:
            messages.error(request, ctx['user_delete_blocked_reason'])
            return redirect('admin_users')
        label = user.display_name
        messages.info(request, f'"{label}" kullanıcısı silindi.')
        return super().delete(request, *args, **kwargs)


class AdminSystemBackupView(SuperuserRequiredMixin, TemplateView):
    template_name = 'settings/system_backup.html'

    def get_context_data(self, **kwargs):
        from core_settings.backup import backup_status_summary
        context = super().get_context_data(**kwargs)
        context['backup_status'] = backup_status_summary()
        context['admin_context'] = True
        return context

    def post(self, request, *args, **kwargs):
        from core_settings.backup import (
            export_backup_response,
            export_sqlite_response,
            import_backup_file,
            import_sqlite_file,
        )
        if 'export_backup' in request.POST:
            try:
                return export_backup_response()
            except Exception as exc:
                messages.error(request, f'Yedekleme sırasında hata oluştu: {exc}')
                return redirect('admin_system_backup')

        if 'import_backup' in request.POST:
            ok, msg = import_backup_file(request.FILES.get('backup_file'))
            if ok:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            return redirect('admin_system_backup')

        if 'export_sqlite' in request.POST:
            try:
                return export_sqlite_response()
            except Exception as exc:
                messages.error(request, f'SQLite dışa aktarım hatası: {exc}')
                return redirect('admin_system_backup')

        if 'import_sqlite' in request.POST:
            ok, msg = import_sqlite_file(request.FILES.get('sqlite_file'))
            if ok:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            return redirect('admin_system_backup')

        return redirect('admin_system_backup')


class AdminSystemUpdatesView(SuperuserRequiredMixin, TemplateView):
    template_name = 'users/yonetim/system_updates.html'

    def get_context_data(self, **kwargs):
        from core_settings.updater import check_for_updates

        context = super().get_context_data(**kwargs)
        status = check_for_updates(force=False)
        context['update_status'] = status.to_dict()
        return context


class AdminSystemUpdateStatusApiView(SuperuserRequiredMixin, TemplateView):
    """GET — güncelleme durumu JSON."""

    def get(self, request, *args, **kwargs):
        from django.http import JsonResponse
        from core_settings.updater import check_for_updates

        force = request.GET.get('force') in ('1', 'true', 'yes')
        status = check_for_updates(force=force)
        return JsonResponse(status.to_dict())


class AdminSystemUpdateApplyApiView(SuperuserRequiredMixin, TemplateView):
    """POST — güncellemeyi uygula."""

    def post(self, request, *args, **kwargs):
        from django.http import JsonResponse
        from core_settings.updater import apply_update, check_for_updates, schedule_restart

        status = check_for_updates(force=True)
        if not status.update_available:
            return JsonResponse({
                'ok': True,
                'message': 'Zaten güncelsiniz.',
                'steps': [],
                'restarting': False,
            })
        if not status.can_apply:
            return JsonResponse({
                'ok': False,
                'error': status.message or 'Güncelleme uygulanamıyor.',
                'steps': [],
            }, status=400)

        ok, msg, steps, restart = apply_update()
        if ok and restart:
            schedule_restart()
        return JsonResponse({
            'ok': ok,
            'message': msg,
            'steps': steps,
            'restarting': ok and restart,
            'apply_mode': status.apply_mode,
        }, status=200 if ok else 500)
