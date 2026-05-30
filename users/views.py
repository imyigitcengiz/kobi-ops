from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as AuthLoginView, LogoutView as AuthLogoutView
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import FormView, TemplateView
from common.login_throttle import clear_login_attempts, is_login_blocked, register_failed_login
from .forms import UserLoginForm, UserPasswordChangeForm, UserProfileForm, UserRegistrationForm
from .registration import complete_user_registration, registration_is_open
from .utils import get_or_create_user_profile


class UserLoginView(AuthLoginView):
    template_name = 'users/login.html'
    authentication_form = UserLoginForm
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST' and is_login_blocked(request):
            messages.error(
                request,
                'Çok fazla başarısız giriş denemesi. Lütfen 15 dakika sonra tekrar deneyin.',
            )
            return redirect('login')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        redirect_to = self.request.POST.get('next') or self.request.GET.get('next')
        if redirect_to and url_has_allowed_host_and_scheme(
            redirect_to,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return redirect_to
        if self.request.user.is_superuser:
            return reverse('admin_dashboard')
        return reverse('home')

    def form_invalid(self, form):
        register_failed_login(self.request)
        return super().form_invalid(form)

    def form_valid(self, form):
        clear_login_attempts(self.request, form.cleaned_data.get('username', ''))
        messages.success(self.request, f'Hoş geldiniz, {form.get_user().display_name}.')
        return super().form_valid(form)


class UserRegisterView(FormView):
    template_name = 'users/register.html'
    form_class = UserRegistrationForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('home')
        if not registration_is_open():
            messages.info(request, 'Üye kaydı kapalı. Yöneticinizden hesap isteyin.')
            return redirect('login')
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        mode = self.request.GET.get('mode')
        if mode:
            initial['business_mode'] = mode
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial_mode'] = self.request.GET.get('mode')
        return kwargs

    def form_valid(self, form):
        user = form.save()
        mode, is_first = complete_user_registration(user, form.cleaned_data['business_mode'])
        if is_first:
            messages.success(
                self.request,
                f'Hoş geldiniz! İlk kurulum tamamlandı — {user.display_name} süper admin olarak atandı.',
            )
        else:
            profile_name = 'Kobi App' if mode == 'kobi' else 'Agency App'
            messages.success(
                self.request,
                f'Hesabınız oluşturuldu. Panel {profile_name} düzeninde açılacak.',
            )
        login(self.request, user)
        return redirect('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['selected_mode'] = self.request.GET.get('mode', 'kobi')
        return context


class UserLogoutView(AuthLogoutView):
    next_page = reverse_lazy('landing')

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.method == 'POST':
            messages.info(request, 'Oturum kapatıldı.')
        return response


class ProfileSettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'users/profile_settings.html'
    login_url = reverse_lazy('login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = get_or_create_user_profile(self.request.user)
        context['profile'] = profile
        context['profile_form'] = UserProfileForm(instance=profile, user=self.request.user)
        context['password_form'] = UserPasswordChangeForm(user=self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        profile = get_or_create_user_profile(request.user)
        action = request.POST.get('form_action', 'profile')

        if action == 'password':
            password_form = UserPasswordChangeForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(request, 'Şifreniz güncellendi.')
            else:
                messages.error(request, 'Şifre güncellenemedi. Lütfen alanları kontrol edin.')
            return redirect('profile_settings')

        profile_form = UserProfileForm(
            request.POST,
            request.FILES,
            instance=profile,
            user=request.user,
        )
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, 'Profil bilgileriniz kaydedildi.')
        else:
            messages.error(request, 'Profil güncellenemedi. Lütfen alanları kontrol edin.')
        return redirect('profile_settings')
