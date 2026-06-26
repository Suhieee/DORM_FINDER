from django.core.management.base import BaseCommand
from django.utils import timezone
from dormitory.models import EarlyOutRequest, Reservation, Message
from datetime import date
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Auto-complete reservations for approved early move-outs whose date has arrived'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        today = date.today()

        approved_requests = EarlyOutRequest.objects.filter(
            status='approved',
            requested_moveout_date__lte=today
        ).select_related('reservation', 'reservation__dorm', 'reservation__tenant', 'reservation__room')

        count = approved_requests.count()

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'DRY RUN: Would process {count} approved move-out(s)'
            ))
            for eor in approved_requests:
                res = eor.reservation
                self.stdout.write(
                    f'  - Reservation #{res.id} for {res.dorm.name} '
                    f'(Tenant: {res.tenant.username}, '
                    f'Requested date: {eor.requested_moveout_date})'
                )
            return

        if count == 0:
            self.stdout.write(self.style.SUCCESS('No approved move-outs ready for processing.'))
            return

        processed = 0
        for eor in approved_requests:
            reservation = eor.reservation
            if reservation.status == 'completed':
                continue

            try:
                reservation.move_out_approved = True
                if not reservation.move_out_approved_date:
                    reservation.move_out_approved_date = timezone.now()
                reservation.status = 'completed'
                reservation.completed_at = timezone.now()
                reservation.save()

                if reservation.dorm.accommodation_type == 'whole_unit':
                    reservation.dorm.available_beds = reservation.dorm.max_occupants
                else:
                    if reservation.dorm.available_beds < reservation.dorm.total_beds:
                        reservation.dorm.available_beds += 1
                reservation.dorm.save()

                if reservation.room is not None:
                    reservation.room.is_available = True
                    reservation.room.save()

                if not eor.reviewed_at:
                    eor.reviewed_at = timezone.now()
                    eor.save(update_fields=['reviewed_at'])

                Message.objects.create(
                    sender=reservation.dorm.landlord,
                    receiver=reservation.tenant,
                    content=f"Your move-out from {reservation.dorm.name} has been processed. Thank you for your stay!",
                    dorm=reservation.dorm,
                    reservation=reservation
                )

                processed += 1
                self.stdout.write(f'  - Completed reservation #{reservation.id} for {reservation.dorm.name}')

            except Exception as e:
                logger.error(f'Error processing EarlyOutRequest #{eor.id}: {e}')
                self.stdout.write(self.style.ERROR(
                    f'Failed to process EarlyOutRequest #{eor.id}: {e}'
                ))

        self.stdout.write(self.style.SUCCESS(
            f'Processed {processed} approved move-out(s).'
        ))
