"""Pazarlama — kampanya, firma, müşteri ve personel mesaj geçmişi (contact firmalardan ayrı)."""

from django.views.generic import TemplateView


class MarketingMessagesView(TemplateView):
    template_name = 'crm/marketing_messages.html'

    SCOPE_META = {
        'kampanya': {
            'title': 'Kampanya mesajları',
            'subtitle': 'Koleksiyon ve toplu kampanya gönderimleri — firma rehberinden bağımsız.',
            'icon': 'megaphone',
            'scope': 'campaign',
            'empty_hint': 'Henüz kampanya mesajı yok. Firmalar rehberinden koleksiyon oluşturup gönderin.',
            'action_url_name': 'contact_firmalar',
            'action_label': 'Firma rehberi',
        },
        'firma': {
            'title': 'Firma mesajları',
            'subtitle': 'Tekil ve toplu firma outreach (kampanya dışı): kazınan, ortak, bayi, özel mesaj.',
            'icon': 'building-2',
            'scope': 'firm',
            'empty_hint': 'Kampanya dışı firma mesajı bulunamadı.',
            'action_url_name': 'contact_firmalar',
            'action_label': 'Firma rehberi',
        },
        'musteri': {
            'title': 'Müşteri mesajları',
            'subtitle': 'Müşteri kartlarına giden WhatsApp kayıtları.',
            'icon': 'users',
            'scope': 'customer',
            'empty_hint': 'Müşteriye gönderilmiş mesaj yok.',
            'action_url_name': 'customers',
            'action_label': 'Müşteriler',
        },
        'personel': {
            'title': 'Personel mesajları',
            'subtitle': 'Otomatik senaryolar ve dahili bildirimler (müşteri / firma kampanyası hariç).',
            'icon': 'id-card',
            'scope': 'personnel',
            'empty_hint': 'Personel / dahili otomatik mesaj kaydı yok.',
            'action_url_name': 'personnel_network',
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
            'kampanya': 'marketing_campaign_messages',
            'firma': 'marketing_firm_messages',
            'musteri': 'marketing_customer_messages',
            'personel': 'marketing_personnel_messages',
        }
        context['marketing_nav'] = [
            {'key': k, 'label': v['title'], 'url_name': url_names[k]}
            for k, v in self.SCOPE_META.items()
        ]
        context['initial_firm_id'] = (self.request.GET.get('firm_id') or '').strip()
        return context
