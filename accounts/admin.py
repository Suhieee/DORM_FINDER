from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'first_name', 'last_name', 'last_name', 'user_type', 'is_staff']
    
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('user_type',)}),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('user_type',)}),
    )

    def save_model(self, request, obj, form, change):
        # If user is marked as admin by type, ensure proper flags
        if obj.user_type == 'admin':
            obj.is_staff = True
            obj.is_superuser = True
        super().save_model(request, obj, form, change)

admin.site.register(CustomUser, CustomUserAdmin)
