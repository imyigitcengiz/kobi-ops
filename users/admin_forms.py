from django import forms
from django.contrib.auth import get_user_model

from .models import Permission, Role

User = get_user_model()

INPUT = 'w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-brand-500 outline-none'
CHECKBOX = 'w-4 h-4 accent-brand-600'


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ['name', 'slug', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Örn: Depo Sorumlusu'}),
            'slug': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'ornek-rol'}),
            'description': forms.Textarea(attrs={'class': INPUT, 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.permission_ids = kwargs.pop('permission_ids', None)
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.is_system:
            self.fields['slug'].widget.attrs['readonly'] = True

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if self.instance.pk and self.instance.is_system:
            return self.instance.slug
        return slug

    def save(self, commit=True):
        role = super().save(commit=commit)
        if self.permission_ids is not None:
            perms = Permission.objects.filter(pk__in=self.permission_ids)
            role.permissions.set(perms)
        return role


class AdminUserCreateForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Şifre',
        widget=forms.PasswordInput(attrs={'class': INPUT}),
    )
    password2 = forms.CharField(
        label='Şifre (tekrar)',
        widget=forms.PasswordInput(attrs={'class': INPUT}),
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': INPUT}),
            'first_name': forms.TextInput(attrs={'class': INPUT}),
            'last_name': forms.TextInput(attrs={'class': INPUT}),
            'email': forms.EmailInput(attrs={'class': INPUT}),
            'role': forms.Select(attrs={'class': INPUT}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].queryset = Role.objects.order_by('name')
        self.fields['is_active'].initial = True
        self.fields['username'].help_text = 'Giriş için kullanılır; ekranda ad soyad görünür.'
        self.fields['first_name'].label = 'Ad'
        self.fields['last_name'].label = 'Soyad'

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 != p2:
            raise forms.ValidationError('Şifreler eşleşmiyor.')
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user


class AdminUserUpdateForm(forms.ModelForm):
    new_password = forms.CharField(
        required=False,
        label='Yeni şifre (opsiyonel)',
        widget=forms.PasswordInput(attrs={'class': INPUT}),
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': INPUT}),
            'first_name': forms.TextInput(attrs={'class': INPUT}),
            'last_name': forms.TextInput(attrs={'class': INPUT}),
            'email': forms.EmailInput(attrs={'class': INPUT}),
            'role': forms.Select(attrs={'class': INPUT}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX}),
        }

    def __init__(self, *args, **kwargs):
        self.editor = kwargs.pop('editor', None)
        super().__init__(*args, **kwargs)
        self.fields['role'].queryset = Role.objects.order_by('name')
        self.fields['username'].help_text = 'Giriş için kullanılır; ekranda ad soyad görünür.'
        self.fields['first_name'].label = 'Ad'
        self.fields['last_name'].label = 'Soyad'
        if self.instance and self.instance.is_superuser:
            self.fields['role'].disabled = True
            self.fields['is_active'].disabled = True

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('new_password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user
