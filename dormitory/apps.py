from django.apps import AppConfig

class DormitoryConfig(AppConfig):
    name = 'dormitory'

    def ready(self):
        try:
            import dormitory.signals  # noqa: F401
        except Exception:
            # avoid breaking management commands if signals import fails
            pass
