from django.db import migrations


AGENCY_APP_SLUGS = [
    'app.agency.retainer_studio',
    'app.agency.clients',
    'app.agency.freelancers',
    'app.agency.firms',
    'app.agency.project_sales',
    'app.agency.finance',
    'app.agency.campaigns',
    'int.whatsapp_bridge',
    'int.whatsapp_api',
    'int.media',
]


def refresh_agency_installations(apps, schema_editor):
    SiteSettings = apps.get_model('core_settings', 'SiteSettings')
    for row in SiteSettings.objects.filter(primary_vertical_slug='agency'):
        row.enabled_module_slugs = list(AGENCY_APP_SLUGS)
        row.save(update_fields=['enabled_module_slugs'])


class Migration(migrations.Migration):

    dependencies = [
        ('core_settings', '0032_normalize_installation_vertical'),
        ('agency', '0002_import_legacy_analytics_projects'),
    ]

    operations = [
        migrations.RunPython(refresh_agency_installations, migrations.RunPython.noop),
    ]
