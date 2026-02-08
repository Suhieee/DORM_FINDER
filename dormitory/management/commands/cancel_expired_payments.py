"""
Django management command to cancel expired payment reservations
Run this as a cron job or scheduled task every 15-30 minutes
Usage: python manage.py cancel_expired_payments
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from dormitory.models import Reservation
from accounts.models import Notification
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Cancel reservations with expired payment deadlines'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cancelled without actually cancelling',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find reservations with expired payment deadlines
        now = timezone.now()
        expired_reservations = Reservation.objects.filter(
            status='pending_payment',
            payment_deadline__lt=now,
            is_payment_overdue=False  # Not already marked as overdue
        ).select_related('dorm', 'tenant', 'dorm__landlord')
        
        count = expired_reservations.count()
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'DRY RUN: Would cancel {count} expired reservations'
            ))
            for reservation in expired_reservations:
                self.stdout.write(
                    f'  - Reservation ID {reservation.id} for {reservation.dorm.name} '
                    f'(Tenant: {reservation.tenant.username}, '
                    f'Deadline: {reservation.payment_deadline})'
                )
            return
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS(
                'No expired reservations found.'
            ))
            return
        
        # Cancel expired reservations
        cancelled_count = 0
        for reservation in expired_reservations:
            try:
                with transaction.atomic():
                    # Mark as overdue
                    reservation.is_payment_overdue = True
                    reservation.status = 'cancelled'
                    reservation.cancellation_reason = 'Payment deadline expired (48 hours)'
                    
                    # Release bed/unit
                    if reservation.dorm.accommodation_type == 'whole_unit':
                        reservation.dorm.available_beds = reservation.dorm.max_occupants
                    else:
                        if reservation.dorm.available_beds < reservation.dorm.total_beds:
                            reservation.dorm.available_beds += 1
                    reservation.dorm.save()
                    
                    # Release room if assigned
                    if reservation.room is not None:
                        reservation.room.is_available = True
                        reservation.room.save()
                    
                    reservation.save()
                    
                    # Notify tenant
                    Notification.objects.create(
                        user=reservation.tenant,
                        message=f'Your reservation for {reservation.dorm.name} was automatically cancelled due to payment deadline expiration.',
                        related_object_id=reservation.id
                    )
                    
                    # Notify landlord
                    Notification.objects.create(
                        user=reservation.dorm.landlord,
                        message=f'Reservation for {reservation.dorm.name} by {reservation.tenant.get_full_name() or reservation.tenant.username} was auto-cancelled (payment deadline expired).',
                        related_object_id=reservation.id
                    )
                    
                    cancelled_count += 1
                    logger.info(
                        f'Cancelled expired reservation ID {reservation.id} '
                        f'for {reservation.dorm.name} (Tenant: {reservation.tenant.username})'
                    )
                    
            except Exception as e:
                logger.error(
                    f'Error cancelling reservation ID {reservation.id}: {str(e)}'
                )
                self.stdout.write(self.style.ERROR(
                    f'Failed to cancel reservation ID {reservation.id}: {str(e)}'
                ))
        
        self.stdout.write(self.style.SUCCESS(
            f'Successfully cancelled {cancelled_count} out of {count} expired reservations.'
        ))
