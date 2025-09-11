from django.db import models
from django.conf import settings
from dormitory.models import Dorm

def default_profile_image():
    return "profile_pictures/default.jpg"

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True, default='profile_pictures/default.jpg')
    favorite_dorms = models.ManyToManyField(Dorm, through='FavoriteDorm', related_name='favorited_by')
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=64, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

class FavoriteDorm(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    dorm = models.ForeignKey(Dorm, on_delete=models.CASCADE)
    added_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user_profile', 'dorm')
        ordering = ['-added_date']

    def __str__(self):
        return f"{self.user_profile.user.username}'s favorite: {self.dorm.name}"

class UserInteraction(models.Model):
    INTERACTION_CHOICES = [
        ('view', 'View'),
        ('favorite', 'Favorite'),
        ('book', 'Book'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    dorm = models.ForeignKey(Dorm, on_delete=models.CASCADE)
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'dorm', 'interaction_type', 'timestamp')
