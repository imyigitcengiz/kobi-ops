from django.db import models
from django.conf import settings


class AgencyProject(models.Model):
    """Ajans retainer / proje — müşteri kartına bağlı hafif iş takibi."""

    class Status(models.TextChoices):
        LEAD = 'lead', 'Potansiyel'
        ACTIVE = 'active', 'Aktif retainer'
        PAUSED = 'paused', 'Duraklatıldı'
        DONE = 'done', 'Tamamlandı'

    name = models.CharField('Proje adı', max_length=200)
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agency_projects',
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
    start_date = models.DateField('Başlangıç', null=True, blank=True)
    end_date = models.DateField('Bitiş', null=True, blank=True)
    notes = models.TextField('Notlar', blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agency_projects_owned',
        verbose_name='Sorumlu',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Ajans projesi'
        verbose_name_plural = 'Ajans projeleri'

    def __str__(self):
        return self.name
