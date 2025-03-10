from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView , UpdateView
from django.urls import reverse_lazy
from accounts.models import CustomUser  
from .models import UserProfile
from .forms import UserProfileForm
from django.contrib import messages

class ProfileDetailView(LoginRequiredMixin, DetailView):
    model = CustomUser
    template_name = "user_profile/profile.html" 
    context_object_name = "profile_user"  
    def get_object(self):
        return self.request.user  
    
class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = UserProfile
    form_class = UserProfileForm
    template_name = "user_profile/edit_profile.html"
    success_url = reverse_lazy("user_profile:profile")  # Redirect after update

    def get_object(self, queryset=None):
        return self.request.user.userprofile

    def form_valid(self, form):
        # Add a success message when the form is valid
        messages.success(self.request, 'Your profile has been updated successfully!')
        return super().form_valid(form)

    def form_invalid(self, form):
        # Add an error message when the form is invalid
        messages.error(self.request, 'There was an error updating your profile. Please try again.')
        return super().form_invalid(form)