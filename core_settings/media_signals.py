from django.db.models.signals import pre_save
from django.dispatch import receiver

from common.media_compress import compress_model_file_field

from .models import SiteSettings


@receiver(pre_save, sender=SiteSettings)
def compress_site_logo(sender, instance, **kwargs):
    compress_model_file_field(instance, 'logo', model=SiteSettings)
