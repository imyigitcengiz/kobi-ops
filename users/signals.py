from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from common.media_compress import compress_model_file_field

from .models import User, UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(pre_save, sender=UserProfile)
def compress_profile_avatar(sender, instance, **kwargs):
    compress_model_file_field(instance, 'avatar', model=UserProfile)
