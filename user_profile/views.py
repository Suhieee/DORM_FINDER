from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import DetailView, UpdateView, View
from django.urls import reverse_lazy, reverse
from accounts.models import CustomUser  
from .models import UserProfile, FavoriteDorm, TenantPreferences
from .forms import UserProfileForm, TenantPreferencesForm, RoommatePreferencesForm
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
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


class SetupPreferencesView(LoginRequiredMixin, View):
    """Two-step wizard for setting up dorm and roommate preferences"""
    template_name = "user_profile/setup_preferences.html"

    def dispatch(self, request, *args, **kwargs):
        # Only tenants can access this
        if request.user.user_type != 'tenant':
            messages.warning(request, 'Preferences are only for tenants.')
            return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        # Get or create preferences
        preferences, created = TenantPreferences.objects.get_or_create(user=request.user)
        
        # Determine current step (default to step 1)
        step = request.GET.get('step', '1')
        
        # Check if we should show the choice modal
        show_choice_modal = not preferences.preference_choice or preferences.preference_choice == 'dorm_only' and step == '1' and created
        
        if step == '2' and preferences.preference_choice == 'dorm_and_roommate':
            # Show Step 2 only if user chose dorm_and_roommate
            form = RoommatePreferencesForm(instance=preferences)
            context = {
                'form': form,
                'step': 2,
                'preferences': preferences,
                'preference_choice': preferences.preference_choice,
                'show_choice_modal': False,
            }
        else:
            # Step 1: Dorm preferences
            form = TenantPreferencesForm(instance=preferences)
            context = {
                'form': form,
                'step': 1,
                'preferences': preferences,
                'preference_choice': preferences.preference_choice,
                'show_choice_modal': show_choice_modal,
            }
        
        return render(request, self.template_name, context)

    def post(self, request):
        # Get or create preferences
        preferences, created = TenantPreferences.objects.get_or_create(user=request.user)
        
        # Check if this is the choice step (from modal)
        if request.POST.get('choice_step') == '1':
            choice = request.POST.get('preference_choice')
            if choice in ['dorm_only', 'dorm_and_roommate']:
                preferences.preference_choice = choice
                preferences.save()
                messages.success(request, f'Great! Let\'s set up your preferences.')
                return redirect('user_profile:setup_preferences')
        
        # Determine current step
        step = request.POST.get('step', '1')
        
        if step == '1':
            # Process dorm preferences (step 1)
            form = TenantPreferencesForm(request.POST, instance=preferences)
            if form.is_valid():
                form.save()
                
                # If user chose dorm_only, finish here
                if preferences.preference_choice == 'dorm_only':
                    messages.success(request, 'Dorm preferences saved! You\'re all set to find your perfect dorm!')
                    return redirect('accounts:dashboard')
                else:
                    # If user chose dorm_and_roommate, go to step 2
                    messages.success(request, 'Dorm preferences saved! Now set your roommate preferences.')
                    return redirect(reverse('user_profile:setup_preferences') + '?step=2')
            else:
                messages.error(request, 'There was an error saving your preferences. Please try again.')
                context = {
                    'form': form,
                    'step': 1,
                    'preferences': preferences,
                    'preference_choice': preferences.preference_choice,
                    'show_choice_modal': False,
                }
                return render(request, self.template_name, context)
        
        elif step == '2':
            # Process roommate preferences (step 2)
            form = RoommatePreferencesForm(request.POST, instance=preferences)
            if form.is_valid():
                form.save()
                
                # Auto-create RoommatePost from preferences
                try:
                    roommate_post = preferences.sync_to_roommate_post()
                    messages.success(request, 'All preferences saved! Your roommate profile has been created. You\'re all set!')
                except Exception as e:
                    messages.warning(request, f'Preferences saved, but there was an issue creating your roommate profile: {str(e)}')
                
                return redirect('accounts:dashboard')
            else:
                messages.error(request, 'There was an error saving your roommate preferences. Please try again.')
                context = {
                    'form': form,
                    'step': 2,
                    'preferences': preferences,
                    'preference_choice': preferences.preference_choice,
                    'show_choice_modal': False,
                }
                return render(request, self.template_name, context)
        
        # Default fallback
        return redirect('user_profile:setup_preferences')



class EditPreferencesView(LoginRequiredMixin, View):
    """View for tenants to edit their preferences anytime (two-step)"""
    template_name = "user_profile/edit_preferences.html"

    def dispatch(self, request, *args, **kwargs):
        # Only tenants can access this
        if request.user.user_type != 'tenant':
            messages.warning(request, 'Preferences are only for tenants.')
            return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        # Get or create preferences
        preferences, created = TenantPreferences.objects.get_or_create(user=request.user)
        
        # Determine which step to display
        step = request.GET.get('step', '1')
        
        if step == '2':
            # Step 2: Roommate preferences
            form = RoommatePreferencesForm(instance=preferences)
        else:
            # Step 1: Dorm preferences
            form = TenantPreferencesForm(instance=preferences)
        
        return render(request, self.template_name, {
            'form': form,
            'step': step,
            'preferences': preferences
        })

    def post(self, request):
        # Get or create preferences
        preferences, created = TenantPreferences.objects.get_or_create(user=request.user)
        
        step = request.GET.get('step', '1')
        
        if step == '2':
            # Step 2: Save roommate preferences
            form = RoommatePreferencesForm(request.POST, instance=preferences)
            if form.is_valid():
                form.save()
                
                # If user has roommate matching enabled, sync to RoommatePost
                if preferences.preference_choice == 'dorm_and_roommate':
                    try:
                        preferences.sync_to_roommate_post()
                        messages.success(request, 'Your preferences and roommate profile have been updated successfully!')
                    except Exception as e:
                        messages.warning(request, f'Preferences updated, but there was an issue updating your roommate profile: {str(e)}')
                else:
                    messages.success(request, 'Your preferences have been updated successfully!')
                
                return redirect('user_profile:profile')
            else:
                messages.error(request, 'Please correct the errors below.')
                return render(request, self.template_name, {
                    'form': form,
                    'step': step,
                    'preferences': preferences
                })
        else:
            # Step 1: Save dorm preferences and redirect to step 2
            form = TenantPreferencesForm(request.POST, instance=preferences)
            if form.is_valid():
                form.save()
                # Redirect to step 2
                return redirect(reverse('user_profile:edit_preferences') + '?step=2')
            else:
                messages.error(request, 'Please correct the errors below.')
                return render(request, self.template_name, {
                    'form': form,
                    'step': step,
                    'preferences': preferences
                })