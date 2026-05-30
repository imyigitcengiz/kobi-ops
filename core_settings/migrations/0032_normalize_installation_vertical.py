from django.db import migrations


def normalize_installation_profiles(apps, schema_editor):
    SiteSettings = apps.get_model('core_settings', 'SiteSettings')
    for row in SiteSettings.objects.exclude(primary_vertical_slug__in=('kobi', 'agency')):
        row.primary_vertical_slug = 'kobi'
        row.save(update_fields=['primary_vertical_slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('core_settings', '0031_sitesettings_profile_setup_completed_at'),
    ]

    operations = [
        migrations.RunPython(normalize_installation_profiles, migrations.RunPython.noop),
    ]
