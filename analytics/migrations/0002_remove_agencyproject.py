from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agency', '0002_import_legacy_analytics_projects'),
        ('analytics', '0001_agencyproject'),
    ]

    operations = [
        migrations.DeleteModel(
            name='AgencyProject',
        ),
    ]
