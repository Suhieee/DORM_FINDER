"""
Management command to check payment deadlines and auto-cancel overdue reservations.
Run this command periodically (e.g., every hour) using a cron job or task scheduler.

Usage:
    python manage.py check_payment_deadlines
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from dormitory.models import Reservation
from accounts.models import Notification


class Command(BaseCommand):
    help = 'Check for overdue payment deadlines and auto-cancel reservations'
    
    def handle(self, *args, **kwargs):
        now = timezone.now()
        
        # Find reservations with overdue payments
        overdue_reservations = Reservation.objects.filter(
            status='pending_payment',
            payment_deadline__lt=now,
            is_payment_overdue=False
        ).select_related('tenant', 'dorm', 'dorm__landlord')
        
        cancelled_count = 0
        for reservation in overdue_reservations:
            # Mark as overdue and cancelled
            reservation.status = 'cancelled'
            reservation.is_payment_overdue = True
            reservation.cancellation_reason = "Payment deadline expired (48 hours)"
            reservation.save()
            
            # Notify student
            Notification.objects.create(
                user=reservation.tenant,
                message=f"Your reservation for {reservation.dorm.name} was cancelled due to payment timeout (48 hours).",
                related_object_id=reservation.id
            )
            
            # Notify landlord
            Notification.objects.create(
                user=reservation.dorm.landlord,
                message=f"Reservation by {reservation.tenant.get_full_name() or reservation.tenant.username} was auto-cancelled (payment timeout).",
                related_object_id=reservation.id
            )
            
            cancelled_count += 1
            self.stdout.write(
                self.style.WARNING(
                    f'Cancelled reservation #{reservation.id} for {reservation.tenant.username} - {reservation.dorm.name}'
                )
            )
        
        if cancelled_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Cancelled {cancelled_count} overdue reservation(s)')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('✓ No overdue reservations found')
            )
