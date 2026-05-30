"""İletişim Merkezi — mesaj kayıtları ve kampanya ekranı."""

from django.views.generic import TemplateView


class OutreachCampaignView(TemplateView):
    template_name = 'outreach/campaigns.html'


class OutreachMessagesView(TemplateView):
    template_name = 'outreach/message_log.html'

    SCOPE_META = {
        'kampanya': {
            'title': 'Kampanya mesaj kayıtları',
            'subtitle': 'WhatsApp Business API ile gönderilen toplu kampanya mesajları.',
            'icon': 'megaphone',
            'scope': 'campaign',
            'empty_hint': 'Henüz kampanya mesajı yok. Kampanyalar bölümünden gönderim yapın.',
            'action_url_name': 'outreach_campaigns',
            'action_label': 'Kampanyalar',
        },
        'firma': {
            'title': 'Firma mesaj kayıtları',
            'subtitle': 'Firma outreach geçmişi (kampanya dışı API gönderimleri dahil).',
            'icon': 'building-2',
            'scope': 'firm',
            'empty_hint': 'Firma mesaj kaydı bulunamadı.',
            'action_url_name': 'contact_firmalar',
            'action_label': 'Firma rehberi',
        },
        'musteri': {
            'title': 'Müşteri mesaj kayıtları',
            'subtitle': 'Müşteri kartlarına giden WhatsApp kayıtları (QR köprüsü).',
            'icon': 'users',
            'scope': 'customer',
            'empty_hint': 'Müşteriye gönderilmiş mesaj yok.',
            'action_url_name': 'customers',
            'action_label': 'Müşteriler',
        },
        'personel': {
            'title': 'Personel mesaj kayıtları',
            'subtitle': 'Servis ekibi otomatik senaryo bildirimleri.',
            'icon': 'id-card',
            'scope': 'personnel',
            'empty_hint': 'Personel mesaj kaydı yok.',
            'action_url_name': 'accounting_payroll',
            'action_label': 'Personel',
        },
    }

    def dispatch(self, request, *args, **kwargs):
        self.scope_key = kwargs.get('scope_key', 'kampanya')
        if self.scope_key not in self.SCOPE_META:
            from django.http import Http404
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        meta = self.SCOPE_META[self.scope_key]
        context['scope_key'] = self.scope_key
        context['page_meta'] = meta
        context['message_scope'] = meta['scope']
        url_names = {
            'kampanya': 'outreach_campaign_messages',
            'firma': 'outreach_firm_messages',
            'musteri': 'outreach_customer_messages',
            'personel': 'outreach_personnel_messages',
        }
        context['outreach_nav'] = [
            {'key': k, 'label': v['title'].replace(' kayıtları', ''), 'url_name': url_names[k]}
            for k, v in self.SCOPE_META.items()
        ]
        context['initial_firm_id'] = (self.request.GET.get('firm_id') or '').strip()
        return context


# Geriye dönük uyumluluk
MarketingMessagesView = OutreachMessagesView
