from django.contrib import admin
from .models import Dorm,Amenity,RoommatePost, RoommateAmenity , School , Review

admin.site.register(Dorm)
admin.site.register(Amenity)
admin.site.register(RoommatePost)
admin.site.register(RoommateAmenity)
admin.site.register(School)
admin.site.register(Review)

