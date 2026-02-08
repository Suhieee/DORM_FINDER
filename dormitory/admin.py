from django.contrib import admin
from .models import (
    Dorm, Amenity, RoommatePost, RoommateAmenity, School, Review, 
    Room, RoomImage, Reservation, PaymentConfiguration,
    ChatbotConversation, ChatbotMessage, ChatbotFAQ
)
from .models_transaction import TransactionLog

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
                      'has_paid_reservation', 'payment_amount', 'payment_submitted_at',
                      'payment_intent_id', 'payment_method', 'payment_status', 'payment_verified_at',
                      'refund_amount', 'refund_reason', 'refund_processed_at')
        }),
        ('Additional Info', {
            'fields': ('notes', 'cancellation_reason', 'reservation_date', 'created_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PaymentConfiguration)
class PaymentConfigurationAdmin(admin.ModelAdmin):
    list_display = ['dorm', 'deposit_months', 'advance_months', 'processing_fee_percent', 'accepts_gateway']
    list_filter = ['accepts_gateway', 'accepts_manual', 'accepts_partial_payment', 'accepts_cash']
    search_fields = ['dorm__name', 'dorm__landlord__username']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Dorm', {
            'fields': ('dorm',)
        }),
        ('Payment Terms', {
            'fields': ('deposit_months', 'advance_months', 'processing_fee_percent')
        }),
        ('Payment Options', {
            'fields': ('accepts_partial_payment', 'partial_payment_percent')
        }),
        ('Accepted Payment Methods', {
            'fields': ('accepts_gateway', 'accepts_manual', 'accepts_cash')
        }),
        ('Cancellation & Refund Policy', {
            'fields': ('refund_before_days', 'partial_refund_percent')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ChatbotConversation)
class ChatbotConversationAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'user', 'created_at', 'updated_at', 'message_count')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('session_id', 'user__username', 'user__email')
    readonly_fields = ('session_id', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    ordering = ('-updated_at',)
    
    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Messages'


@admin.register(ChatbotMessage)
class ChatbotMessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'role', 'content_preview', 'is_from_cache', 'timestamp')
    list_filter = ('role', 'is_from_cache', 'timestamp')
    search_fields = ('content', 'conversation__session_id')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content'


@admin.register(ChatbotFAQ)
class ChatbotFAQAdmin(admin.ModelAdmin):
    list_display = ('question_preview', 'hit_count', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('question', 'answer', 'keywords')
    readonly_fields = ('hit_count', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    ordering = ('-hit_count', '-updated_at')
    
    fieldsets = (
        ('Question & Answer', {
            'fields': ('question', 'answer', 'is_active')
        }),
        ('Keywords & Matching', {
            'fields': ('keywords',),
            'description': 'Comma-separated keywords to help match similar questions'
        }),
        ('Statistics', {
            'fields': ('hit_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def question_preview(self, obj):
        return obj.question[:80] + '...' if len(obj.question) > 80 else obj.question
    question_preview.short_description = 'Question'

