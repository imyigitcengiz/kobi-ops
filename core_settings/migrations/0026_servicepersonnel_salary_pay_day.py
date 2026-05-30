# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_settings', '0025_payroll_periods'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicepersonnel',
            name='salary_pay_day',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='Her ay maaşın ödeneceği gün (1–31).',
                null=True,
                verbose_name='Maaş günü',
            ),
        ),
    ]
