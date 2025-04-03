from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model
from django.conf import settings

class CustomUser(AbstractUser):
    USER_TYPES = (
        ('student', 'Student'),
        ('landlord', 'Landlord'),
        ('admin', 'Admin'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPES, default='student')
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    
    def __str__(self):

        return self.username
    
User = get_user_model()

class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,  # TEMPORARILY allow null values
        blank=True  # Allow it to be empty in forms
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)  # Store dorm ID


    def __str__(self):
        return f"Notification for {self.user.username if self.user else 'Unknown'}: {self.message}"
    
