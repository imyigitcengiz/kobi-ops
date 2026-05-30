"""Landing sayfası — sektör profiline göre vitrin metinleri (KOBİ & Ajans)."""

from __future__ import annotations

LANDING_VERTICAL_COPY: dict[str, dict] = {
    'kobi': {
        'badge': 'KOBİ & saha servis',
        'headline': 'Müşteri, servis, satış ve saha ekibiniz tek panelde birleşsin.',
        'lead': (
            'Montaj ve teknik servis ekipleri ile B2B satış yapan işletmeler için '
            'yardım masası, müşteri rehberi, personel, bordro ve WhatsApp — aynı veri üzerinde.'
        ),
        'highlights': (
            ('headphones', 'Yardım Masası', 'Saha servis iş emirleri'),
            ('users-round', 'Saha Ekipleri', 'Montaj ve teknik kadro'),
            ('wallet', 'Maaş & Avans', 'Brüt − avans = net'),
            ('message-circle', 'WhatsApp', 'Ekip ve müşteri iletişimi'),
        ),
    },
    'agency': {
        'badge': 'Ajans & proje',
        'headline': 'Retainer, freelancer ve müşteri pipeline tek stüdyoda.',
        'lead': (
            'Dijital ajans ve proje ekipleri için retainer takibi, müşteri kartları, '
            'freelancer ağı ve proje satışı — personel ve saha servisi olmadan.'
        ),
        'highlights': (
            ('palette', 'Retainer Stüdyosu', 'Aylık proje ve MRR'),
            ('sparkles', 'Müşteri & Marka', 'Ajans müşteri kartları'),
            ('user-plus', 'Freelancer Ağı', 'Taşeron ve tasarımcı kadrosu'),
            ('trending-up', 'Proje Pipeline', 'Teklif ve satış takibi'),
        ),
    },
}

DEFAULT_LANDING_VERTICAL = 'kobi'
