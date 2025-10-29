from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile_on_user_creation(sender, instance, created, **kwargs):
    if not created:
        return
    # Ensure a profile exists for every user
    UserProfile.objects.get_or_create(
        user=instance,
        defaults={
            'profile_picture': 'profile_pictures/default.jpg',
        },
    )


