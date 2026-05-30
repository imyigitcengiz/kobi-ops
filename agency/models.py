from django.conf import settings
from django.db import models


class AgencyClient(models.Model):
    """Ajans müşteri / marka kartı — KOBİ Customer kaydından bağımsız."""

    name = models.CharField('Marka / müşteri adı', max_length=200)
    contact_name = models.CharField('İletişim kişisi', max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    contract_type = models.CharField(
        max_length=20,
        choices=(
            ('retainer', 'Retainer'),
            ('project', 'Proje bazlı'),
            ('mixed', 'Karma'),
        ),
        default='retainer',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Ajans müşterisi'
        verbose_name_plural = 'Ajans müşterileri'

    def __str__(self):
        return self.name


class AgencyFreelancer(models.Model):
    name = models.CharField(max_length=200)
    specialty = models.CharField('Uzmanlık', max_length=120, blank=True)
    hourly_rate = models.DecimalField(
        'Saatlik ücret (₺)',
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Freelancer'
        verbose_name_plural = 'Freelancerlar'

    def __str__(self):
        return self.name


class AgencyFirm(models.Model):
    class Status(models.TextChoices):
        PROSPECT = 'prospect', 'Potansiyel'
        ACTIVE = 'active', 'İlişkide'
        ARCHIVED = 'archived', 'Arşiv'

    name = models.CharField(max_length=200)
    city = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PROSPECT,
        db_index=True,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Ajans firması'
        verbose_name_plural = 'Ajans firmaları'

    def __str__(self):
        return self.name


class AgencyProject(models.Model):
    class Status(models.TextChoices):
        LEAD = 'lead', 'Potansiyel'
        ACTIVE = 'active', 'Aktif retainer'
        PAUSED = 'paused', 'Duraklatıldı'
        DONE = 'done', 'Tamamlandı'

    name = models.CharField('Proje adı', max_length=200)
    client = models.ForeignKey(
        AgencyClient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='projects',
        verbose_name='Müşteri',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.LEAD,
        db_index=True,
    )
    monthly_retainer = models.DecimalField(
        'Aylık retainer (₺)',
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agency_projects_owned',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Retainer projesi'
        verbose_name_plural = 'Retainer projeleri'

    def __str__(self):
        return self.name


class AgencyDeal(models.Model):
    class Stage(models.TextChoices):
        LEAD = 'lead', 'Lead'
        PROPOSAL = 'proposal', 'Teklif'
        WON = 'won', 'Kazanıldı'
        LOST = 'lost', 'Kaybedildi'

    title = models.CharField(max_length=200)
    client = models.ForeignKey(
        AgencyClient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deals',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.LEAD, db_index=True)
    expected_close = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agency_deals_owned',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Pipeline kaydı'
        verbose_name_plural = 'Pipeline kayıtları'

    def __str__(self):
        return self.title


class AgencyFinanceEntry(models.Model):
    class Kind(models.TextChoices):
        INCOME = 'income', 'Gelir'
        EXPENSE = 'expense', 'Gider'

    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.INCOME)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    entry_date = models.DateField()
    project = models.ForeignKey(
        AgencyProject,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finance_entries',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-entry_date', '-id']
        verbose_name = 'Ajans finans kaydı'
        verbose_name_plural = 'Ajans finans kayıtları'

    def __str__(self):
        return self.title


class AgencyCampaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Taslak'
        SCHEDULED = 'scheduled', 'Planlandı'
        SENT = 'sent', 'Gönderildi'

    name = models.CharField(max_length=200)
    message_body = models.TextField('Mesaj metni', blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    target_client = models.ForeignKey(
        AgencyClient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Ajans kampanyası'
        verbose_name_plural = 'Ajans kampanyaları'

    def __str__(self):
        return self.name
