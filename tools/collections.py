from tools.models import MapsScrapedFirm, OutreachCollection, OutreachCollectionMember

from tools.outreach_memory import ensure_firm_record, get_sent_count, has_been_messaged_globally

from tools.phone_utils import is_turkish_landline, is_whatsapp_eligible, normalize_phone





DEFAULT_TEMPLATE = """Merhaba {firma},

Sizinle iletişime geçmek istedik. Uygun olduğunuzda kısaca görüşebilir miyiz?

İyi çalışmalar."""





def get_or_create_default_collection():

    col = OutreachCollection.objects.order_by('-updated_at').first()

    if col:

        return col

    return OutreachCollection.objects.create(

        name='Genel Kampanya',

        message_template=DEFAULT_TEMPLATE,

        skip_globally_messaged=False,

        allow_repeat_in_campaign=True,

    )





def serialize_member(member: OutreachCollectionMember) -> dict:

    firm = member.firm

    name = member.name or (firm.name if firm else 'İsimsiz')

    phone_display = member.phone_display or member.phone_normalized

    messages_sent = get_sent_count(member.phone_normalized)

    wa_eligible = is_whatsapp_eligible(phone_display, member.phone_normalized)

    globally_messaged = has_been_messaged_globally(member.phone_normalized)



    return {

        'id': member.id,

        'firm_id': firm.id if firm else None,

        'name': name,

        'phone': phone_display,

        'phone_normalized': member.phone_normalized,

        'messages_sent': messages_sent,

        'globally_messaged': globally_messaged,

        'whatsapp_eligible': wa_eligible,

        'is_landline': is_turkish_landline(phone_display, member.phone_normalized),
        'custom_message': member.custom_message or '',
    }




def serialize_collection(collection: OutreachCollection, *, include_members=False) -> dict:

    data = {

        'id': collection.id,

        'name': collection.name,

        'message_template': collection.message_template or DEFAULT_TEMPLATE,

        'skip_globally_messaged': collection.skip_globally_messaged,

        'allow_repeat_in_campaign': collection.allow_repeat_in_campaign,

        'delay_seconds': collection.delay_seconds,

        'member_count': collection.members.count(),

        'created_at': collection.created_at.isoformat(),

        'updated_at': collection.updated_at.isoformat(),

    }

    if include_members:

        members = collection.members.select_related('firm').order_by('id')

        data['members'] = [serialize_member(m) for m in members]

    return data





def add_customer_to_collection(collection: OutreachCollection, customer) -> tuple[OutreachCollectionMember | None, str | None]:
    phone_raw = (customer.phone or '').strip()
    if not phone_raw:
        return None, 'Telefon yok'
    return add_manual_to_collection(collection, customer.name, phone_raw)


def add_firm_to_collection(collection: OutreachCollection, firm: MapsScrapedFirm) -> tuple[OutreachCollectionMember | None, str | None]:

    if not firm.phone_normalized:

        return None, 'Telefon yok'

    if not is_whatsapp_eligible(firm.phone, firm.phone_normalized):

        return None, 'Sabit hat'

    if OutreachCollectionMember.objects.filter(collection=collection, phone_normalized=firm.phone_normalized).exists():

        return None, 'Zaten listede'

    member = OutreachCollectionMember.objects.create(

        collection=collection,

        firm=firm,

        name=firm.name,

        phone_normalized=firm.phone_normalized,

        phone_display=firm.phone,

    )

    return member, None





def add_manual_to_collection(collection: OutreachCollection, name: str, phone_raw: str) -> tuple[OutreachCollectionMember | None, str | None]:

    phone_norm = normalize_phone(phone_raw)

    if not phone_norm:

        return None, 'Geçersiz telefon'

    if not is_whatsapp_eligible(phone_raw, phone_norm):

        return None, 'Sabit hat'

    if OutreachCollectionMember.objects.filter(collection=collection, phone_normalized=phone_norm).exists():

        return None, 'Zaten listede'



    firm = ensure_firm_record(name=name, phone_raw=phone_raw, phone_normalized=phone_norm, notes='Manuel eklendi')

    member = OutreachCollectionMember.objects.create(

        collection=collection,

        firm=firm,

        name=name or firm.name,

        phone_normalized=phone_norm,

        phone_display=phone_raw,

    )

    return member, None


