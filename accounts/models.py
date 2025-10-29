from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from datetime import timedelta 

class CustomUser(AbstractUser):
    USER_TYPES = (
        ('student', 'Student'),
        ('landlord', 'Landlord'),
        ('admin', 'Admin'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPES, default='student')
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    ban_reason = models.TextField(null=True, blank=True, help_text='Reason for banning the user')
    ban_expires_at = models.DateTimeField(null=True, blank=True, help_text='When the ban expires (null for permanent)')
    ban_severity = models.CharField(
        max_length=20, 
        choices=[
            ('minor', 'Minor (1 day)'),
            ('moderate', 'Moderate (7 days)'),
            ('major', 'Major (30 days)'),
            ('permanent', 'Permanent'),
        ],
        null=True, 
        blank=True
    )

    def __str__(self):
        return self.username
    
    @property
    def is_banned(self):
        """Check if user is currently banned"""
        if not self.is_active:
            if self.ban_expires_at is None:
                return True  # Permanent ban
            return timezone.now() < self.ban_expires_at
        return False
    
    @property
    def ban_status(self):
        """Get current ban status"""
        if self.is_active:
            return "Active"
        if self.ban_expires_at is None:
            return "Permanently Banned"
        if timezone.now() >= self.ban_expires_at:
            return "Ban Expired"
        return f"Banned until {self.ban_expires_at.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower('email'),
                name='unique_email_ci'
            )
        ]
    
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

class UserReport(models.Model):
    REPORT_REASONS = [
        ('inappropriate_content', 'Inappropriate Content'),
        ('spam', 'Spam'),
        ('harassment', 'Harassment'),
        ('fake_listing', 'Fake Listing'),
        ('scam', 'Scam'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('investigating', 'Under Investigation'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]
    
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_made',
        help_text='User who made the report'
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_received',
        help_text='User being reported'
    )
    reason = models.CharField(max_length=50, choices=REPORT_REASONS)
    description = models.TextField(help_text='Detailed description of the issue')
    evidence = models.TextField(blank=True, null=True, help_text='Any additional evidence or context')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True, null=True, help_text='Admin notes on the report')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports_resolved',
        help_text='Admin who resolved this report'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['reporter', 'reported_user', 'created_at']
    
    def __str__(self):
        return f"Report by {self.reporter.username} on {self.reported_user.username} - {self.get_reason_display()}"
    
    def resolve(self, admin_user, action_taken, notes=""):
        """Resolve the report with admin action"""
        self.status = 'resolved'
        self.resolved_by = admin_user
        self.resolved_at = timezone.now()
        self.admin_notes = f"Action: {action_taken}\nNotes: {notes}"
        self.save()
    
