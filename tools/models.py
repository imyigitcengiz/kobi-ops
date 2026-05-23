from django.db import models

from django.db.models import Q





class FirmTag(models.Model):

    name = models.CharField(max_length=60, unique=True, verbose_name='Etiket')

    color = models.CharField(max_length=7, default='#6366f1', verbose_name='Renk')

    created_at = models.DateTimeField(auto_now_add=True)



    class Meta:

        verbose_name = 'Firma etiketi'

        verbose_name_plural = 'Firma etiketleri'

        ordering = ['name']



    def __str__(self):

        return self.name





class MapsScrapedFirm(models.Model):
    KIND_SCRAPED = 'scraped'
    KIND_PARTNER = 'partner'
    KIND_DEALER = 'dealer'
    KIND_BUSINESS = 'business'
    KIND_CHOICES = (
        (KIND_SCRAPED, 'Kazınan'),
        (KIND_PARTNER, 'Çözüm ortağı'),
        (KIND_DEALER, 'Bayi'),
        (KIND_BUSINESS, 'İş ortağı'),
    )

    place_id = models.CharField(max_length=128, blank=True, default='')

    phone_normalized = models.CharField(max_length=20, blank=True, default='', db_index=True)

    name = models.CharField(max_length=255)

    address = models.TextField(blank=True, default='')

    phone = models.CharField(max_length=40, blank=True, default='')

    website = models.CharField(max_length=500, blank=True, default='')

    rating = models.CharField(max_length=20, blank=True, default='')

    reviews = models.CharField(max_length=20, blank=True, default='')

    maps_url = models.CharField(max_length=500, blank=True, default='')

    lat = models.CharField(max_length=32, blank=True, default='')

    lng = models.CharField(max_length=32, blank=True, default='')

    first_scraped_at = models.DateTimeField(auto_now_add=True)

    last_scraped_at = models.DateTimeField(auto_now=True)

    messages_sent_count = models.PositiveIntegerField(default=0)

    last_message_at = models.DateTimeField(null=True, blank=True)

    notes = models.CharField(max_length=255, blank=True, default='')
    region = models.CharField(max_length=80, blank=True, default='', db_index=True, verbose_name='Bölge')
    firm_kind = models.CharField(
        max_length=20,
        choices=KIND_CHOICES,
        default=KIND_SCRAPED,
        db_index=True,
        verbose_name='Firma türü',
    )
    is_active = models.BooleanField(default=True, verbose_name='Aktif')
    solution_partner = models.OneToOneField(
        'core_settings.SolutionPartner',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='directory_entry',
        verbose_name='Çözüm ortağı kaydı',
    )
    tags = models.ManyToManyField(FirmTag, blank=True, related_name='firms')



    class Meta:

        verbose_name = 'Firma rehberi'

        verbose_name_plural = 'Firma rehberi'

        ordering = ['-last_scraped_at']

        constraints = [

            models.UniqueConstraint(

                fields=['place_id'],

                condition=~Q(place_id=''),

                name='tools_mapsfirm_unique_place_id',

            ),

            models.UniqueConstraint(

                fields=['phone_normalized'],

                condition=~Q(phone_normalized=''),

                name='tools_mapsfirm_unique_phone',

            ),

        ]



    def __str__(self):

        return self.name





class OutreachCollection(models.Model):

    """Kampanya / alıcı koleksiyonu."""

    name = models.CharField(max_length=120, verbose_name='Koleksiyon adı')

    message_template = models.TextField(blank=True, default='', verbose_name='Mesaj şablonu')

    skip_globally_messaged = models.BooleanField(

        default=False,

        verbose_name='Daha önce mesaj atılanları atla',

        help_text='İşaretliyse daha önce en az bir kez mesaj almış numaralar gönderilmez.',

    )

    allow_repeat_in_campaign = models.BooleanField(

        default=True,

        verbose_name='Bu kampanyada tekrar gönder',

        help_text='Kapalıysa bu koleksiyondan daha önce başarıyla gönderilmiş numaralar atlanır.',

    )

    delay_seconds = models.PositiveSmallIntegerField(default=4, verbose_name='Mesaj arası bekleme (sn)')

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)



    class Meta:

        verbose_name = 'Koleksiyon'

        verbose_name_plural = 'Koleksiyonlar'

        ordering = ['-updated_at']



    def __str__(self):

        return self.name





class OutreachCollectionMember(models.Model):

    collection = models.ForeignKey(

        OutreachCollection,

        on_delete=models.CASCADE,

        related_name='members',

    )

    firm = models.ForeignKey(

        MapsScrapedFirm,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name='collection_memberships',

    )

    name = models.CharField(max_length=255, blank=True, default='')

    phone_normalized = models.CharField(max_length=20, db_index=True)

    phone_display = models.CharField(max_length=40, blank=True, default='')
    custom_message = models.TextField(blank=True, default='', verbose_name='Özel mesaj')
    added_at = models.DateTimeField(auto_now_add=True)



    class Meta:

        verbose_name = 'Koleksiyon üyesi'

        verbose_name_plural = 'Koleksiyon üyeleri'

        ordering = ['id']

        constraints = [

            models.UniqueConstraint(

                fields=['collection', 'phone_normalized'],

                name='tools_collection_unique_phone',

            ),

        ]





class WhatsappOutboundMessage(models.Model):

    STATUS_PENDING = 'pending'

    STATUS_SENDING = 'sending'

    STATUS_SENT = 'sent'

    STATUS_FAILED = 'failed'

    STATUS_SKIPPED = 'skipped'

    STATUS_CHOICES = (

        (STATUS_PENDING, 'Bekliyor'),

        (STATUS_SENDING, 'Gönderiliyor'),

        (STATUS_SENT, 'Gönderildi'),

        (STATUS_FAILED, 'Başarısız'),

        (STATUS_SKIPPED, 'Atlandı'),

    )

    SOURCE_SCRAPED = 'scraped'

    SOURCE_MANUAL = 'manual'

    SOURCE_AUTO = 'auto'

    SOURCE_CHOICES = (

        (SOURCE_SCRAPED, 'Kazıma'),

        (SOURCE_MANUAL, 'Manuel'),

        (SOURCE_AUTO, 'Otomatik'),

    )

    SEND_CUSTOMER = 'customer'
    SEND_SCRAPED = 'scraped_firm'
    SEND_PARTNER = 'partner'
    SEND_DEALER = 'dealer'
    SEND_BUSINESS = 'business'
    SEND_CAMPAIGN = 'campaign'
    SEND_PRIVATE = 'private'
    SEND_AUTO = 'auto'
    SEND_TYPE_CHOICES = (
        (SEND_CUSTOMER, 'Müşteri'),
        (SEND_SCRAPED, 'Kazınan firma'),
        (SEND_PARTNER, 'Çözüm ortağı'),
        (SEND_DEALER, 'Bayi'),
        (SEND_BUSINESS, 'İş ortağı'),
        (SEND_CAMPAIGN, 'Kampanya'),
        (SEND_PRIVATE, 'Özel (toplu)'),
        (SEND_AUTO, 'Otomatik senaryo'),
    )



    collection = models.ForeignKey(

        OutreachCollection,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name='outbound_messages',

    )

    firm = models.ForeignKey(

        MapsScrapedFirm,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name='outbound_messages',

    )
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='whatsapp_outbound_messages',
        verbose_name='Müşteri',
    )

    recipient_name = models.CharField(max_length=255, blank=True, default='')

    phone_normalized = models.CharField(max_length=20, db_index=True)

    phone_display = models.CharField(max_length=40, blank=True, default='')

    message = models.TextField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_SCRAPED)
    send_type = models.CharField(
        max_length=24,
        choices=SEND_TYPE_CHOICES,
        blank=True,
        default='',
        db_index=True,
        verbose_name='Gönderim türü',
    )

    error_message = models.CharField(max_length=500, blank=True, default='')

    batch_id = models.CharField(max_length=64, blank=True, default='', db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    sent_at = models.DateTimeField(null=True, blank=True)



    class Meta:

        ordering = ['id']

        verbose_name = 'WhatsApp giden mesaj'

        verbose_name_plural = 'WhatsApp giden mesajlar'


class WhatsappConnection(models.Model):
    name = models.CharField(max_length=80, verbose_name='Bağlantı adı')
    phone = models.CharField(max_length=40, blank=True, default='')
    pushname = models.CharField(max_length=120, blank=True, default='')
    last_connected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'WhatsApp bağlantısı'
        verbose_name_plural = 'WhatsApp bağlantıları'
        ordering = ['name']

    def __str__(self):
        return self.name

