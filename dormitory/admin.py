from django.contrib import admin
from .models import Dorm,Amenity,RoommatePost, RoommateAmenity , School , Review, Room, RoomImage

admin.site.register(Dorm)
admin.site.register(Amenity)
admin.site.register(RoommatePost)
admin.site.register(RoommateAmenity)
admin.site.register(School)
admin.site.register(Review)

class RoomImageInline(admin.TabularInline):
    model = RoomImage
    extra = 1

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "dorm", "price", "is_available")
    list_filter = ("dorm", "is_available")
    search_fields = ("name", "dorm__name")
    inlines = [RoomImageInline]

@admin.register(RoomImage)
class RoomImageAdmin(admin.ModelAdmin):
    list_display = ("room", "image")

