from django.db import models
from django.conf import settings

def default_profile_image():
    return "profile_pictures/default.jpg"

class  UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True, default='profile_pictures/default.jpg')

    def __str__(self):
        return f"{self.user.username}'s Profile"
