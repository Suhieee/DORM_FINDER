from django.core.management.base import BaseCommand
from dormitory.models import School

SCHOOLS_DATA = [
    {
        'name': 'University of Santo Tomas',
        'address': 'España Blvd, Sampaloc, Manila',
        'latitude': 14.6096,
        'longitude': 120.9899
    },
    {
        'name': 'De La Salle University',
        'address': '2401 Taft Ave, Malate, Manila',
        'latitude': 14.5646, 
        'longitude': 120.9932
    }
]

class Command(BaseCommand):
    help = 'Adds Manila schools to database'

    def handle(self, *args, **options):
        for school in SCHOOLS_DATA:
            School.objects.get_or_create(
                name=school['name'],
                defaults=school
            )
        self.stdout.write(self.style.SUCCESS(f'Added {len(SCHOOLS_DATA)} schools'))