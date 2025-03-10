from django import forms
from .models import UserProfile
from accounts.models import CustomUser  # Import your custom user model

class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=50, required=True, label="First Name")
    last_name = forms.CharField(max_length=50, required=True, label="Last Name")
    username = forms.CharField(max_length=50, required=True, label="Username")
    email = forms.EmailField(required=True, label="Email Address")
    contact_number = forms.CharField(max_length=15, required=False, label="Contact Number")

    class Meta:
        model = UserProfile
        fields = ['profile_picture', 'first_name', 'last_name', 'username', 'email', 'contact_number']

    def __init__(self, *args, **kwargs):
        """Populate the fields with existing user data"""
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['username'].initial = self.instance.user.username
            self.fields['email'].initial = self.instance.user.email
            self.fields['contact_number'].initial = self.instance.user.contact_number

    def save(self, commit=True):
        """Save profile and update user fields"""
        user_profile = super().save(commit=False)
        user = user_profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.username = self.cleaned_data['username']
        user.email = self.cleaned_data['email']
        user.contact_number = self.cleaned_data['contact_number']
        if commit:
            user.save()
            user_profile.save()
        return user_profile

