from django.db import migrations

RBAC_FIXUPS = {
    '_rbac_muhasebe': ('Muhasebe', ''),
    '_rbac_satis': ('Satış', 'Temsilcisi'),
    '_rbac_servis': ('Servis', 'Personeli'),
    '_rbac_operasyon': ('Operasyon', ''),
}


def fix_rbac_display_names(apps, schema_editor):
    User = apps.get_model('users', 'User')
    for username, (first, last) in RBAC_FIXUPS.items():
        User.objects.filter(username=username).update(first_name=first, last_name=last)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_remove_userprofile_business_mode'),
    ]

    operations = [
        migrations.RunPython(fix_rbac_display_names, migrations.RunPython.noop),
    ]
