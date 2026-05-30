from django.db import models

from common.storage_paths import site_logo_upload_to

from .color_utils import DEFAULT_HEX, normalize_hex


class SiteSettings(models.Model):
    BULK_PRINT_SORT_CHOICES = [
        ('created_desc', 'Tarih (Yeni -> Eski)'),
        ('created_asc', 'Tarih (Eski -> Yeni)'),
        ('customer', 'Müşteri Adına Göre'),
        ('product', 'Ürüne Göre'),
        ('team', 'Ekibe Göre'),
        ('personnel', 'Personele Göre'),
        ('status', 'Duruma Göre'),
        ('priority', 'Önceliğe Göre'),
    ]

    site_name = models.CharField(max_length=255, default="CoolOPS")
    logo = models.ImageField(upload_to=site_logo_upload_to, null=True, blank=True)
    company_phone = models.CharField(max_length=50, blank=True, null=True, verbose_name="Firma Telefonu")
    company_address = models.TextField(blank=True, null=True, verbose_name="Firma Adresi")
    bulk_print_default_sort = models.CharField(
        max_length=20,
        choices=BULK_PRINT_SORT_CHOICES,
        default='created_desc',
        verbose_name='Toplu Yazdır Varsayılan Sıralama',
    )
    sidebar_profile_name = models.CharField(max_length=100, default="Yönetici", verbose_name="Sol Alt Profil Adı")
    sidebar_profile_role = models.CharField(max_length=100, default="Admin", verbose_name="Sol Alt Profil Ünvanı")

    openai_api_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="OpenAI API Key")
    google_api_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="Google AI (Gemini) API Key")
    ai_chat_enabled = models.BooleanField(default=False, verbose_name="Yapay Zeka Sohbet Aktif")
    ai_system_prompt = models.TextField(
        blank=True,
        null=True,
        default="Sen bir asistanasın. Kullanıcının sorularını yanıtla ve ona yardımcı ol.",
        verbose_name="Yapay Zeka Sistem Talimatı",
    )
    whatsapp_default_delay = models.PositiveSmallIntegerField(
        default=4,
        verbose_name='WhatsApp varsayılan bekleme (sn)',
    )
    whatsapp_skip_globally_default = models.BooleanField(
        default=False,
        verbose_name='WhatsApp: daha önce mesaj atılanları varsayılan atla',
    )
    whatsapp_location_request_template = models.TextField(
        blank=True,
        default='',
        verbose_name='Yazdırma: WhatsApp konum isteme mesajı',
        help_text='Toplu yazdırmada konum yoksa QR bu metinle oluşturulur. Değişkenler: {site_name}, {ariza}',
    )
    whatsapp_cloud_token = models.CharField(
        max_length=512,
        blank=True,
        default='',
        verbose_name='WhatsApp Business API token',
    )
    whatsapp_cloud_phone_id = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name='WhatsApp Business telefon numarası ID',
    )
    registration_enabled = models.BooleanField(
        default=True,
        verbose_name='Herkese açık üye kaydı',
        help_text='Kapalıyken yalnızca yönetici kullanıcı oluşturabilir (ilk kurulum hariç).',
    )

    class Meta:
        verbose_name = "Site Ayarları"
        verbose_name_plural = "Site Ayarları"

    def __str__(self):
        return self.site_name


class ColorOptionMixin(models.Model):
    color = models.CharField(max_length=7, default='#3b82f6', verbose_name="Renk")

    class Meta:
        abstract = True

    _COLOR_KIND = {
        'ServiceTypeOption': 'service_type',
        'ProductOption': 'product',
        'StatusOption': 'status',
        'PriorityOption': 'priority',
    }

    @property
    def color_hex(self):
        kind = self._COLOR_KIND.get(self.__class__.__name__, 'status')
        return normalize_hex(self.color, fallback=DEFAULT_HEX.get(kind, '#3b82f6'))

    def save(self, *args, **kwargs):
        kind = self._COLOR_KIND.get(self.__class__.__name__, 'status')
        self.color = normalize_hex(self.color, fallback=DEFAULT_HEX.get(kind, '#3b82f6'))
        super().save(*args, **kwargs)


class ServiceTypeOption(ColorOptionMixin, models.Model):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = "Servis tipi"
        verbose_name_plural = "Servis tipleri"

    def __str__(self):
        return self.name


class ProductOption(ColorOptionMixin, models.Model):
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, default='box')
    service_types = models.ManyToManyField(
        ServiceTypeOption,
        blank=True,
        related_name='products',
        verbose_name='İzin verilen arıza / servis tipleri',
    )

    class Meta:
        verbose_name = "Ürün seçeneği"
        verbose_name_plural = "Ürün seçenekleri"

    def __str__(self):
        return self.name


class ProductColorOption(ColorOptionMixin, models.Model):
    product = models.ForeignKey(
        ProductOption,
        on_delete=models.CASCADE,
        related_name='color_options',
        verbose_name='Ürün',
    )
    name = models.CharField(max_length=100, verbose_name='Renk adı')

    class Meta:
        verbose_name = 'Ürün rengi'
        verbose_name_plural = 'Ürün renkleri'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['product', 'name'], name='uniq_product_color_name'),
        ]

    def __str__(self):
        return f'{self.product.name} — {self.name}'


class StatusOption(ColorOptionMixin, models.Model):
    LIST_ACTIVE = 'active'
    LIST_PENDING = 'pending'
    LIST_HIDDEN = 'hidden'
    LIST_GROUP_CHOICES = [
        (LIST_ACTIVE, 'Liste: varsayılan göster'),
        (LIST_PENDING, 'Liste: isteğe bağlı (beklemede)'),
        (LIST_HIDDEN, 'Liste: varsayılan gizle'),
    ]

    name = models.CharField(max_length=100)
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name='Sıra')
    list_group = models.CharField(
        max_length=20,
        choices=LIST_GROUP_CHOICES,
        default=LIST_ACTIVE,
        verbose_name='Liste görünürlüğü',
    )

    class Meta:
        verbose_name = "Servis durumu"
        verbose_name_plural = "Servis durumları"
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class WhatsAppTemplate(models.Model):
    SCENARIO_SERVICE_CREATED = 'service_created'
    SCENARIO_SERVICE_STATUS = 'service_status'
    SCENARIO_SALES_LEAD_CREATED = 'sales_lead_created'
    SCENARIO_SALES_LEAD_STATUS = 'sales_lead_status'
    SCENARIO_CUSTOMER_CREATED = 'customer_created'
    SCENARIO_CHOICES = (
        (SCENARIO_SERVICE_CREATED, 'Servis — ilk kayıt açılışı'),
        (SCENARIO_SERVICE_STATUS, 'Servis — durum değişimi'),
        (SCENARIO_SALES_LEAD_CREATED, 'Satış — ilk kayıt'),
        (SCENARIO_SALES_LEAD_STATUS, 'Satış — durum değişimi'),
        (SCENARIO_CUSTOMER_CREATED, 'Müşteri — ilk kayıt'),
    )

    title = models.CharField(max_length=100, verbose_name="Kural adı")
    message = models.TextField(verbose_name="Mesaj içeriği")
    scenario = models.CharField(
        max_length=40,
        choices=SCENARIO_CHOICES,
        default=SCENARIO_SERVICE_STATUS,
        verbose_name='Senaryo',
    )
    trigger_from = models.CharField(
        max_length=80,
        blank=True,
        default='',
        verbose_name='Eski durum (önce)',
        help_text='Durum değişiminde önceki değer. Boş = herhangi.',
    )
    trigger_to = models.CharField(
        max_length=80,
        blank=True,
        default='',
        verbose_name='Yeni durum (sonra)',
        help_text='Oluşturma anındaki durum veya değişim sonrası durum. Boş = herhangi.',
    )
    trigger_value = models.CharField(
        max_length=80,
        blank=True,
        default='',
        verbose_name='Durum / koşul (eski)',
        help_text='Kullanımdan kalktı — trigger_to kullanın.',
    )
    auto_send = models.BooleanField(default=True, verbose_name='Otomatik gönder')
    is_active = models.BooleanField(default=True, verbose_name='Aktif')
    connection = models.ForeignKey(
        'tools.WhatsappConnection',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scenario_templates',
        verbose_name='Gönderen hat',
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "WhatsApp Şablonu"
        verbose_name_plural = "WhatsApp Şablonları"
        ordering = ['sort_order', 'title']

    def __str__(self):
        return self.title


class PriorityOption(ColorOptionMixin, models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Öncelik"
        verbose_name_plural = "Öncelikler"

    def __str__(self):
        return self.name


class SolutionPartnerType(models.Model):
    name = models.CharField(max_length=80, unique=True, verbose_name='Tür adı')
    is_active = models.BooleanField(default=True, verbose_name='Aktif')

    class Meta:
        verbose_name = 'Çözüm ortağı türü'
        verbose_name_plural = 'Çözüm ortağı türleri'
        ordering = ['name']

    def __str__(self):
        return self.name


class ServiceTeam(models.Model):
    name = models.CharField(max_length=80, unique=True, verbose_name='Ekip adı')
    product_groups = models.ManyToManyField(
        ProductOption,
        blank=True,
        related_name='skilled_teams',
        verbose_name='Yetenekli ürün grupları',
    )
    company_phone = models.CharField(max_length=30, blank=True, null=True, verbose_name='Şirket hattı')
    is_active = models.BooleanField(default=True, verbose_name='Aktif')

    class Meta:
        verbose_name = 'Servis ekibi'
        verbose_name_plural = 'Servis ekipleri'
        ordering = ['name']

    def __str__(self):
        return self.name


class ServicePersonnel(models.Model):
    name = models.CharField(max_length=120, verbose_name='Ad Soyad')
    team = models.ForeignKey(
        ServiceTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='personnel',
        verbose_name='Ekip',
    )
    product_groups = models.ManyToManyField(
        ProductOption,
        blank=True,
        related_name='skilled_personnel',
        verbose_name='Yetenekli ürün grupları',
    )
    company_phone = models.CharField(max_length=30, blank=True, null=True, verbose_name='Şirket numarası')
    monthly_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Aylık maaş',
        help_text='Muhasebe modülünde aylık döngü hesabı için.',
    )
    salary_pay_day = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Maaş günü',
        help_text='Her ay maaşın ödeneceği gün (1–31).',
    )
    is_active = models.BooleanField(default=True, verbose_name='Aktif')
    notes = models.CharField(max_length=255, blank=True, null=True, verbose_name='Not')

    class Meta:
        verbose_name = 'Servis personeli'
        verbose_name_plural = 'Servis personelleri'
        ordering = ['name']

    def __str__(self):
        return self.name


class PersonnelPayment(models.Model):
    TYPE_SALARY = 'salary'
    TYPE_ADVANCE = 'advance'
    TYPE_CHOICES = (
        (TYPE_SALARY, 'Maaş'),
        (TYPE_ADVANCE, 'Avans'),
    )

    personnel = models.ForeignKey(
        ServicePersonnel,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Personel',
    )
    payment_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='Tür')
    period = models.DateField(
        verbose_name='Maaş dönemi',
        help_text='Ayın ilk günü — avans ve maaş hangi aya ait.',
    )
    gross_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Brüt maaş',
        help_text='Maaş ödemesinde brüt tutar; net amount alanına yazılır.',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Tutar')
    payment_date = models.DateField(verbose_name='Ödeme tarihi')
    notes = models.CharField(max_length=255, blank=True, verbose_name='Not')
    settled_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='settled_advances',
        verbose_name='Mahsup eden maaş',
    )
    recorded_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='personnel_payments',
        verbose_name='Kaydeden',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Personel ödemesi'
        verbose_name_plural = 'Personel ödemeleri'
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f'{self.personnel.name} — {self.get_payment_type_display()} ({self.amount})'


class FinanceRecord(models.Model):
    TYPE_INCOME = 'income'
    TYPE_EXPENSE = 'expense'
    TYPE_CHOICES = (
        (TYPE_INCOME, 'Gelir'),
        (TYPE_EXPENSE, 'Gider'),
    )

    record_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='Tür')
    title = models.CharField(max_length=120, verbose_name='Açıklama')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Tutar')
    record_date = models.DateField(verbose_name='Tarih')
    notes = models.CharField(max_length=255, blank=True, verbose_name='Not')
    recorded_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finance_records',
        verbose_name='Kaydeden',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Gelir/gider kaydı'
        verbose_name_plural = 'Gelir/gider kayıtları'
        ordering = ['-record_date', '-created_at']

    def __str__(self):
        return f'{self.get_record_type_display()} — {self.title} ({self.amount})'


class SolutionPartner(models.Model):
    name = models.CharField(max_length=120, verbose_name='Ad')
    partner_type = models.ForeignKey(
        SolutionPartnerType,
        on_delete=models.PROTECT,
        related_name='partners',
        null=True,
        blank=True,
        verbose_name='Tür',
    )
    phone = models.CharField(max_length=30, blank=True, null=True, verbose_name='Telefon')
    notes = models.CharField(max_length=255, blank=True, null=True, verbose_name='Not')
    is_active = models.BooleanField(default=True, verbose_name='Aktif')

    class Meta:
        verbose_name = 'Çözüm ortağı'
        verbose_name_plural = 'Çözüm ortakları'
        ordering = ['name']

    def __str__(self):
        type_name = self.partner_type.name if self.partner_type else 'Türsüz'
        return f'{self.name} ({type_name})'


