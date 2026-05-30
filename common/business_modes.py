"""CoolOPS içindeki iş profilleri: Kobi App (saha/KOBİ) ve Agency App (dijital ajans)."""

from common import module_labels as ml

MODE_KOBI = 'kobi'
MODE_AGENCY = 'agency'

MODE_CHOICES = [
    (MODE_KOBI, 'Kobi App'),
    (MODE_AGENCY, 'Agency App'),
]

ROLE_SLUG_BY_MODE = {
    MODE_KOBI: 'kobi_app',
    MODE_AGENCY: 'agency_app',
}

MODE_META = {
    MODE_KOBI: {
        'profile_name': 'Kobi App',
        'tagline': 'Saha operasyonu, servis takibi ve B2B satış',
        'home_intro': 'Servis, müşteri ve muhasebe modülleriniz Kobi App düzeninde gösteriliyor.',
        'home_hint': 'Önerilen akış: Servis kayıtları → Müşteriler → Raporlar',
        'register_blurb': 'Montaj, teknik servis, bayi ve saha ekipleri için.',
    },
    MODE_AGENCY: {
        'profile_name': 'Agency App',
        'tagline': 'Lead, kampanya ve proje geliri takibi',
        'home_intro': 'Firma kazıma, outreach ve proje geliri modülleriniz Agency App düzeninde gösteriliyor.',
        'home_hint': 'Önerilen akış: Lead firmalar → Kampanyalar → Proje geliri',
        'register_blurb': 'Dijital pazarlama, outreach ve proje bazlı ajanslar için.',
    },
}

LABEL_OVERRIDES = {
    MODE_KOBI: {},
    MODE_AGENCY: {
        'rehber_firmalar': 'Lead firmalar',
        'rehber_firma_bul': 'Lead bul',
        'sb_kayitlar': 'Proje kayıtları',
        'sb_ozet': 'Proje özeti',
        'yardim_masasi': 'Destek talepleri',
        'ym_kayitlar': 'Destek kayıtları',
        'ym_ozet': 'Destek paneli',
    },
}


def normalize_mode(value, *, default=MODE_KOBI):
    if value in (MODE_KOBI, MODE_AGENCY):
        return value
    return default


def get_mode_meta(mode):
    return MODE_META.get(normalize_mode(mode), MODE_META[MODE_KOBI])


def build_gy_labels(mode):
    """Temel module_labels + moda özel etiket birleşimi."""
    base = {
        'app_name': ml.APP_NAME,
        'kobi_app': ml.KOBI_APP,
        'agency_app': ml.AGENCY_APP,
        'rehber': ml.REHBER,
        'yardim_masasi': ml.YARDIM_MASASI,
        'satis_birimi': ml.SATIS_BIRIMI,
        'muhasebe': ml.MUHASEBE,
        'ym_ozet': ml.YM_OZET,
        'ym_kayitlar': ml.YM_KAYITLAR,
        'ym_durumlar': ml.YM_DURUMLAR,
        'ym_ariza': ml.YM_ARIZA_TIPLERI,
        'ym_oncelik': ml.YM_ONCELIKLER,
        'rehber_ozet': ml.REHBER_OZET,
        'rehber_musteriler': ml.REHBER_MUSTERILER,
        'rehber_firmalar': ml.REHBER_FIRMALAR,
        'rehber_firma_bul': ml.REHBER_FIRMA_BUL,
        'sb_ozet': ml.SB_OZET,
        'sb_kayitlar': ml.SB_KAYITLAR,
        'mh_ozet': ml.MH_OZET,
        'mh_maas_avans': ml.MH_MAAS_AVANS,
        'mh_raporlar': ml.MH_RAPORLAR,
        'mh_gelir_gider': ml.MH_GELIR_GIDER,
        'ortak_urunler': ml.ORTAK_URUNLER,
    }
    meta = get_mode_meta(mode)
    base['app_profile_name'] = meta['profile_name']
    base['home_intro'] = meta['home_intro']
    base['home_hint'] = meta['home_hint']
    base.update(LABEL_OVERRIDES.get(normalize_mode(mode), {}))
    return base
