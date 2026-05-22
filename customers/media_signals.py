from django.db.models.signals import pre_save
from django.dispatch import receiver

from common.media_compress import compress_model_file_field, prepare_media_file_for_storage

from .models import CustomerMedia


@receiver(pre_save, sender=CustomerMedia)
def compress_customer_media_on_save(sender, instance, **kwargs):
    """Tüm yükleme yollarında sunucu tarafı sıkıştırma."""
    if not instance.file:
        return
    if getattr(instance.file, '_gy_compressed', False):
        return

    if instance.pk:
        try:
            old = CustomerMedia.objects.only('file').get(pk=instance.pk)
            if old.file.name == instance.file.name:
                return
        except CustomerMedia.DoesNotExist:
            pass

    processed, meta = prepare_media_file_for_storage(instance.file)
    instance.file = processed
    instance.file_size_original = meta.get('original_bytes')
    instance.file_size_stored = meta.get('stored_bytes')
    instance.compress_method = meta.get('method', '') if meta.get('compressed') else ''
