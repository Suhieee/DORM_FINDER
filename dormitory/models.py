from django.db import models
from accounts.models import CustomUser
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from django.db.models import Avg
from django.db.models.signals import post_save
from django.dispatch import receiver
from math import radians, sin, cos, sqrt, atan2
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError


CustomUser = settings.AUTH_USER_MODEL  # Use this for flexible user model referencing


class Amenity(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


CustomUser  = get_user_model()

class Dorm(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    ACCOMMODATION_TYPE_CHOICES = (
        ('whole_unit', 'Whole Unit'),
        ('bedspace', 'Bed Space'),
        ('room_sharing', 'Room Sharing'),
    )

    landlord = models.ForeignKey(CustomUser , on_delete=models.CASCADE, limit_choices_to={'user_type': 'landlord'})
    name = models.CharField(max_length=255)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    permit = models.FileField(upload_to='dorm_permits/', null=True, blank=True)
    payment_qr = models.ImageField(upload_to='payment_qr_codes/', null=True, blank=True, help_text="Upload your GCash/Maya QR code for payments")
    available = models.BooleanField(default=True)
    approval_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(null=True, blank=True)
    amenities = models.ManyToManyField("Amenity", blank=True, related_name='dorms')
    nearby_schools = models.ManyToManyField('School', blank=True, related_name='nearby_dorms')
    reservations_count = models.PositiveIntegerField(default=0)
    recent_views = models.PositiveIntegerField(default=0)  # Field to track recent views

    # New fields for enhanced dorm filtering
    accommodation_type = models.CharField(max_length=20, choices=ACCOMMODATION_TYPE_CHOICES, default='whole_unit')
    total_beds = models.PositiveIntegerField(default=1, help_text="Total number of beds available (for bedspace/room sharing)")
    available_beds = models.PositiveIntegerField(default=1, help_text="Number of beds currently available")
    max_occupants = models.PositiveIntegerField(default=1, help_text="Maximum number of occupants allowed")
    created_at = models.DateTimeField(auto_now_add=True)

    def get_average_rating(self):
        average = self.reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
        return round(average, 1) if average else 0


    def __str__(self):
        return f"{self.name} - {self.landlord.username} ({self.landlord.contact_number})"


    def associate_nearby_schools(self, max_distance_km=5.0):
        """Associate schools that are within max_distance_km kilometers of the dorm."""
        if not self.latitude or not self.longitude:
            return

        # Clear existing associations to prevent duplicates
        self.nearby_schools.clear()

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
            distance_km = 6371 * c  # Earth's radius is 6371 km

            if distance_km <= max_distance_km:
                self.nearby_schools.add(school)

    def save(self, *args, **kwargs):
        """Override save to ensure schools are associated whenever a dorm is saved."""
        super().save(*args, **kwargs)
        self.associate_nearby_schools()

@receiver(post_save, sender=Dorm)
def update_reservation_count(sender, instance, created, **kwargs):
    if created:
        instance.reservations_count = 0  # Initialize count on creation
        instance.save()
                
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
        ("quiet", "Quiet and Reserved"),
        ("friendly", "Friendly and Social"),
        ("adventurous", "Adventurous and Outgoing"),
        ("studious", "Studious and Focused"),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, help_text="Your full name")
    age = models.PositiveIntegerField(
        validators=[MinValueValidator(16), MaxValueValidator(100)],
        help_text="Your age (must be between 16 and 100)",
        default=18
    )
    profile_image = models.ImageField(
        upload_to="roommate_profiles/",
        null=True,
        blank=True,
        help_text="Upload a profile picture (optional)"
    )
    contact_number = models.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                regex=r"^9\d{9}$",
                message="Enter a valid Philippine mobile number starting with 9 (e.g., 9123456789)"
            )
        ],
        help_text="Your Philippine mobile number (e.g., 9123456789)"
    )

    hobbies = models.TextField(
        blank=True,
        null=True,
        help_text="List your hobbies and interests"
    )
    mood = models.CharField(
        max_length=20,
        choices=MOOD_CHOICES,
        default="friendly",
        db_index=True,
        help_text="Choose the personality type that best describes you"
    )
    preferred_budget_min = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Minimum monthly budget (in PHP)",
        null=True,
        blank=True,
        default=0
    )
    preferred_budget_max = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Maximum monthly budget (in PHP)",
        null=True,
        blank=True,
        default=0
    )
    preferred_budget = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Average monthly budget (automatically calculated)",
        editable=False,
        null=True,
        blank=True,
        default=0
    )
    preferred_location = models.CharField(
        max_length=255,
        help_text="Where do you want to stay? (e.g., España, Manila near UST)",
        db_index=True
    )
    amenities = models.ManyToManyField(
        "RoommateAmenity",
        blank=True,
        related_name="roommate_posts",
        help_text="Select your preferred amenities"
    )
    description = models.TextField(
        help_text="Describe yourself and what you're looking for in a roommate",
        blank=True
    )
    date_posted = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_posted']
        verbose_name = "Roommate Listing"
        verbose_name_plural = "Roommate Listings"

    def save(self, *args, **kwargs):
        if self.preferred_budget_min and self.preferred_budget_max:
            self.preferred_budget = (self.preferred_budget_min + self.preferred_budget_max) / 2
        super().save(*args, **kwargs)

    def get_compatibility_score(self):
        """Calculate compatibility score with the current user's post."""
        from .services import RoommateMatchingService
        
        # Get the current user's post
        user_post = RoommatePost.objects.filter(user=self.user).first()
        if not user_post or user_post == self:
            return None
            
        # Calculate compatibility score
        score = RoommateMatchingService.calculate_compatibility(user_post, self)
        return round(float(score), 1)

    def __str__(self):
        return f"{self.name} - {self.get_mood_display()} ({self.preferred_location})"

class Message(models.Model):
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField(blank=True)  # Make content optional since we might have only file/image
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    dorm = models.ForeignKey(Dorm, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    reservation = models.ForeignKey('Reservation', on_delete=models.CASCADE, related_name='chat_messages', null=True, blank=True)
    attachment = models.FileField(upload_to='chat_attachments/', null=True, blank=True)
    image = models.ImageField(upload_to='chat_images/', null=True, blank=True)

    def __str__(self):
        return f"Message from {self.sender} to {self.receiver} at {self.timestamp}"

    class Meta:
        ordering = ['timestamp']

    @property
    def is_image(self):
        if self.image:
            return True
        if self.attachment:
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
            return any(self.attachment.name.lower().endswith(ext) for ext in image_extensions)
        return False

    @property
    def get_file_name(self):
        if self.attachment:
            return self.attachment.name.split('/')[-1]
        return None

class Reservation(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Confirmation'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Transaction Completed'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
    )

    dorm = models.ForeignKey(Dorm, on_delete=models.CASCADE, related_name='reservations')
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'user_type': 'student'})
    room = models.ForeignKey('Room', on_delete=models.SET_NULL, null=True, blank=True, related_name='reservations')
    reservation_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_proof = models.ImageField(upload_to='payment_proofs/', null=True, blank=True)
    payment_submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    has_paid_reservation = models.BooleanField(default=False)
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cancellation_reason = models.TextField(blank=True, null=True, help_text='Reason for cancellation if the reservation was cancelled')

    class Meta:
        db_table = 'dormitory_reservation'

    def save(self, *args, **kwargs):
        if not self.id:
            self.created_at = timezone.now()
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.username}'s reservation for {self.dorm.name}"

    @property
    def is_reviewable(self):
        """Check if the reservation is eligible for review."""
        return (
            self.status in ['confirmed', 'completed'] and
            not hasattr(self, 'review')
        )

class Review(models.Model):
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]  # Rating from 1 to 5

    dorm = models.ForeignKey(Dorm, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    reservation = models.OneToOneField(
        'Reservation', 
        on_delete=models.CASCADE,
        related_name="review",
        null=True,
        blank=True
    )
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True, default="No comment provided.")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.dorm.name} ({self.rating}/5)"

    def clean(self):
        if self.reservation and self.reservation.status not in ['confirmed', 'completed']:
            raise ValidationError({
                'reservation': 'Reviews can only be created for confirmed or completed reservations.'
            })

class ReservationMessage(models.Model):
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_reservation_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']
        db_table = 'dormitory_reservation_message'

    def __str__(self):
        return f"Message from {self.sender.username} on {self.timestamp}"

class School(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    def __str__(self):
        return self.name

class RoommateMatch(models.Model):
    initiator = models.ForeignKey(RoommatePost, on_delete=models.CASCADE, related_name='initiated_matches')
    target = models.ForeignKey(RoommatePost, on_delete=models.CASCADE, related_name='received_matches')
    compatibility_score = models.DecimalField(max_digits=5, decimal_places=2)  # Store as percentage
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
        ],
        default='pending'
    )
    
    class Meta:
        unique_together = ('initiator', 'target')
        ordering = ['-compatibility_score']

    def __str__(self):
        return f"{self.initiator.name} → {self.target.name} ({self.compatibility_score}%)"

class RoommateChat(models.Model):
    match = models.ForeignKey(RoommateMatch, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_roommate_messages')
    receiver = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='received_roommate_messages',
        null=True  # Allow null temporarily for migration
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

    def save(self, *args, **kwargs):
        # Auto-set receiver based on match if not set
        if not self.receiver:
            if self.sender == self.match.initiator.user:
                self.receiver = self.match.target.user
            else:
                self.receiver = self.match.initiator.user
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Message from {self.sender.username} at {self.timestamp}"

class Room(models.Model):
    dorm = models.ForeignKey(Dorm, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=100, help_text="Name or label for this room (e.g., Room 1, Bed A)")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Monthly price for this room")
    is_available = models.BooleanField(default=True, help_text="Is this room currently available?")
    description = models.TextField(blank=True, null=True, help_text="Optional description for this room")

    def __str__(self):
        return f"{self.name} in {self.dorm.name}"

class RoomImage(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to='room_images/')

    def __str__(self):
        return f"Image for {self.room.name} in {self.room.dorm.name}"