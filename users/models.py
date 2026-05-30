from django.contrib.auth.models import AbstractUser
from django.db import models

from common.business_modes import MODE_CHOICES, MODE_KOBI


class Permission(models.Model):
    KIND_ACCESS = 'access'
    KIND_ACTION = 'action'
    KIND_CHOICES = [
        (KIND_ACCESS, 'Modül erişimi'),
        (KIND_ACTION, 'Fonksiyon izni'),
    ]

    codename = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    module = models.CharField(max_length=40, default='Genel')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_ACTION)
    description = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['kind', 'module', 'sort_order', 'name']
        verbose_name = 'İzin'
        verbose_name_plural = 'İzinler'

    def __str__(self):
        return self.name

    @property
    def is_access(self):
        return self.kind == self.KIND_ACCESS


class Role(models.Model):
    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False, verbose_name='Sistem rolü')
    permissions = models.ManyToManyField(Permission, blank=True, related_name='roles')

    class Meta:
        ordering = ['name']
        verbose_name = 'Rol'
        verbose_name_plural = 'Roller'

    def __str__(self):
        return self.name


class User(AbstractUser):
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='users',
        null=True,
        blank=True,
        verbose_name='Rol',
    )

    class Meta:
        verbose_name = 'Kullanıcı'
        verbose_name_plural = 'Kullanıcılar'

    def __str__(self):
        role_name = self.role.name if self.role_id else 'Rol yok'
        return f"{self.username} ({role_name})"

    @property
    def display_name(self):
        full = self.get_full_name().strip()
        return full or self.username

    @property
    def initials(self):
        parts = self.display_name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.display_name[:2].upper()

    @property
    def role_label(self):
        if self.is_superuser:
            return 'Süper Admin'
        if self.role_id:
            return self.role.name
        return 'Rol atanmadı'

    def get_permission_codenames(self):
        if self.is_superuser:
            return set(Permission.objects.values_list('codename', flat=True))
        if not self.role_id:
            return set()
        return set(self.role.permissions.values_list('codename', flat=True))

    def has_perm_codename(self, codename):
        if self.is_superuser:
            return True
        if not codename:
            return True
        if not self.role_id:
            return False
        return self.role.permissions.filter(codename=codename).exists()

    def has_any_perm_codename(self, *codenames):
        if self.is_superuser:
            return True
        codes = {c for c in codenames if c}
        if not codes:
            return True
        if not self.role_id:
            return False
        return self.role.permissions.filter(codename__in=codes).exists()


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    business_mode = models.CharField(
        max_length=16,
        choices=MODE_CHOICES,
        default=MODE_KOBI,
        verbose_name='İş profili',
        help_text='CoolOPS içinde Kobi App veya Agency App deneyimi.',
    )
    avatar = models.ImageField(upload_to='profiles/', null=True, blank=True, verbose_name='Profil fotoğrafı')
    phone = models.CharField(max_length=30, blank=True, verbose_name='Telefon')
    job_title = models.CharField(max_length=120, blank=True, verbose_name='Ünvan')
    bio = models.TextField(blank=True, verbose_name='Hakkında')

    class Meta:
        verbose_name = 'Kullanıcı profili'
        verbose_name_plural = 'Kullanıcı profilleri'

    def __str__(self):
        return self.user.display_name

    def subtitle(self):
        if self.job_title:
            return self.job_title
        return self.user.role_label
