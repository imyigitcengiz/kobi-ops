from decimal import Decimal

from django.db import migrations


def import_legacy_projects(apps, schema_editor):
    connection = schema_editor.connection
    if 'analytics_agencyproject' not in connection.introspection.table_names():
        return

    AgencyClient = apps.get_model('agency', 'AgencyClient')
    AgencyProject = apps.get_model('agency', 'AgencyProject')
    LegacyProject = apps.get_model('analytics', 'AgencyProject')
    Customer = apps.get_model('customers', 'Customer')

    client_cache: dict[int, int] = {}

    for legacy in LegacyProject.objects.all().iterator():
        client = None
        if legacy.customer_id:
            if legacy.customer_id not in client_cache:
                try:
                    cust = Customer.objects.get(pk=legacy.customer_id)
                except Customer.DoesNotExist:
                    cust = None
                if cust:
                    ac, _ = AgencyClient.objects.get_or_create(
                        name=cust.name,
                        defaults={'phone': getattr(cust, 'phone', '') or ''},
                    )
                    client_cache[legacy.customer_id] = ac.pk
                else:
                    client_cache[legacy.customer_id] = None
            cid = client_cache.get(legacy.customer_id)
            if cid:
                client = AgencyClient.objects.filter(pk=cid).first()

        AgencyProject.objects.create(
            name=legacy.name,
            client=client,
            status=legacy.status,
            monthly_retainer=legacy.monthly_retainer,
            start_date=legacy.start_date,
            end_date=legacy.end_date,
            notes=legacy.notes or '',
            owner_id=legacy.owner_id,
            created_at=legacy.created_at,
            updated_at=legacy.updated_at,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('agency', '0001_initial'),
        ('analytics', '0001_agencyproject'),
        ('customers', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(import_legacy_projects, migrations.RunPython.noop),
    ]
