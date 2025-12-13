from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from dormitory.models import Reservation
from accounts.models import Notification


def notify_user(user, message, related_object_id=None):
    """Create a notification for a user"""
    Notification.objects.create(
        user=user,
        message=message,
        related_object_id=related_object_id
    )


class Command(BaseCommand):
    help = 'Send reminders for upcoming visits and move-ins'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)
        
        # Find visits scheduled for tomorrow (24hr reminder)
        upcoming_visits = Reservation.objects.filter(
            visit_scheduled=True,
            visit_status='scheduled',
            visit_date=tomorrow
        ).select_related('tenant', 'dorm', 'dorm__landlord')
        
        visit_count = 0
        for reservation in upcoming_visits:
            # Send reminder to tenant
            notify_user(
                user=reservation.tenant,
                message=f"⏰ Reminder: You have a property visit tomorrow at {reservation.dorm.name} ({reservation.get_visit_time_slot_display()})",
                related_object_id=reservation.id
            )
            
            # Send reminder to landlord
            notify_user(
                user=reservation.dorm.landlord,
                message=f"⏰ Reminder: {reservation.tenant.get_full_name() or reservation.tenant.username} is visiting {reservation.dorm.name} tomorrow ({reservation.get_visit_time_slot_display()})",
                related_object_id=reservation.id
            )
            
            visit_count += 1
        
        # Find move-ins scheduled for 2 days from now (48hr reminder)
        day_after_tomorrow = today + timedelta(days=2)
        upcoming_moveins_48hr = Reservation.objects.filter(
            move_in_date=day_after_tomorrow,
            status='confirmed'
        ).select_related('tenant', 'dorm', 'dorm__landlord')
        
        movein_48hr_count = 0
        for reservation in upcoming_moveins_48hr:
            # Send 48hr reminder to tenant
            notify_user(
                user=reservation.tenant,
                message=f"⏰ Reminder: Your move-in to {reservation.dorm.name} is in 2 days! ({reservation.move_in_date.strftime('%B %d, %Y')})",
                related_object_id=reservation.id
            )
            
            # Send reminder to landlord
            notify_user(
                user=reservation.dorm.landlord,
                message=f"⏰ Reminder: {reservation.tenant.get_full_name() or reservation.tenant.username} moves in to {reservation.dorm.name} in 2 days",
                related_object_id=reservation.id
            )
            
            movein_48hr_count += 1
        
        # Find move-ins scheduled for tomorrow (24hr reminder)
        upcoming_moveins_24hr = Reservation.objects.filter(
            move_in_date=tomorrow,
            status='confirmed'
        ).select_related('tenant', 'dorm', 'dorm__landlord')
        
        movein_24hr_count = 0
        for reservation in upcoming_moveins_24hr:
            # Send 24hr reminder to tenant
            notify_user(
                user=reservation.tenant,
                message=f"⏰ Final Reminder: Your move-in to {reservation.dorm.name} is TOMORROW! Make sure you're ready. {reservation.move_in_notes[:100] if reservation.move_in_notes else ''}",
                related_object_id=reservation.id
            )
            
            # Send reminder to landlord
            notify_user(
                user=reservation.dorm.landlord,
                message=f"⏰ Reminder: {reservation.tenant.get_full_name() or reservation.tenant.username} moves in to {reservation.dorm.name} tomorrow",
                related_object_id=reservation.id
            )
            
            movein_24hr_count += 1
        
        # Summary
        total = visit_count + movein_48hr_count + movein_24hr_count
        if total > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Sent {visit_count} visit reminders, '
                    f'{movein_48hr_count} 48hr move-in reminders, '
                    f'and {movein_24hr_count} 24hr move-in reminders'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS('✓ No reminders needed at this time'))
