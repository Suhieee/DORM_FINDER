from django.apps import AppConfig

class DormitoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dormitory'

    def ready(self):
        import dormitory.signals  # Ensure signals are loaded!
