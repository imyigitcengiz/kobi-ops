from django.db import migrations, models
import django.db.models.deletion


def split_customer_whatsapp_logs(apps, schema_editor):
    Customer = apps.get_model('customers', 'Customer')
    Firm = apps.get_model('tools', 'MapsScrapedFirm')
    Msg = apps.get_model('tools', 'WhatsappOutboundMessage')

    customers_by_phone = {}
    for c in Customer.objects.exclude(phone='').exclude(phone__isnull=True).iterator():
        raw = (c.phone or '').strip()
        digits = ''.join(ch for ch in raw if ch.isdigit())
        if len(digits) >= 10:
            customers_by_phone[digits[-10:]] = c.pk

    for msg in Msg.objects.select_related('firm').iterator():
        is_customer = msg.send_type == 'customer'
        if not is_customer and msg.firm_id and getattr(msg.firm, 'notes', '') == 'Müşteri mesajı':
            is_customer = True
        if not is_customer:
            continue

        digits = ''.join(ch for ch in (msg.phone_normalized or '') if ch.isdigit())
        customer_pk = customers_by_phone.get(digits[-10:]) if len(digits) >= 10 else None

        msg.send_type = 'customer'
        msg.customer_id = customer_pk
        msg.firm_id = None
        msg.save(update_fields=['send_type', 'customer_id', 'firm_id'])

    Firm.objects.filter(notes='Müşteri mesajı').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0001_initial'),
        ('tools', '0006_firm_kind_send_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='whatsappoutboundmessage',
            name='customer',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='whatsapp_outbound_messages',
                to='customers.customer',
                verbose_name='Müşteri',
            ),
        ),
        migrations.RunPython(split_customer_whatsapp_logs, migrations.RunPython.noop),
    ]
