from django.apps import AppConfig


class CustomersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'customers'

    def ready(self):
        from . import signals  # noqa: F401
        from . import media_signals  # noqa: F401
