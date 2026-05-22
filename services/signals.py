from django.db.models.signals import m2m_changed, post_delete, pre_save, post_save

from django.dispatch import receiver



from config.live_sync import publish_live_event

from common.media_compress import compress_model_file_field

from .models import ServiceRecord, ServiceImage





@receiver(pre_save, sender=ServiceRecord)

def cache_service_status(sender, instance, **kwargs):

    if instance.pk:

        try:

            old = ServiceRecord.objects.only('status_id').get(pk=instance.pk)

            instance._prev_status_id = old.status_id

        except ServiceRecord.DoesNotExist:

            instance._prev_status_id = None

    else:

        instance._prev_status_id = None





@receiver(post_save, sender=ServiceRecord)

def on_service_saved(sender, instance, created, **kwargs):

    publish_live_event(

        kind="service",

        action="created" if created else "updated",

        object_id=instance.id,

        message=f"Servis #{instance.id} {'oluşturuldu' if created else 'güncellendi'}.",

    )



    # WhatsApp senaryoları otomatik gönderilmez; kullanıcı onayı views + whatsapp_status_prompt ile yapılır.





@receiver(post_delete, sender=ServiceRecord)

def on_service_deleted(sender, instance, **kwargs):

    publish_live_event(

        kind="service",

        action="deleted",

        object_id=instance.id,

        message=f"Servis #{instance.id} silindi.",

    )





@receiver(m2m_changed, sender=ServiceRecord.products.through)

def on_service_products_changed(sender, instance, action, **kwargs):

    if action in {"post_add", "post_remove", "post_clear"}:

        publish_live_event(

            kind="service",

            action="updated",

            object_id=instance.id,

            message=f"Servis #{instance.id} ürünleri güncellendi.",

        )





@receiver(m2m_changed, sender=ServiceRecord.service_types.through)

def on_service_types_changed(sender, instance, action, **kwargs):

    if action in {"post_add", "post_remove", "post_clear"}:

        publish_live_event(

            kind="service",

            action="updated",

            object_id=instance.id,

            message=f"Servis #{instance.id} arıza tipleri güncellendi.",

        )


@receiver(pre_save, sender=ServiceImage)
def compress_service_image_on_save(sender, instance, **kwargs):
    compress_model_file_field(instance, 'image', model=ServiceImage)

