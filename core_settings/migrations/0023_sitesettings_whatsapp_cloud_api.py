from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_settings', '0022_sitesettings_whatsapp_location_request_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='whatsapp_cloud_token',
            field=models.CharField(
                blank=True,
                default='',
                max_length=512,
                verbose_name='WhatsApp Business API token',
            ),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='whatsapp_cloud_phone_id',
            field=models.CharField(
                blank=True,
                default='',
                max_length=64,
                verbose_name='WhatsApp Business telefon numarası ID',
            ),
        ),
    ]
