# dormitory/management/commands/associate_dorms.py
from django.core.management.base import BaseCommand
from dormitory.models import Dorm, School
from math import radians, sin, cos, sqrt, atan2

class Command(BaseCommand):
    help = 'Associate dorms with nearby schools'

    def add_arguments(self, parser):
        parser.add_argument(
            '--radius',
            type=float,
            default=2.0,
            help='Maximum association radius in kilometers (default: 2km)'
        )

    def handle(self, *args, **options):
        radius_km = options['radius']
        updated = 0
        
        for dorm in Dorm.objects.filter(latitude__isnull=False, longitude__isnull=False):
            # Clear existing associations
            dorm.nearby_schools.clear()
            
            # Find nearby schools
            for school in School.objects.all():
                # Distance calculation
                lat1 = radians(float(dorm.latitude))
                lon1 = radians(float(dorm.longitude))
                lat2 = radians(float(school.latitude))
                lon2 = radians(float(school.longitude))
                
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                distance = 6371 * 2 * atan2(sqrt(a), sqrt(1-a))
                
                if distance <= radius_km:
                    dorm.nearby_schools.add(school)
                    updated += 1
        
        self.stdout.write(f'Created {updated} dorm-school associations within {radius_km}km radius')