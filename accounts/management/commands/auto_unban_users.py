from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import CustomUser
from django.db.models import Q


class Command(BaseCommand):
    help = 'Automatically unban users whose ban period has expired'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        
        # Find users whose ban has expired
        expired_bans = CustomUser.objects.filter(
            is_active=False,
            ban_expires_at__isnull=False,
            ban_expires_at__lte=now
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would unban {expired_bans.count()} users'
                )
            )
            for user in expired_bans:
                self.stdout.write(
                    f'  - {user.username} (banned until {user.ban_expires_at})'
                )
            return
        
        # Actually unban the users
        unbanned_count = 0
        for user in expired_bans:
            user.is_active = True
            user.ban_reason = ''
            user.ban_severity = None
            user.ban_expires_at = None
            user.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Unbanned user: {user.username} (was banned until {user.ban_expires_at})'
                )
            )
            unbanned_count += 1
        
        if unbanned_count == 0:
            self.stdout.write(
                self.style.SUCCESS('No users to unban')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully unbanned {unbanned_count} users'
                )
            ) 