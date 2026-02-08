from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import DetailView, UpdateView, View
from django.urls import reverse_lazy
from accounts.models import CustomUser  
from .models import UserProfile, FavoriteDorm, TenantPreferences
from .forms import UserProfileForm, TenantPreferencesForm
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from dormitory.models import Dorm
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
import logging

logger = logging.getLogger(__name__)

class ProfileDetailView(LoginRequiredMixin, DetailView):
    model = CustomUser
    template_name = "user_profile/profile.html" 
    context_object_name = "profile_user"

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Ensure a profile exists; avoid RelatedObjectDoesNotExist
        user_profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        context['favorite_dorms'] = FavoriteDorm.objects.filter(
            user_profile=user_profile
        ).select_related('dorm')
        
        # Add listed dorms for landlords
        if self.request.user.user_type == 'landlord':
            context['listed_dorms'] = Dorm.objects.filter(landlord=self.request.user)
        
        # Add tenant preferences if user is a tenant
        if self.request.user.user_type == 'tenant':
            try:
                context['tenant_preferences'] = TenantPreferences.objects.get(user=self.request.user)
            except TenantPreferences.DoesNotExist:
                context['tenant_preferences'] = None
                
        return context
    
class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = UserProfile
    form_class = UserProfileForm
    template_name = "user_profile/edit_profile.html"
    success_url = reverse_lazy("user_profile:profile")

    def get_object(self, queryset=None):
        # Ensure profile exists when accessing edit
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    def form_valid(self, form):
        messages.success(self.request, 'Your profile has been updated successfully!')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'There was an error updating your profile. Please try again.')
        return super().form_invalid(form)

@method_decorator(ensure_csrf_cookie, name='dispatch')
class ToggleFavoriteDormView(LoginRequiredMixin, View):
    def post(self, request, dorm_id):
        try:
            dorm = Dorm.objects.get(id=dorm_id)
            profile = UserProfile.objects.get(user=request.user)
            
            if dorm in profile.favorite_dorms.all():
                profile.favorite_dorms.remove(dorm)
                messages.success(request, f'Removed {dorm.name} from favorites')
                is_favorite = False
            else:
                profile.favorite_dorms.add(dorm)
                messages.success(request, f'Added {dorm.name} to favorites')
                is_favorite = True
                
            return JsonResponse({
                'status': 'success',
                'is_favorite': is_favorite
            })
            
        except (Dorm.DoesNotExist, UserProfile.DoesNotExist) as e:
            messages.error(request, 'Failed to update favorites. Please try again.')
            return JsonResponse({
                'status': 'error'
            }, status=400)


class PublicLandlordProfileView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for admins to see landlord profiles with verification documents"""
    model = CustomUser
    template_name = "user_profile/landlord_profile.html"
    context_object_name = "landlord"
    pk_url_kwarg = "user_id"
    
    def test_func(self):
        # Only admins can view this
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        landlord = self.get_object()
        
        # Get user profile and dorms
        user_profile, _ = UserProfile.objects.get_or_create(user=landlord)
        context['user_profile'] = user_profile
        context['dorms'] = landlord.dorm_set.all()
        
        # Show verification documents
        context['show_documents'] = True
        
        return context


class SetupPreferencesView(LoginRequiredMixin, UpdateView):
    """View for tenants to set up their preferences after registration"""
    model = TenantPreferences
    form_class = TenantPreferencesForm
    template_name = "user_profile/setup_preferences.html"
    success_url = reverse_lazy("accounts:dashboard")

    def dispatch(self, request, *args, **kwargs):
        # Only tenants can access this
        if request.user.user_type != 'tenant':
            messages.warning(request, 'Preferences are only for tenants.')
            return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        # Get or create preferences for the logged-in tenant
        preferences, created = TenantPreferences.objects.get_or_create(user=self.request.user)
        return preferences

    def form_valid(self, form):
        messages.success(self.request, 'Your preferences have been saved! We will use these to find the best dorms for you.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'There was an error saving your preferences. Please try again.')
        return super().form_invalid(form)


class EditPreferencesView(LoginRequiredMixin, UpdateView):
    """View for tenants to edit their preferences anytime"""
    model = TenantPreferences
    form_class = TenantPreferencesForm
    template_name = "user_profile/edit_preferences.html"
    success_url = reverse_lazy("user_profile:profile")

    def dispatch(self, request, *args, **kwargs):
        # Only tenants can access this
        if request.user.user_type != 'tenant':
            messages.warning(request, 'Preferences are only for tenants.')
            return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        # Get or create preferences for the logged-in tenant
        preferences, created = TenantPreferences.objects.get_or_create(user=self.request.user)
        return preferences

    def form_valid(self, form):
        messages.success(self.request, 'Your preferences have been updated successfully!')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'There was an error updating your preferences. Please try again.')
        return super().form_invalid(form)