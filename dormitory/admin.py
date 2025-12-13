from django.contrib import admin
from .models import Dorm,Amenity,RoommatePost, RoommateAmenity , School , Review, Room, RoomImage, DormVisit, Reservation, TransactionLog

admin.site.register(Dorm)
admin.site.register(Amenity)
admin.site.register(RoommatePost)
admin.site.register(RoommateAmenity)
admin.site.register(School)
admin.site.register(Review)

@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    list_display = ('landlord', 'transaction_type', 'dorm', 'tenant', 'amount', 'status', 'created_at')
    list_filter = ('transaction_type', 'status', 'created_at')
    search_fields = ('landlord__email', 'dorm__name', 'tenant__email', 'description')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

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


@admin.register(DormVisit)
class DormVisitAdmin(admin.ModelAdmin):
    list_display = ('student', 'dorm', 'visit_date', 'time_slot', 'status', 'created_at')
    list_filter = ('status', 'visit_date', 'created_at')
    search_fields = ('student__username', 'student__first_name', 'student__last_name', 'dorm__name')
    readonly_fields = ('created_at', 'confirmed_at', 'completed_at')
    list_per_page = 50
    
    fieldsets = (
        ('Visit Information', {
            'fields': ('dorm', 'student', 'visit_date', 'time_slot', 'status')
        }),
        ('Messages & Notes', {
            'fields': ('student_message', 'landlord_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'confirmed_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'dorm', 'status', 'payment_deadline', 'is_payment_overdue', 'created_at')
    list_filter = ('status', 'is_payment_overdue', 'has_paid_reservation', 'created_at')
    search_fields = ('tenant__username', 'dorm__name')
    readonly_fields = ('created_at', 'completed_at', 'payment_submitted_at')
    list_per_page = 50
    
    fieldsets = (
        ('Reservation Details', {
            'fields': ('dorm', 'tenant', 'room', 'visit', 'status')
        }),
        ('Payment Information', {
            'fields': ('payment_proof', 'payment_deadline', 'is_payment_overdue', 
                      'has_paid_reservation', 'payment_amount', 'payment_submitted_at')
        }),
        ('Additional Info', {
            'fields': ('notes', 'cancellation_reason', 'reservation_date', 'created_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )

