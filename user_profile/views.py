from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, UpdateView, View
from django.urls import reverse_lazy
from accounts.models import CustomUser  
from .models import UserProfile, FavoriteDorm
from .forms import UserProfileForm
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
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
        context['favorite_dorms'] = FavoriteDorm.objects.filter(
            user_profile=self.request.user.userprofile
        ).select_related('dorm')
        return context
    
class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = UserProfile
    form_class = UserProfileForm
    template_name = "user_profile/edit_profile.html"
    success_url = reverse_lazy("user_profile:profile")

    def get_object(self, queryset=None):
        return self.request.user.userprofile

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