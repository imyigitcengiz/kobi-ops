from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_accounting_module_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='business_mode',
            field=models.CharField(
                choices=[('kobi', 'Kobi App'), ('agency', 'Agency App')],
                default='kobi',
                help_text='CoolOPS içinde Kobi App veya Agency App deneyimi.',
                max_length=16,
                verbose_name='İş profili',
            ),
        ),
    ]
