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
    verification_token_created_at = models.DateTimeField(blank=True, null=True)

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


class TenantPreferences(models.Model):
    """Model to store tenant preferences for smart dorm matching"""
    GENDER_CHOICES = [
        ('male', 'Male Only'),
        ('female', 'Female Only'),
        ('any', 'No Preference'),
    ]
    
    ROOM_TYPE_CHOICES = [
        ('single', 'Single Room'),
        ('shared', 'Shared Room'),
        ('any', 'No Preference'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tenant_preferences')
    
    # Location Preferences
    preferred_location = models.CharField(max_length=255, blank=True, null=True, help_text='Preferred area/location')
    max_distance_km = models.FloatField(default=5.0, help_text='Maximum distance from preferred location (in km)')
    
    # Budget Preferences
    min_budget = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Minimum budget per month')
    max_budget = models.DecimalField(max_digits=10, decimal_places=2, default=10000, help_text='Maximum budget per month')
    
    # Room Preferences
    preferred_gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='any')
    preferred_room_type = models.CharField(max_length=10, choices=ROOM_TYPE_CHOICES, default='any')
    
    # Amenities (Important features)
    wifi_required = models.BooleanField(default=False)
    parking_required = models.BooleanField(default=False)
    laundry_required = models.BooleanField(default=False)
    kitchen_required = models.BooleanField(default=False)
    aircon_required = models.BooleanField(default=False)
    security_required = models.BooleanField(default=False)
    
    # Additional Preferences
    pet_friendly_required = models.BooleanField(default=False)
    study_area_required = models.BooleanField(default=False)
    near_public_transport = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s Preferences"
    
    class Meta:
        verbose_name = "Tenant Preference"
        verbose_name_plural = "Tenant Preferences"
