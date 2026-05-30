from datetime import date
from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


def backfill_payment_periods(apps, schema_editor):
    PersonnelPayment = apps.get_model('core_settings', 'PersonnelPayment')
    for payment in PersonnelPayment.objects.all():
        d = payment.payment_date
        period = date(d.year, d.month, 1)
        updates = {'period': period}
        if payment.payment_type == 'salary' and payment.gross_amount is None:
            updates['gross_amount'] = payment.amount
        PersonnelPayment.objects.filter(pk=payment.pk).update(**updates)


class Migration(migrations.Migration):

    dependencies = [
        ('core_settings', '0024_accounting_module'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicepersonnel',
            name='monthly_salary',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Muhasebe modülünde aylık döngü hesabı için.',
                max_digits=12,
                null=True,
                verbose_name='Aylık maaş',
            ),
        ),
        migrations.AddField(
            model_name='personnelpayment',
            name='period',
            field=models.DateField(
                help_text='Ayın ilk günü — avans ve maaş hangi aya ait.',
                null=True,
                verbose_name='Maaş dönemi',
            ),
        ),
        migrations.AddField(
            model_name='personnelpayment',
            name='gross_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Maaş ödemesinde brüt tutar; net amount alanına yazılır.',
                max_digits=12,
                null=True,
                verbose_name='Brüt maaş',
            ),
        ),
        migrations.AddField(
            model_name='personnelpayment',
            name='settled_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='settled_advances',
                to='core_settings.personnelpayment',
                verbose_name='Mahsup eden maaş',
            ),
        ),
        migrations.RunPython(backfill_payment_periods, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='personnelpayment',
            name='period',
            field=models.DateField(
                help_text='Ayın ilk günü — avans ve maaş hangi aya ait.',
                verbose_name='Maaş dönemi',
            ),
        ),
    ]
