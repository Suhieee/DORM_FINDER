from django.db import models
from accounts.models import CustomUser
from django.core.validators import RegexValidator
from django.contrib.auth import get_user_model
from django.db.models import Avg
from django.db.models.signals import post_save
from django.dispatch import receiver
from math import radians, sin, cos, sqrt, atan2


class Amenity(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Dorm(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    landlord = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'user_type': 'landlord'})
    name = models.CharField(max_length=255)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)  # Added
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)  # Added
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    permit = models.FileField(upload_to='dorm_permits/', null=True, blank=True)
    available = models.BooleanField(default=True)
    approval_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(null=True, blank=True)
    amenities = models.ManyToManyField("Amenity", blank=True, related_name='dorms')
    nearby_schools = models.ManyToManyField('School', blank=True, related_name='nearby_dorms')

    def get_average_rating(self):
        average = self.reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
        return round(average, 1) if average else 0  # Round to 1 decimal place

    def __str__(self):
        return f"{self.name} - {self.landlord.username} ({self.landlord.contact_number})"
    
    def associate_nearby_schools(self, max_distance_km=2.0):
        """
        Automatically associate this dorm with schools within specified distance.
        Default: 2.0 km radius
        """
        if not self.latitude or not self.longitude:
            return  # Skip if no coordinates
            
        for school in School.objects.all():
            # Convert coordinates to radians
            lat1 = radians(float(self.latitude))
            lon1 = radians(float(self.longitude))
            lat2 = radians(float(school.latitude))
            lon2 = radians(float(school.longitude))
            
            # Haversine formula
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            distance_km = 6371 * c  # Earth's radius in km
            
            if distance_km <= max_distance_km:
                self.nearby_schools.add(school)
                
@receiver(post_save, sender=Dorm)
def auto_associate_schools(sender, instance, created, **kwargs):
    """
    Automatically associate nearby schools when a dorm is saved or updated
    """
    instance.associate_nearby_schools()

class DormImage(models.Model):
    dorm = models.ForeignKey(Dorm, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to='dorm_images/')

    def __str__(self):
        return f"Image for {self.dorm.name}"
    
class RoommateAmenity(models.Model):
    """Amenities for roommate preference."""
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        verbose_name_plural = "Roommate Amenities"

    def __str__(self):
        return self.name


CustomUser = get_user_model()

class RoommatePost(models.Model):
    MOOD_CHOICES = [
        ("quiet", "Quiet"),
        ("friendly", "Friendly"),
        ("adventurous", "Adventurous"),
        ("studious", "Studious"),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    age = models.PositiveIntegerField(null=True, blank=True)  # New field
    profile_image = models.ImageField(upload_to="roommate_profiles/", null=True, blank=True)  # Image field added
    contact_number = models.CharField(
        max_length=15,
        validators=[RegexValidator(regex=r"^\+?\d{9,15}$", message="Enter a valid contact number.")],
        help_text="Provide a contact number for potential roommates."
    )

    hobbies = models.TextField(blank=True, null=True)
    mood = models.CharField(max_length=20, choices=MOOD_CHOICES, default="friendly", db_index=True)
    preferred_budget = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    preferred_location = models.CharField(max_length=255, help_text="Where do you want to stay? (e.g., near UST, UP Diliman)", db_index=True)
    amenities = models.ManyToManyField("RoommateAmenity", blank=True, related_name="roommate_posts")
    
    description = models.TextField(
        help_text="Describe your ideal roommate and preferences.",
        blank=True
    )
    
    date_posted = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.mood} ({self.preferred_location})"

class Review(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]  # Rating from 1 to 5

    dorm = models.ForeignKey(Dorm, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True, default="No comment provided.")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.dorm.name} ({self.rating}/5)"

class School(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    def __str__(self):
        return self.name