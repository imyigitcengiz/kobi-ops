from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_settings', '0021_dynamic_payments_product_lines'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='whatsapp_location_request_template',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Toplu yazdırmada konum yoksa QR bu metinle oluşturulur. Değişkenler: {site_name}, {ariza}',
                verbose_name='Yazdırma: WhatsApp konum isteme mesajı',
            ),
        ),
    ]
