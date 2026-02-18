from django import forms
from .models import UserProfile, TenantPreferences
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


class TenantPreferencesForm(forms.ModelForm):
    """Form for tenant preferences - smart matching system"""
    
    class Meta:
        model = TenantPreferences
        fields = [
            'preferred_location', 'max_distance_km', 'min_budget', 'max_budget',
            'preferred_gender', 'preferred_room_type', 'wifi_required', 'parking_required',
            'laundry_required', 'kitchen_required', 'aircon_required', 'security_required',
            'pet_friendly_required', 'study_area_required', 'near_public_transport'
        ]
        widgets = {
            'preferred_location': forms.TextInput(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'e.g., Quezon City, Manila'
            }),
            'max_distance_km': forms.NumberInput(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'min': '0.5',
                'max': '50',
                'step': '0.5'
            }),
            'min_budget': forms.NumberInput(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'min': '0',
                'step': '100'
            }),
            'max_budget': forms.NumberInput(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'min': '0',
                'step': '100'
            }),
            'preferred_gender': forms.Select(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),
            'preferred_room_type': forms.Select(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),
        }
        
        labels = {
            'preferred_location': 'Preferred Location',
            'max_distance_km': 'Maximum Distance (km)',
            'min_budget': 'Minimum Budget (₱/month)',
            'max_budget': 'Maximum Budget (₱/month)',
            'preferred_gender': 'Gender Preference',
            'preferred_room_type': 'Room Type Preference',
            'wifi_required': 'WiFi',
            'parking_required': 'Parking',
            'laundry_required': 'Laundry',
            'kitchen_required': 'Kitchen',
            'aircon_required': 'Air Conditioning',
            'security_required': 'Security',
            'pet_friendly_required': 'Pet Friendly',
            'study_area_required': 'Study Area',
            'near_public_transport': 'Near Public Transport',
        }
        
        help_texts = {
            'max_distance_km': 'How far are you willing to travel from your preferred location?',
            'min_budget': 'Your minimum monthly budget',
            'max_budget': 'Your maximum monthly budget',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add custom styling for checkboxes
        checkbox_fields = [
            'wifi_required', 'parking_required', 'laundry_required', 'kitchen_required',
            'aircon_required', 'security_required', 'pet_friendly_required',
            'study_area_required', 'near_public_transport'
        ]
        for field in checkbox_fields:
            self.fields[field].widget.attrs.update({
                'class': 'w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500'
            })


class RoommatePreferencesForm(forms.ModelForm):
    """Form for roommate preferences - second step of smart matching"""
    
    class Meta:
        model = TenantPreferences
        fields = [
            'preferred_roommate_mood', 'preferred_roommate_age_range', 'preferred_roommate_gender',
            'roommate_budget_min', 'roommate_budget_max', 'roommate_preferred_location',
            'roommate_cleanliness_important', 'roommate_quiet_environment',
            'roommate_social_activities', 'roommate_shared_expenses'
        ]
        widgets = {
            'preferred_roommate_mood': forms.Select(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500'
            }),
            'preferred_roommate_age_range': forms.Select(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500'
            }),
            'preferred_roommate_gender': forms.Select(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500'
            }),
            'roommate_budget_min': forms.NumberInput(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500',
                'min': '0',
                'step': '100'
            }),
            'roommate_budget_max': forms.NumberInput(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500',
                'min': '0',
                'step': '100'
            }),
            'roommate_preferred_location': forms.TextInput(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500',
                'placeholder': 'e.g., España, Manila'
            }),
        }
        
        labels = {
            'preferred_roommate_mood': 'Preferred Personality Type',
            'preferred_roommate_age_range': 'Preferred Age Range',
            'preferred_roommate_gender': 'Preferred Gender',
            'roommate_budget_min': 'Minimum Budget (₱/month)',
            'roommate_budget_max': 'Maximum Budget (₱/month)',
            'roommate_preferred_location': 'Preferred Location',
            'roommate_cleanliness_important': 'Cleanliness is Important',
            'roommate_quiet_environment': 'Prefer Quiet Environment',
            'roommate_social_activities': 'Enjoy Social Activities',
            'roommate_shared_expenses': 'Open to Sharing Expenses',
        }
        
        help_texts = {
            'preferred_roommate_mood': 'What personality type would you prefer in a roommate?',
            'preferred_roommate_age_range': 'What age range do you prefer?',
            'roommate_budget_min': 'Minimum budget you expect roommate to have',
            'roommate_budget_max': 'Maximum budget you expect roommate to have',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add custom styling for checkboxes
        checkbox_fields = [
            'roommate_cleanliness_important', 'roommate_quiet_environment',
            'roommate_social_activities', 'roommate_shared_expenses'
        ]
        for field in checkbox_fields:
            self.fields[field].widget.attrs.update({
                'class': 'w-4 h-4 text-purple-600 bg-gray-100 border-gray-300 rounded focus:ring-purple-500'
            })

