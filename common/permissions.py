PAYROLL_PERM = 'contact.payroll'
FINANCE_PERM = 'accounting.finance'
ACCOUNTING_ACCESS_PERM = 'access.accounting'
TEAM_PERM = 'contact.teams'
PERSONNEL_PERM = 'contact.personnel'

CUSTOMERS_VIEW_PERM = 'contact.customers_view'
CUSTOMERS_EDIT_PERM = 'contact.customers'
CUSTOMERS_DELETE_PERM = 'contact.customers_delete'

SERVICES_MANAGE_PERM = 'services.manage'
SERVICES_DELETE_PERM = 'services.delete'
SERVICES_BULK_PERM = 'services.bulk'
SERVICES_PRINT_PERM = 'services.print'
SERVICES_WHATSAPP_PERM = 'services.whatsapp'

SALES_MANAGE_PERM = 'sales.manage'
SALES_DELETE_PERM = 'sales.delete'
SALES_REPORTS_PERM = 'sales.reports'
SALES_EXPORT_PERM = 'sales.export'


def user_has_perm(user, codename):
    if not user.is_authenticated:
        return False
    return user.has_perm_codename(codename)


def user_has_any_perm(user, *codenames):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    codes = [c for c in codenames if c]
    if not codes:
        return True
    return user.has_any_perm_codename(*codes)


def user_has_role_slug(user, allowed_slugs):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not user.role_id:
        return False
    return user.role.slug in allowed_slugs


def can_view_customers(user):
    return user_has_any_perm(user, CUSTOMERS_VIEW_PERM, CUSTOMERS_EDIT_PERM)


def can_edit_customers(user):
    return user_has_perm(user, CUSTOMERS_EDIT_PERM)


def can_delete_customers(user):
    return user_has_perm(user, CUSTOMERS_DELETE_PERM)


def can_manage_payroll(user):
    return user_has_perm(user, PAYROLL_PERM)


def can_manage_finance(user):
    return user_has_perm(user, FINANCE_PERM)


def can_access_accounting(user):
    return user_has_perm(user, ACCOUNTING_ACCESS_PERM)


def can_manage_teams(user):
    return user_has_perm(user, TEAM_PERM)


def can_manage_personnel(user):
    return user_has_perm(user, PERSONNEL_PERM)


def can_access_personnel_page(user):
    return can_manage_personnel(user)


def resolve_customer_route_permission(path, method):
    """Müşteri URL'leri için middleware izin çözümlemesi."""
    base = '/contact/musteriler'
    if path != base and not path.startswith(base + '/'):
        return None

    if path in (base, base + '/'):
        return (CUSTOMERS_VIEW_PERM, CUSTOMERS_EDIT_PERM)

    write_exact = (
        base + '/yeni/',
        base + '/toplu-sil/',
        base + '/toplu-islem/',
        base + '/hizli-ekle/',
    )
    if path in write_exact:
        if 'toplu-sil' in path:
            return CUSTOMERS_DELETE_PERM
        return CUSTOMERS_EDIT_PERM

    if '/sil/' in path:
        return CUSTOMERS_DELETE_PERM
    if any(part in path for part in ('/duzenle/', '/hizli-duzenle/', '/urunler/')):
        return CUSTOMERS_EDIT_PERM

    if '/medya/yukle/' in path:
        if method == 'POST':
            return (CUSTOMERS_EDIT_PERM, SERVICES_MANAGE_PERM)
        return (CUSTOMERS_VIEW_PERM, CUSTOMERS_EDIT_PERM, SERVICES_MANAGE_PERM)
    if '/medya/' in path and method in ('POST', 'DELETE'):
        return (CUSTOMERS_EDIT_PERM, SERVICES_MANAGE_PERM, 'tools.media_delete')

    if '/api/' in path or '/secim/' in path:
        if method == 'POST' and '/urunler/' in path:
            return CUSTOMERS_EDIT_PERM
        if '/hizli-duzenle/' in path and method == 'POST':
            return CUSTOMERS_EDIT_PERM
        return (CUSTOMERS_VIEW_PERM, CUSTOMERS_EDIT_PERM)

    return (CUSTOMERS_VIEW_PERM, CUSTOMERS_EDIT_PERM)
