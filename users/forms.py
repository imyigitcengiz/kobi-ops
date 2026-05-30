from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm

from common.business_modes import MODE_AGENCY, MODE_CHOICES, MODE_KOBI, normalize_mode

from .models import User, UserProfile

INPUT = 'w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-brand-500 outline-none'


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': INPUT,
            'placeholder': 'Kullanıcı adı',
            'autocomplete': 'username',
        }),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': INPUT,
            'placeholder': 'Şifre',
            'autocomplete': 'current-password',
        }),
    )


class UserRegistrationForm(UserCreationForm):
    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Ad'}),
    )
    last_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Soyad'}),
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': INPUT, 'placeholder': 'ornek@firma.com'}),
    )
    business_mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        widget=forms.RadioSelect,
        label='İş profiliniz',
        initial=MODE_KOBI,
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'business_mode', 'password1', 'password2')

    def __init__(self, *args, initial_mode=None, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('username', 'password1', 'password2'):
            self.fields[name].widget.attrs['class'] = INPUT
        self.fields['username'].widget.attrs['placeholder'] = 'Kullanıcı adı'
        self.fields['password1'].widget.attrs['placeholder'] = 'Şifre'
        self.fields['password2'].widget.attrs['placeholder'] = 'Şifre tekrar'
        if initial_mode:
            self.fields['business_mode'].initial = normalize_mode(initial_mode)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.email = self.cleaned_data.get('email', '')
        if commit:
            user.save()
        return user


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Ad'}),
    )
    last_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Soyad'}),
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': INPUT, 'placeholder': 'ornek@firma.com'}),
    )

    class Meta:
        model = UserProfile
        fields = ['business_mode', 'avatar', 'phone', 'job_title', 'bio']
        widgets = {
            'business_mode': forms.RadioSelect,
            'phone': forms.TextInput(attrs={'class': INPUT, 'placeholder': '+90 5xx xxx xx xx'}),
            'job_title': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn: Operasyon Yöneticisi'}),
            'bio': forms.Textarea(attrs={'class': INPUT, 'rows': 4, 'placeholder': 'Kısa tanıtım...'}),
            'avatar': forms.FileInput(attrs={'class': 'block w-full text-sm text-slate-600 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:bg-brand-50 file:text-brand-700 file:font-semibold hover:file:bg-brand-100'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
        self.fields['business_mode'].widget.attrs.update({'class': 'accent-brand-600'})

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user:
            self.user.first_name = self.cleaned_data.get('first_name', '')
            self.user.last_name = self.cleaned_data.get('last_name', '')
            self.user.email = self.cleaned_data.get('email', '')
            if commit:
                self.user.save(update_fields=['first_name', 'last_name', 'email'])
        if commit:
            profile.save()
        return profile


class UserPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = INPUT
