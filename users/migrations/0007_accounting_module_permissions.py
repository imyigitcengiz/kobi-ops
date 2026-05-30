from django.db import migrations


def sync_accounting_permissions(apps, schema_editor):
    from users.permission_sync import sync_permissions_to_db

    sync_permissions_to_db(reset_system_role_permissions=True)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_customers_view_permission'),
        ('core_settings', '0024_accounting_module'),
    ]

    operations = [
        migrations.RunPython(sync_accounting_permissions, migrations.RunPython.noop),
    ]
