import re
from pathlib import Path

from django.conf import settings
from django.db import models


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r'[^\w.\-ğüşıöçĞÜŞİÖÇ ]', '_', name, flags=re.UNICODE)
    return name.strip() or 'dosya'


def customer_media_upload_path(instance, filename):
    cid = instance.customer_id or 'yeni'
    safe = _safe_filename(filename)
    if instance.scope == CustomerMedia.SCOPE_CONTRACT:
        return f'customers/{cid}/sozlesme/{safe}'
    if instance.scope == CustomerMedia.SCOPE_SERVICE and instance.service_id:
        return f'customers/{cid}/servis/{instance.service_id}/{safe}'
    return f'customers/{cid}/dosyalar/{safe}'


class Customer(models.Model):
    name = models.CharField(max_length=255, verbose_name="Müşteri Adı")
    phone = models.CharField(max_length=100, verbose_name="Telefon", blank=True, null=True)
    region = models.CharField(max_length=255, verbose_name="Bölge", blank=True, null=True)
    address = models.TextField(verbose_name="Adres", blank=True, null=True)
    location_link = models.URLField(max_length=500, verbose_name="Konum Linki", blank=True, null=True)
    contract_date = models.DateField(null=True, blank=True, verbose_name="Sözleşme Tarihi")
    products = models.ManyToManyField('core_settings.ProductOption', blank=True, verbose_name="Satın Aldığı Ürünler")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def contract_age(self):
        if not self.contract_date:
            return None
        
        from django.utils import timezone
        from dateutil.relativedelta import relativedelta
        
        diff = relativedelta(timezone.now().date(), self.contract_date)
        parts = []
        if diff.years > 0:
            parts.append(f"{diff.years} yıl")
        if diff.months > 0:
            parts.append(f"{diff.months} ay")
        
        if not parts:
            if diff.days > 0:
                return f"{diff.days} gün"
            return "Bugün"
            
        return " ".join(parts)

    def __str__(self):
        return self.name

    @property
    def whatsapp_link(self):
        if self.phone:
            clean_phone = ''.join(filter(str.isdigit, self.phone))
            if clean_phone.startswith('0'):
                clean_phone = '9' + clean_phone
            elif not clean_phone.startswith('90') and len(clean_phone) == 10:
                clean_phone = '90' + clean_phone
            return f"https://wa.me/{clean_phone}"
        return None


class CustomerMedia(models.Model):
    SCOPE_CUSTOMER = 'customer'
    SCOPE_SERVICE = 'service'
    SCOPE_CONTRACT = 'contract'
    SCOPE_CHOICES = (
        (SCOPE_CUSTOMER, 'Müşteri dosyası'),
        (SCOPE_SERVICE, 'Servis dosyası'),
        (SCOPE_CONTRACT, 'Sözleşme / belge'),
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='media_files',
        verbose_name='Müşteri',
    )
    service = models.ForeignKey(
        'services.ServiceRecord',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='media_files',
        verbose_name='Servis',
    )
    scope = models.CharField(
        max_length=20,
        choices=SCOPE_CHOICES,
        default=SCOPE_CUSTOMER,
        verbose_name='Kategori',
    )
    file = models.FileField(upload_to=customer_media_upload_path, verbose_name='Dosya')
    title = models.CharField(max_length=255, blank=True, verbose_name='Başlık')
    note = models.TextField(blank=True, verbose_name='Not')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_customer_media',
        verbose_name='Yükleyen',
    )
    file_size_original = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Orijinal boyut (bayt)',
    )
    file_size_stored = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Saklanan boyut (bayt)',
    )
    compress_method = models.CharField(
        max_length=40,
        blank=True,
        default='',
        verbose_name='Sıkıştırma',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Müşteri medyası'
        verbose_name_plural = 'Müşteri medyaları'

    def __str__(self):
        return self.title or Path(self.file.name).name if self.file else f'Medya #{self.pk}'

    @property
    def scope_label(self):
        return dict(self.SCOPE_CHOICES).get(self.scope, self.scope)

    def save(self, *args, **kwargs):
        if self.scope == self.SCOPE_SERVICE and self.service_id and not self.customer_id:
            self.customer_id = self.service.customer_id
        if self.scope != self.SCOPE_SERVICE:
            self.service_id = None
        super().save(*args, **kwargs)
