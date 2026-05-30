# Generated manually for agency workspace

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('customers', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AgencyProject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Proje adı')),
                ('status', models.CharField(choices=[('lead', 'Potansiyel'), ('active', 'Aktif retainer'), ('paused', 'Duraklatıldı'), ('done', 'Tamamlandı')], db_index=True, default='lead', max_length=20)),
                ('monthly_retainer', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Aylık retainer (₺)')),
                ('start_date', models.DateField(blank=True, null=True, verbose_name='Başlangıç')),
                ('end_date', models.DateField(blank=True, null=True, verbose_name='Bitiş')),
                ('notes', models.TextField(blank=True, verbose_name='Notlar')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='agency_projects', to='customers.customer', verbose_name='Müşteri')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='agency_projects_owned', to=settings.AUTH_USER_MODEL, verbose_name='Sorumlu')),
            ],
            options={
                'verbose_name': 'Ajans projesi',
                'verbose_name_plural': 'Ajans projeleri',
                'ordering': ['-updated_at'],
            },
        ),
    ]
