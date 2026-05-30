from users.permission_catalog import PERMISSIONS


def _build_user_perms(user):
    if user.is_superuser:
        return {row[0].replace('.', '_'): True for row in PERMISSIONS}
    codes = user.get_permission_codenames()
    return {row[0].replace('.', '_'): row[0] in codes for row in PERMISSIONS}


def user_access(request):
    user = request.user
    if not user.is_authenticated:
        return {'user_access': {}, 'user_permission_codes': set(), 'user_perms': {}}

    if user.is_superuser:
        access = {
            'home': True,
            'services': True,
            'contact': True,
            'outreach': True,
            'sales': True,
            'accounting': True,
            'tools': True,
            'settings': True,
            'admin_panel': True,
        }
    else:
        access = {
            'home': user.has_perm_codename('access.home'),
            'services': user.has_perm_codename('access.services'),
            'contact': user.has_perm_codename('access.contact'),
            'outreach': user.has_perm_codename('access.outreach'),
            'sales': (
                user.has_perm_codename('sales.manage')
                or user.has_perm_codename('sales.reports')
                or user.has_perm_codename('sales.export')
            ),
            'accounting': user.has_perm_codename('access.accounting'),
            'tools': user.has_perm_codename('access.tools'),
            'settings': user.has_perm_codename('access.settings'),
            'admin_panel': False,
        }

    return {
        'user_access': access,
        'user_permission_codes': user.get_permission_codenames(),
        'user_perms': _build_user_perms(user),
    }
