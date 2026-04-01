from django.db import models
from django.conf import settings
from dormitory.models import Dorm
from django.utils import timezone

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
        ('whole_unit', 'Whole Unit'),
        ('bedspace', 'Bed Space / Shared Space'),
        ('single', 'Single Room'),
        ('shared', 'Shared Room'),
        ('any', 'No Preference'),
    ]
    
    PREFERENCE_CHOICE = [
        ('dorm_only', 'Find Dorm Only'),
        ('dorm_and_roommate', 'Find Dorm and Roommate'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tenant_preferences')
    
    # User's initial preference choice
    preference_choice = models.CharField(
        max_length=20, 
        choices=PREFERENCE_CHOICE, 
        default='dorm_only',
        help_text='Whether user wants to find just dorm or dorm + roommate'
    )
    
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
    
    # Roommate Preferences
    ROOMMATE_MOOD_CHOICES = [
        ('quiet', 'Quiet and Reserved'),
        ('friendly', 'Friendly and Social'),
        ('adventurous', 'Adventurous and Outgoing'),
        ('studious', 'Studious and Focused'),
        ('any', 'No Preference'),
    ]
    
    ROOMMATE_AGE_RANGE_CHOICES = [
        ('18-25', '18-25 years'),
        ('26-35', '26-35 years'),
        ('36-50', '36-50 years'),
        ('any', 'No Preference'),
    ]
    
    # Roommate matching preferences
    preferred_roommate_mood = models.CharField(
        max_length=20,
        choices=ROOMMATE_MOOD_CHOICES,
        default='any',
        help_text='Preferred roommate personality type'
    )
    preferred_roommate_age_range = models.CharField(
        max_length=10,
        choices=ROOMMATE_AGE_RANGE_CHOICES,
        default='any',
        help_text='Preferred roommate age range'
    )
    preferred_roommate_gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        default='any',
        help_text='Preferred roommate gender'
    )
    roommate_budget_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Minimum budget for roommate search (optional)'
    )
    roommate_budget_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=10000,
        help_text='Maximum budget for roommate search (optional)'
    )
    roommate_preferred_location = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text='Preferred location for roommate search'
    )
    roommate_cleanliness_important = models.BooleanField(
        default=False,
        help_text='Is cleanliness important to you?'
    )
    roommate_quiet_environment = models.BooleanField(
        default=False,
        help_text='Do you prefer a quiet environment?'
    )
    roommate_social_activities = models.BooleanField(
        default=False,
        help_text='Do you enjoy social activities with roommates?'
    )
    roommate_shared_expenses = models.BooleanField(
        default=False,
        help_text='Open to sharing household expenses?'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def sync_to_roommate_post(self):
        """
        Create or update a RoommatePost based on preferences.
        Only call this when user has chosen 'dorm_and_roommate'.
        """
        from dormitory.models import RoommatePost, RoommateAmenity
        
        # Get contact number from user, default to placeholder if not set
        contact_number = self.user.contact_number or '9000000000'
        
        # Get age - default to 18 if not available
        age = getattr(self.user, 'age', 18) or 18
        
        # Check if user already has a roommate post
        roommate_post, created = RoommatePost.objects.get_or_create(
            user=self.user,
            defaults={
                'name': self.user.get_full_name() or self.user.username,
                'age': age,
                'contact_number': contact_number,
                'mood': self.preferred_roommate_mood if self.preferred_roommate_mood != 'any' else 'friendly',
                'preferred_budget_min': self.roommate_budget_min,
                'preferred_budget_max': self.roommate_budget_max,
                'preferred_location': self.roommate_preferred_location or self.preferred_location or '',
                'description': self._generate_roommate_description(),
            }
        )
        
        # If post already exists, update it
        if not created:
            roommate_post.name = self.user.get_full_name() or self.user.username
            roommate_post.age = age
            roommate_post.contact_number = contact_number
            roommate_post.mood = self.preferred_roommate_mood if self.preferred_roommate_mood != 'any' else 'friendly'
            roommate_post.preferred_budget_min = self.roommate_budget_min
            roommate_post.preferred_budget_max = self.roommate_budget_max
            roommate_post.preferred_location = self.roommate_preferred_location or self.preferred_location or ''
            roommate_post.description = self._generate_roommate_description()
            roommate_post.save()
        
        # Handle amenities ManyToManyField
        amenities_list = self._get_required_amenities_objects()
        roommate_post.amenities.set(amenities_list)
        
        return roommate_post
    
    def _get_required_amenities_list(self):
        """Get list of required amenities as a comma-separated string."""
        amenities = []
        if self.wifi_required:
            amenities.append('WiFi')
        if self.parking_required:
            amenities.append('Parking')
        if self.laundry_required:
            amenities.append('Laundry')
        if self.kitchen_required:
            amenities.append('Kitchen')
        if self.aircon_required:
            amenities.append('Air Conditioning')
        if self.security_required:
            amenities.append('Security')
        if self.pet_friendly_required:
            amenities.append('Pet Friendly')
        if self.study_area_required:
            amenities.append('Study Area')
        if self.near_public_transport:
            amenities.append('Near Public Transport')
        
        return ', '.join(amenities) if amenities else 'No specific requirements'
    
    def _get_required_amenities_objects(self):
        """Get list of RoommateAmenity objects based on preferences."""
        from dormitory.models import RoommateAmenity
        
        amenities = []
        amenity_mapping = {
            'wifi_required': 'WiFi',
            'parking_required': 'Parking',
            'laundry_required': 'Laundry',
            'kitchen_required': 'Kitchen',
            'aircon_required': 'Air Conditioning',
            'security_required': 'Security',
            'pet_friendly_required': 'Pet Friendly',
            'study_area_required': 'Study Area',
            'near_public_transport': 'Near Public Transport',
        }
        
        for field_name, amenity_name in amenity_mapping.items():
            if getattr(self, field_name, False):
                amenity_obj, created = RoommateAmenity.objects.get_or_create(name=amenity_name)
                amenities.append(amenity_obj)
        
        return amenities
    
    def _generate_roommate_description(self):
        """Generate a description based on preferences."""
        traits = []
        
        # Add personality traits
        if self.preferred_roommate_mood and self.preferred_roommate_mood != 'any':
            traits.append(f"Looking for {self.preferred_roommate_mood} roommate")
        
        # Add lifestyle preferences
        if self.roommate_cleanliness_important:
            traits.append("values cleanliness")
        if self.roommate_quiet_environment:
            traits.append("prefers quiet environment")
        if self.roommate_social_activities:
            traits.append("enjoys social activities")
        if self.roommate_shared_expenses:
            traits.append("open to shared expenses")
        
        # Add budget info
        if self.roommate_budget_min and self.roommate_budget_max:
            traits.append(f"Budget: ₱{self.roommate_budget_min:,.0f} - ₱{self.roommate_budget_max:,.0f}")
        
        description = ". ".join(traits) if traits else "Looking for a compatible roommate"
        return description + "."
    
    def __str__(self):
        return f"{self.user.username}'s Preferences"
    
    class Meta:
        verbose_name = "Tenant Preference"
        verbose_name_plural = "Tenant Preferences"
