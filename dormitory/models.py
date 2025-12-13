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
    payment_terms = models.TextField(null=True, blank=True, help_text="Payment terms (e.g., '3 months deposit, 1 month advance')")
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
    key_features = models.TextField(null=True, blank=True, help_text="Short highlights, one per line")

    def get_average_rating(self):
        average = self.reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
        return round(average, 1) if average else 0
    # ADD THIS METHOD HERE:
    def is_reservable(self):
        """
        Check if dorm can be reserved.
        For whole_unit: Check if there's an active reservation (confirmed or occupied)
        For other types: Use existing available_beds logic
        """
        if not self.available or self.approval_status != 'approved':
            return False
        
        if self.accommodation_type == 'whole_unit':
            # Check if there's any active reservation
            # Active means: confirmed (payment verified) or occupied (tenant moved in)
            # 'completed' means tenant moved out, so dorm is available again
            active_reservation = self.reservations.filter(
                status__in=['confirmed', 'occupied']  # Check for both active statuses
            ).exists()
            return not active_reservation
        else:
            # For bedspace/room_sharing, use available_beds count
            return self.available_beds > 0

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

    def get_profile_image_url(self):
        """
        Safely get profile image URL with fallback to default image
        """
        if self.profile_image and hasattr(self.profile_image, 'url'):
            return self.profile_image.url
        return '/static/images/default-profile.png'  # Path to your default image


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

class DormVisit(models.Model):
    """Visit scheduling system - students schedule visits before making reservations"""
    STATUS_CHOICES = (
        ('pending', 'Pending Landlord Confirmation'),
        ('confirmed', 'Visit Confirmed'),
        ('completed', 'Visit Completed'),
        ('cancelled', 'Cancelled'),
        ('declined', 'Declined by Landlord'),
        ('no_show', 'Student Did Not Show Up'),
    )
    
    TIME_SLOT_CHOICES = (
        ('09:00-11:00', '9:00 AM - 11:00 AM'),
        ('11:00-13:00', '11:00 AM - 1:00 PM'),
        ('13:00-15:00', '1:00 PM - 3:00 PM'),
        ('15:00-17:00', '3:00 PM - 5:00 PM'),
        ('17:00-19:00', '5:00 PM - 7:00 PM'),
    )
    
    dorm = models.ForeignKey(Dorm, on_delete=models.CASCADE, related_name='visits')
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, 
                                limit_choices_to={'user_type': 'tenant'},
                                related_name='dorm_visits')
    visit_date = models.DateField()
    time_slot = models.CharField(max_length=20, choices=TIME_SLOT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    student_message = models.TextField(blank=True, null=True, 
                                       help_text="Message from student to landlord")
    landlord_notes = models.TextField(blank=True, null=True,
                                      help_text="Internal notes from landlord")
    
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        db_table = 'dormitory_visit'
    
    def clean(self):
        from datetime import timedelta
        
        # Only validate if we have the required fields
        if not self.visit_date:
            return
        
        # Validate visit date is within next 7 days
        today = timezone.now().date()
        max_date = today + timedelta(days=7)
        
        if self.visit_date < today:
            raise ValidationError("Visit date cannot be in the past.")
        
        if self.visit_date > max_date:
            raise ValidationError("Visit date must be within the next 7 days.")
        
        # Check if time slot is already booked (only if dorm is set)
        if self.dorm_id and self.time_slot:
            conflicting_visits = DormVisit.objects.filter(
                dorm=self.dorm,
                visit_date=self.visit_date,
                time_slot=self.time_slot,
                status__in=['pending', 'confirmed']
            ).exclude(pk=self.pk if self.pk else None)
            
            if conflicting_visits.exists():
                raise ValidationError("This time slot is already booked.")
    
    def save(self, *args, **kwargs):
        # Only run validation if we have the minimum required fields
        if self.dorm_id and self.visit_date and self.time_slot:
            self.full_clean()  # Run validation
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.student.username} visiting {self.dorm.name} on {self.visit_date}"
    
    @property
    def can_convert_to_reservation(self):
        """Check if this visit can be converted to a reservation"""
        return self.status == 'completed' and not hasattr(self, 'reservation')
    
    @property
    def is_upcoming(self):
        """Check if visit is in the future"""
        return self.visit_date >= timezone.now().date() and self.status in ['pending', 'confirmed']


class Reservation(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Confirmation'),
        ('pending_payment', 'Awaiting Payment'),
        ('confirmed', 'Confirmed'),
        ('occupied', 'Tenant Checked In'),
        ('completed', 'Tenant Moved Out'),
        ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
    )
    
    VISIT_STATUS_CHOICES = (
        ('not_scheduled', 'Not Scheduled'),
        ('scheduled', 'Visit Scheduled'),
        ('completed', 'Visit Completed'),
        ('cancelled', 'Visit Cancelled'),
    )
    
    TIME_SLOT_CHOICES = (
        ('09:00-11:00', '9:00 AM - 11:00 AM'),
        ('11:00-13:00', '11:00 AM - 1:00 PM'),
        ('13:00-15:00', '1:00 PM - 3:00 PM'),
        ('15:00-17:00', '3:00 PM - 5:00 PM'),
        ('17:00-19:00', '5:00 PM - 7:00 PM'),
    )

    dorm = models.ForeignKey(Dorm, on_delete=models.CASCADE, related_name='reservations')
    tenant = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'user_type': 'tenant'})
    room = models.ForeignKey('Room', on_delete=models.SET_NULL, null=True, blank=True, related_name='reservations')
    visit = models.OneToOneField('DormVisit', on_delete=models.SET_NULL, 
                                  null=True, blank=True,
                                  related_name='reservation',
                                  help_text="The visit that led to this reservation")
    reservation_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_proof = models.ImageField(upload_to='payment_proofs/', null=True, blank=True)
    payment_submitted_at = models.DateTimeField(null=True, blank=True)
    payment_deadline = models.DateTimeField(null=True, blank=True,
                                           help_text="Deadline for payment (48 hours from reservation)")
    is_payment_overdue = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    has_paid_reservation = models.BooleanField(default=False)
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cancellation_reason = models.TextField(blank=True, null=True, help_text='Reason for cancellation if the reservation was cancelled')
    
    # Visit scheduling fields
    visit_scheduled = models.BooleanField(default=False, help_text="Whether landlord scheduled a visit")
    visit_status = models.CharField(max_length=20, choices=VISIT_STATUS_CHOICES, default='not_scheduled')
    visit_date = models.DateField(null=True, blank=True, help_text="Scheduled visit date")
    visit_time_slot = models.CharField(max_length=20, choices=TIME_SLOT_CHOICES, null=True, blank=True)
    visit_notes = models.TextField(blank=True, help_text="Landlord notes about the visit")
    visit_completed_at = models.DateTimeField(null=True, blank=True)
    
    # Move-in fields
    move_in_date = models.DateField(null=True, blank=True, help_text="Scheduled move-in date")
    move_in_notes = models.TextField(blank=True, help_text="Move-in instructions from landlord")
    
    # Move-in checklist
    checklist_keys_received = models.BooleanField(default=False)
    checklist_property_inspected = models.BooleanField(default=False)
    checklist_inventory_checked = models.BooleanField(default=False)
    checklist_rules_acknowledged = models.BooleanField(default=False)
    checklist_completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'dormitory_reservation'

    def save(self, *args, **kwargs):
        from datetime import timedelta
        
        if not self.id:
            self.created_at = timezone.now()
            # Set payment deadline for pending_payment status
            if self.status == 'pending_payment' and not self.payment_deadline:
                self.payment_deadline = timezone.now() + timedelta(hours=48)
        
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tenant.username}'s reservation for {self.dorm.name}"

    @property
    def is_reviewable(self):
        """Check if the reservation is eligible for review."""
        return (
            self.status in ['confirmed', 'completed'] and
            not hasattr(self, 'review')
        )
    
    @property
    def hours_until_payment_deadline(self):
        """Calculate hours remaining until payment deadline"""
        if not self.payment_deadline:
            return None
        
        remaining = self.payment_deadline - timezone.now()
        return max(0, remaining.total_seconds() / 3600)  # Convert to hours
    
    @property
    def payment_deadline_passed(self):
        """Check if payment deadline has passed"""
        if not self.payment_deadline:
            return False
        
        return timezone.now() > self.payment_deadline

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

    def get_reactions_summary(self):
        """Get a summary of reactions for this message"""
        reactions = self.reactions.values('emoji').annotate(count=models.Count('id'))
        return {r['emoji']: r['count'] for r in reactions}

    def __str__(self):
        return f"Message from {self.sender.username} at {self.timestamp}"

class RoommateChatReaction(models.Model):
    EMOJI_CHOICES = [
        ('👍', 'Thumbs Up'),
        ('❤️', 'Heart'),
        ('😊', 'Smile'),
        ('😂', 'Laugh'),
        ('😮', 'Wow'),
        ('😢', 'Sad'),
        ('😡', 'Angry'),
    ]
    
    message = models.ForeignKey(RoommateChat, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=10, choices=EMOJI_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user', 'emoji')  # One reaction per user per emoji per message
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.username} reacted {self.emoji} to message {self.message.id}"

class Room(models.Model):
    dorm = models.ForeignKey(Dorm, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=100, help_text="Name or label for this room (e.g., Room 1, Bed A)")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Monthly price for this room")
    is_available = models.BooleanField(default=True, help_text="Is this room currently available?")
    description = models.TextField(blank=True, null=True, help_text="Optional description for this room")

    # 🔹 New optional fields to make it richer
    room_type = models.CharField(
        max_length=50,
        choices=[('single', 'Single'), ('double', 'Double'), ('shared', 'Shared')],
        default='single'
    )
    capacity = models.PositiveIntegerField(default=1, help_text="Number of people this room can accommodate")
    size = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True, help_text="Size in square meters")
    floor_number = models.PositiveIntegerField(blank=True, null=True, help_text="Floor where the room is located")

    def __str__(self):
        return f"{self.name} in {self.dorm.name}"

class RoomImage(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to='room_images/')

    def __str__(self):
        return f"Image for {self.room.name} in {self.room.dorm.name}"


# ============================================
# Transaction Log Model
# ============================================
class TransactionLog(models.Model):
    """
    Tracks all transactions and activities for landlords
    """
    TRANSACTION_TYPES = (
        ('reservation_created', 'Reservation Created'),
        ('reservation_confirmed', 'Reservation Confirmed'),
        ('reservation_cancelled', 'Reservation Cancelled'),
        ('payment_received', 'Payment Received'),
        ('payment_verified', 'Payment Verified'),
        ('payment_rejected', 'Payment Rejected'),
        ('visit_scheduled', 'Visit Scheduled'),
        ('visit_completed', 'Visit Completed'),
        ('visit_cancelled', 'Visit Cancelled'),
        ('tenant_moved_in', 'Tenant Checked In'),
        ('tenant_moved_out', 'Tenant Moved Out'),
        ('review_received', 'Review Received'),
        ('dorm_created', 'Dorm Listed'),
        ('dorm_updated', 'Dorm Updated'),
        ('message_received', 'Message Received'),
    )
    
    STATUS_CHOICES = (
        ('success', 'Success'),
        ('pending', 'Pending'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )

    landlord = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='transaction_logs',
        limit_choices_to={'user_type': 'landlord'}
    )
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='success')
    dorm = models.ForeignKey('Dorm', on_delete=models.SET_NULL, null=True, blank=True, related_name='transaction_logs')
    reservation = models.ForeignKey('Reservation', on_delete=models.SET_NULL, null=True, blank=True, related_name='transaction_logs')
    tenant = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenant_transaction_logs',
        limit_choices_to={'user_type': 'tenant'}
    )
    
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Transaction amount if applicable")
    description = models.TextField(help_text="Description of the transaction")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional transaction details")
    
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['landlord', '-created_at']),
            models.Index(fields=['transaction_type', '-created_at']),
            models.Index(fields=['dorm', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.landlord.get_full_name()} - {self.get_transaction_type_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def icon(self):
        """Return icon class based on transaction type"""
        icons = {
            'reservation_created': 'bi-calendar-plus',
            'reservation_confirmed': 'bi-check-circle',
            'reservation_cancelled': 'bi-x-circle',
            'payment_received': 'bi-cash-coin',
            'payment_verified': 'bi-check2-circle',
            'payment_rejected': 'bi-x-octagon',
            'visit_scheduled': 'bi-calendar-event',
            'visit_completed': 'bi-calendar-check',
            'visit_cancelled': 'bi-calendar-x',
            'tenant_moved_in': 'bi-house-door',
            'tenant_moved_out': 'bi-house-door-fill',
            'review_received': 'bi-star-fill',
            'dorm_created': 'bi-building-add',
            'dorm_updated': 'bi-pencil-square',
            'message_received': 'bi-chat-dots',
        }
        return icons.get(self.transaction_type, 'bi-info-circle')
    
    @property
    def color_class(self):
        """Return color class based on transaction type"""
        colors = {
            'reservation_created': 'text-blue-600 bg-blue-50',
            'reservation_confirmed': 'text-green-600 bg-green-50',
            'reservation_cancelled': 'text-red-600 bg-red-50',
            'payment_received': 'text-green-600 bg-green-50',
            'payment_verified': 'text-green-700 bg-green-100',
            'payment_rejected': 'text-red-600 bg-red-50',
            'visit_scheduled': 'text-blue-600 bg-blue-50',
            'visit_completed': 'text-green-600 bg-green-50',
            'visit_cancelled': 'text-gray-600 bg-gray-50',
            'tenant_moved_in': 'text-purple-600 bg-purple-50',
            'tenant_moved_out': 'text-orange-600 bg-orange-50',
            'review_received': 'text-yellow-600 bg-yellow-50',
            'dorm_created': 'text-indigo-600 bg-indigo-50',
            'dorm_updated': 'text-blue-600 bg-blue-50',
            'message_received': 'text-blue-600 bg-blue-50',
        }
        return colors.get(self.transaction_type, 'text-gray-600 bg-gray-50')
    
    @classmethod
    def log_transaction(cls, landlord, transaction_type, description, dorm=None, reservation=None, tenant=None, amount=None, status='success', metadata=None):
        """
        Helper method to create a transaction log entry
        """
        return cls.objects.create(
            landlord=landlord,
            transaction_type=transaction_type,
            status=status,
            dorm=dorm,
            reservation=reservation,
            tenant=tenant,
            amount=amount,
            description=description,
            metadata=metadata or {}
        )