from django.db import migrations, models


def rename_legacy_site_name(apps, schema_editor):
    SiteSettings = apps.get_model('core_settings', 'SiteSettings')
    legacy = ('GÖLGEDE YAŞAM', 'Gölgede Yaşam')
    SiteSettings.objects.filter(site_name__in=legacy).update(site_name='CoolOPS')


class Migration(migrations.Migration):

    dependencies = [
        ('core_settings', '0026_servicepersonnel_salary_pay_day'),
    ]

    operations = [
        migrations.RunPython(rename_legacy_site_name, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='sitesettings',
            name='site_name',
            field=models.CharField(default='CoolOPS', max_length=255),
        ),
    ]
