from django.contrib import admin
from .models import Dorm,Amenity,RoommatePost, RoommateAmenity

admin.site.register(Dorm)
admin.site.register(Amenity)
admin.site.register(RoommatePost)
admin.site.register(RoommateAmenity)
