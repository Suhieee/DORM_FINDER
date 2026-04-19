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


class PWDVerificationForm(forms.Form):
    pwd_document = forms.ImageField(
        required=True,
        help_text='Upload a clear image of your PWD ID, birth certificate, valid government ID, disability certificate, or equivalent proof.',
        widget=forms.FileInput(attrs={
            'accept': 'image/*',
            'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-slate-700'
        })
    )
    pwd_id_photo = forms.ImageField(
        required=True,
        help_text='Upload a clear photo of you holding your valid ID or PWD ID for identity matching.',
        widget=forms.FileInput(attrs={
            'accept': 'image/*',
            'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-slate-700'
        })
    )
    pwd_reference_number = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-200',
            'placeholder': 'PWD ID / reference number (optional)'
        })
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-200',
            'placeholder': 'Anything an admin should know about your PWD discount request (optional)'
        })
    )


class TenantPreferencesForm(forms.ModelForm):
    """Form for tenant preferences - smart matching system"""
    
    class Meta:
        model = TenantPreferences
        fields = [
            'preferred_location', 'max_distance_km', 'min_budget', 'max_budget',
            'preferred_gender', 'preferred_room_type', 'wifi_required', 'parking_required',
            'laundry_required', 'kitchen_required', 'aircon_required', 'security_required',
            'pet_friendly_required', 'study_area_required', 'near_public_transport',
            'other_amenity_required', 'other_amenity_text'
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
            'other_amenity_text': forms.TextInput(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Type other amenity (e.g., Elevator, Generator)'
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
            'other_amenity_required': 'Others',
            'other_amenity_text': 'Other Amenity',
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
            'study_area_required', 'near_public_transport', 'other_amenity_required'
        ]
        for field in checkbox_fields:
            self.fields[field].widget.attrs.update({
                'class': 'w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500'
            })

    def clean(self):
        cleaned_data = super().clean()
        other_enabled = cleaned_data.get('other_amenity_required')
        other_text = (cleaned_data.get('other_amenity_text') or '').strip()
        cleaned_data['other_amenity_text'] = other_text

        if other_enabled and not other_text:
            self.add_error('other_amenity_text', 'Please specify the other amenity.')

        if not other_enabled:
            cleaned_data['other_amenity_text'] = ''

        return cleaned_data


class RoommatePreferencesForm(forms.ModelForm):
    """Form for roommate preferences - second step of smart matching"""
    preferred_roommate_personalities = forms.MultipleChoiceField(
        choices=[
            ('quiet', 'Quiet and Reserved'),
            ('friendly', 'Friendly and Social'),
            ('adventurous', 'Adventurous and Outgoing'),
            ('studious', 'Studious and Focused'),
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Preferred Personality Types',
        help_text='Select one or more personality types. Leave empty if no preference.'
    )
    
    class Meta:
        model = TenantPreferences
        fields = [
            'preferred_roommate_personalities', 'preferred_roommate_age_range', 'preferred_roommate_gender',
            'roommate_budget_min', 'roommate_budget_max', 'roommate_preferred_location',
            'roommate_cleanliness_important', 'roommate_quiet_environment',
            'roommate_social_activities', 'roommate_shared_expenses',
            'preferred_roommate_other_enabled', 'preferred_roommate_other_text'
        ]
        widgets = {
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
            'preferred_roommate_other_text': forms.TextInput(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500',
                'placeholder': 'Type other roommate preference'
            }),
        }
        
        labels = {
            'preferred_roommate_age_range': 'Preferred Age Range',
            'preferred_roommate_gender': 'Preferred Gender',
            'roommate_budget_min': 'Minimum Budget (₱/month)',
            'roommate_budget_max': 'Maximum Budget (₱/month)',
            'roommate_preferred_location': 'Preferred Location',
            'roommate_cleanliness_important': 'Cleanliness is Important',
            'roommate_quiet_environment': 'Prefer Quiet Environment',
            'roommate_social_activities': 'Enjoy Social Activities',
            'roommate_shared_expenses': 'Open to Sharing Expenses',
            'preferred_roommate_other_enabled': 'Others',
            'preferred_roommate_other_text': 'Other Roommate Preference',
        }
        
        help_texts = {
            'preferred_roommate_age_range': 'What age range do you prefer?',
            'roommate_budget_min': 'Minimum budget you expect roommate to have',
            'roommate_budget_max': 'Maximum budget you expect roommate to have',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.preferred_roommate_personalities:
            self.initial['preferred_roommate_personalities'] = self.instance.preferred_roommate_personalities

        self.fields['preferred_roommate_personalities'].widget.attrs.update({
            'class': 'space-y-2'
        })

        # Add custom styling for checkboxes
        checkbox_fields = [
            'roommate_cleanliness_important', 'roommate_quiet_environment',
            'roommate_social_activities', 'roommate_shared_expenses', 'preferred_roommate_other_enabled'
        ]
        for field in checkbox_fields:
            self.fields[field].widget.attrs.update({
                'class': 'w-4 h-4 text-purple-600 bg-gray-100 border-gray-300 rounded focus:ring-purple-500'
            })

    def clean(self):
        cleaned_data = super().clean()
        selected = cleaned_data.get('preferred_roommate_personalities') or []
        other_enabled = cleaned_data.get('preferred_roommate_other_enabled')
        other_text = (cleaned_data.get('preferred_roommate_other_text') or '').strip()

        if selected:
            cleaned_data['preferred_roommate_mood'] = selected[0]
        else:
            cleaned_data['preferred_roommate_mood'] = 'any'

        cleaned_data['preferred_roommate_other_text'] = other_text
        if other_enabled and not other_text:
            self.add_error('preferred_roommate_other_text', 'Please specify your other roommate preference.')

        if not other_enabled:
            cleaned_data['preferred_roommate_other_text'] = ''

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        selected = self.cleaned_data.get('preferred_roommate_personalities') or []
        instance.preferred_roommate_mood = selected[0] if selected else 'any'
        if commit:
            instance.save()
        return instance

