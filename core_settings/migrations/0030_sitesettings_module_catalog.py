from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_settings', '0029_remove_sitesettings_registration_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='primary_vertical_slug',
            field=models.CharField(
                default='kobi',
                help_text='Modül vitrininde öne çıkan sektör kategorisi (KOBİ, ajans, …).',
                max_length=32,
                verbose_name='Birincil sektör profili',
            ),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='enabled_module_slugs',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Boş bırakılırsa varsayılan aktif modüller kullanılır.',
                verbose_name='Açık modüller',
            ),
        ),
    ]
