from django.apps import AppConfig

class FutureConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Future'

    def ready(self):
        import Future.signals
