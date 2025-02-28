from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    USER_TYPES = (
        ('student', 'Student'),
        ('landlord', 'Landlord'),
        ('admin', 'Admin'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPES, default='student')
    contact_number = models.CharField(max_length=15, blank=True, null=True)  # New Field

    def __str__(self):
        return self.username

