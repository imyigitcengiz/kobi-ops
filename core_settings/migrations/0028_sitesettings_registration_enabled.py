from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_settings', '0027_coolops_site_name_default'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='registration_enabled',
            field=models.BooleanField(
                default=True,
                help_text='Kapalıyken yalnızca yönetici kullanıcı oluşturabilir (ilk kurulum hariç).',
                verbose_name='Herkese açık üye kaydı',
            ),
        ),
    ]
