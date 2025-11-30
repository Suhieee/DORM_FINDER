from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
import getpass
import sys

User = get_user_model()


class Command(BaseCommand):
    help = 'Create a superuser for production deployment. This command connects to the production database based on environment variables.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username for the superuser',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email for the superuser',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            help='Use provided arguments without prompting (requires --username, --email, and password via environment variable)',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password for the superuser (not recommended, use environment variable instead)',
        )

    def handle(self, *args, **options):
        username = options.get('username')
        email = options.get('email')
        password = options.get('password')
        noinput = options.get('noinput', False)

        # Check if superuser already exists
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.WARNING(
                    'A superuser already exists. Use Django admin or update the existing user.'
                )
            )
            if not noinput:
                response = input('Do you want to create another superuser? (yes/no): ')
                if response.lower() != 'yes':
                    self.stdout.write(self.style.SUCCESS('Operation cancelled.'))
                    return

        # Collect username
        if not username:
            if noinput:
                self.stdout.write(
                    self.style.ERROR('Error: --username is required when using --noinput')
                )
                sys.exit(1)
            username = input('Username: ')
            if not username:
                self.stdout.write(self.style.ERROR('Error: Username cannot be empty'))
                sys.exit(1)

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.ERROR(f'Error: Username "{username}" already exists.')
            )
            sys.exit(1)

        # Collect email
        if not email:
            if noinput:
                self.stdout.write(
                    self.style.ERROR('Error: --email is required when using --noinput')
                )
                sys.exit(1)
            email = input('Email address: ')
            if not email:
                self.stdout.write(self.style.ERROR('Error: Email cannot be empty'))
                sys.exit(1)

        # Check if email already exists
        if User.objects.filter(email__iexact=email).exists():
            self.stdout.write(
                self.style.ERROR(f'Error: Email "{email}" is already registered.')
            )
            sys.exit(1)

        # Collect password
        if not password:
            # Try to get from environment variable first
            import os
            password = os.environ.get('SUPERUSER_PASSWORD')
            
            if not password:
                if noinput:
                    self.stdout.write(
                        self.style.ERROR(
                            'Error: Password must be provided via --password or SUPERUSER_PASSWORD environment variable when using --noinput'
                        )
                    )
                    sys.exit(1)
                password = getpass.getpass('Password: ')
                password_confirm = getpass.getpass('Password (again): ')
                if password != password_confirm:
                    self.stdout.write(
                        self.style.ERROR('Error: Passwords do not match.')
                    )
                    sys.exit(1)
                if len(password) < 8:
                    self.stdout.write(
                        self.style.ERROR('Error: Password must be at least 8 characters long.')
                    )
                    sys.exit(1)

        # Create the superuser
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    is_staff=True,
                    is_superuser=True,
                    user_type='admin',  # Set user type to admin
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Superuser "{username}" created successfully!\n'
                        f'  Username: {username}\n'
                        f'  Email: {email}\n'
                        f'  User Type: admin\n'
                        f'  Is Staff: True\n'
                        f'  Is Superuser: True'
                    )
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating superuser: {str(e)}')
            )
            sys.exit(1)

