import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AgencyClient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Marka / müşteri adı')),
                ('contact_name', models.CharField(blank=True, max_length=120, verbose_name='İletişim kişisi')),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('phone', models.CharField(blank=True, max_length=50)),
                ('contract_type', models.CharField(choices=[('retainer', 'Retainer'), ('project', 'Proje bazlı'), ('mixed', 'Karma')], default='retainer', max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Ajans müşterisi',
                'verbose_name_plural': 'Ajans müşterileri',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='AgencyFreelancer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('specialty', models.CharField(blank=True, max_length=120, verbose_name='Uzmanlık')),
                ('hourly_rate', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Saatlik ücret (₺)')),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('phone', models.CharField(blank=True, max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Freelancer',
                'verbose_name_plural': 'Freelancerlar',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='AgencyFirm',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('city', models.CharField(blank=True, max_length=100)),
                ('website', models.URLField(blank=True)),
                ('status', models.CharField(choices=[('prospect', 'Potansiyel'), ('active', 'İlişkide'), ('archived', 'Arşiv')], db_index=True, default='prospect', max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Ajans firması',
                'verbose_name_plural': 'Ajans firmaları',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='AgencyProject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='Proje adı')),
                ('status', models.CharField(choices=[('lead', 'Potansiyel'), ('active', 'Aktif retainer'), ('paused', 'Duraklatıldı'), ('done', 'Tamamlandı')], db_index=True, default='lead', max_length=20)),
                ('monthly_retainer', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Aylık retainer (₺)')),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='projects', to='agency.agencyclient', verbose_name='Müşteri')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='agency_projects_owned', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Retainer projesi',
                'verbose_name_plural': 'Retainer projeleri',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='AgencyDeal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('amount', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('stage', models.CharField(choices=[('lead', 'Lead'), ('proposal', 'Teklif'), ('won', 'Kazanıldı'), ('lost', 'Kaybedildi')], db_index=True, default='lead', max_length=20)),
                ('expected_close', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deals', to='agency.agencyclient')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='agency_deals_owned', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Pipeline kaydı',
                'verbose_name_plural': 'Pipeline kayıtları',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='AgencyFinanceEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('kind', models.CharField(choices=[('income', 'Gelir'), ('expense', 'Gider')], default='income', max_length=10)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('entry_date', models.DateField()),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='finance_entries', to='agency.agencyproject')),
            ],
            options={
                'verbose_name': 'Ajans finans kaydı',
                'verbose_name_plural': 'Ajans finans kayıtları',
                'ordering': ['-entry_date', '-id'],
            },
        ),
        migrations.CreateModel(
            name='AgencyCampaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('message_body', models.TextField(blank=True, verbose_name='Mesaj metni')),
                ('status', models.CharField(choices=[('draft', 'Taslak'), ('scheduled', 'Planlandı'), ('sent', 'Gönderildi')], default='draft', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('target_client', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='campaigns', to='agency.agencyclient')),
            ],
            options={
                'verbose_name': 'Ajans kampanyası',
                'verbose_name_plural': 'Ajans kampanyaları',
                'ordering': ['-created_at'],
            },
        ),
    ]
