from django.apps import AppConfig


class EngageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'engage'
    verbose_name = 'Customer engagement'

    def ready(self):
        from . import signals  # noqa: F401
