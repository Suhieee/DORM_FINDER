"""
Transaction Log Model for tracking all landlord activities
"""
from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
from dormitory.models import Dorm, Reservation


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
        ('tenant_moved_in', 'Tenant Moved In'),
        ('tenant_moved_out', 'Tenant Moved Out'),
        ('review_received', 'Review Received'),
        ('dorm_created', 'Dorm Listed'),
        ('dorm_updated', 'Dorm Updated'),
        ('dorm_approved', 'Dorm Approved'),
        ('dorm_rejected', 'Dorm Rejected'),
        ('message_received', 'Message Received'),
        ('inquiry_received', 'Inquiry Received'),
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
    dorm = models.ForeignKey(Dorm, on_delete=models.SET_NULL, null=True, blank=True, related_name='transaction_logs')
    reservation = models.ForeignKey(Reservation, on_delete=models.SET_NULL, null=True, blank=True, related_name='transaction_logs')
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
            'dorm_approved': 'bi-check-circle-fill',
            'dorm_rejected': 'bi-x-circle-fill',
            'message_received': 'bi-chat-dots',
            'inquiry_received': 'bi-envelope',
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
            'dorm_approved': 'text-green-600 bg-green-50',
            'dorm_rejected': 'text-red-600 bg-red-50',
            'message_received': 'text-blue-600 bg-blue-50',
            'inquiry_received': 'text-purple-600 bg-purple-50',
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
