"""Kullanıcı adlarını arayüzde okunabilir etiketlere çevirir."""

RBAC_TEST_PREFIX = '_rbac_'

RBAC_USERNAME_LABELS = {
    '_rbac_muhasebe': 'Muhasebe',
    '_rbac_satis': 'Satış Temsilcisi',
    '_rbac_servis': 'Servis Personeli',
    '_rbac_operasyon': 'Operasyon',
}


def is_rbac_test_username(username: str) -> bool:
    return (username or '').startswith(RBAC_TEST_PREFIX)


def humanize_username(username: str, *, role_name: str = '') -> str:
    """SQL/test kullanıcı adını arayüz etiketine çevirir."""
    if not username:
        return ''
    if username in RBAC_USERNAME_LABELS:
        return RBAC_USERNAME_LABELS[username]
    if is_rbac_test_username(username):
        if role_name:
            return role_name
        slug = username[len(RBAC_TEST_PREFIX):]
        return slug.replace('_', ' ').replace('-', ' ').title()
    return username
