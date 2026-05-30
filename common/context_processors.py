from common import module_labels as ml


def gy_branding(request):
    """Modül adları — şablonlarda {{ gy.rehber }}, {{ gy.yardim_masasi }} vb."""
    return {
        'gy': {
            'app_name': ml.APP_NAME,
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
            'rehber_ekipler': ml.REHBER_EKIPLER,
            'rehber_personel': ml.REHBER_PERSONEL,
            'sb_ozet': ml.SB_OZET,
            'sb_kayitlar': ml.SB_KAYITLAR,
            'mh_ozet': ml.MH_OZET,
            'mh_maas_avans': ml.MH_MAAS_AVANS,
            'mh_personel': ml.MH_PERSONEL,
            'mh_raporlar': ml.MH_RAPORLAR,
            'mh_gelir_gider': ml.MH_GELIR_GIDER,
            'ortak_urunler': ml.ORTAK_URUNLER,
        },
    }
