from django.contrib.auth import get_user_model

from common.business_modes import MODE_KOBI, ROLE_SLUG_BY_MODE, normalize_mode
from users.models import Role
from users.utils import get_or_create_user_profile

User = get_user_model()


def registration_is_open():
    from core_settings.models import SiteSettings

    settings = SiteSettings.objects.first()
    if settings is None:
        return True
    if not User.objects.exists():
        return True
    return settings.registration_enabled


def complete_user_registration(user, business_mode):
    """Kayıt sonrası profil modu, rol ve ilk kurulum süper admin ataması."""
    mode = normalize_mode(business_mode)
    profile = get_or_create_user_profile(user)
    profile.business_mode = mode
    profile.save(update_fields=['business_mode'])

    is_first_user = not User.objects.exclude(pk=user.pk).exists()
    if is_first_user:
        user.is_superuser = True
        user.is_staff = True
        user.save(update_fields=['is_superuser', 'is_staff'])
        return mode, True

    role_slug = ROLE_SLUG_BY_MODE.get(mode, ROLE_SLUG_BY_MODE[MODE_KOBI])
    role = Role.objects.filter(slug=role_slug).first()
    if role:
        user.role = role
        user.save(update_fields=['role'])
    return mode, False
