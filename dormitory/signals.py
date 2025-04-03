from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Dorm
from accounts.models import Notification  # Import Notification model

@receiver(post_save, sender=Dorm)
def dorm_approval_notification(sender, instance, created, **kwargs):
    """Send a notification when a dorm gets approved, but prevent duplicates."""
    if not created and instance.approval_status == "approved":
        # Check if a notification already exists for this dorm approval
        existing_notification = Notification.objects.filter(
            user=instance.landlord,
            message=f"Your dorm '{instance.name}' has been approved!"
        ).exists()

        if not existing_notification:
            Notification.objects.create(
                user=instance.landlord,
                message=f"Your dorm '{instance.name}' has been approved!",
                related_object_id=instance.id,  # Ensure you store dorm ID for linking
            )
