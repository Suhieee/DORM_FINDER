from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, UserReport
from django.utils import timezone
from datetime import timedelta


class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True, label="First Name")
    last_name = forms.CharField(max_length=30, required=True, label="Last Name")
    contact_number = forms.CharField(max_length=15, required=True, label="Contact Number")
    profile_picture = forms.ImageField(required=False, label="Profile Picture")  # New Field

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'username', 'email', 'contact_number', 'password1', 'password2', 'user_type']

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            return email
        # Enforce case-insensitive uniqueness
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class AdminCreationForm(UserCreationForm):
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput)

    class Meta:
        model = CustomUser
        fields = UserCreationForm.Meta.fields + ('email', 'contact_number')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            return email
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserReportForm(forms.ModelForm):
    class Meta:
        model = UserReport
        fields = ['reason', 'description', 'evidence']
        widgets = {
            'reason': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-blue-500 focus:border-blue-500'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-3 py-2 min-h-[100px] focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Type here the details of your report'
            }),
            'evidence': forms.Textarea(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Any additional evidence or context (optional)',
                'rows': 3
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reason'].widget.attrs['class'] = 'w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-blue-500 focus:border-blue-500'
        self.fields['description'].widget.attrs['class'] = 'w-full border border-gray-300 rounded-lg px-3 py-2 min-h-[100px] focus:ring-blue-500 focus:border-blue-500'
        self.fields['evidence'].widget.attrs['class'] = 'w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-blue-500 focus:border-blue-500'


class BanUserForm(forms.Form):
    BAN_CHOICES = [
        ('minor', 'Minor (1 day)'),
        ('moderate', 'Moderate (7 days)'),
        ('major', 'Major (30 days)'),
        ('permanent', 'Permanent'),
    ]
    
    ban_severity = forms.ChoiceField(
        choices=BAN_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='Select the severity of the ban'
    )
    ban_reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Reason for banning this user...'}),
        help_text='Provide a detailed reason for the ban'
    )
    
    def get_ban_duration(self):
        """Get ban duration based on severity"""
        severity = self.cleaned_data.get('ban_severity')
        if severity == 'minor':
            return timedelta(days=1)
        elif severity == 'moderate':
            return timedelta(days=7)
        elif severity == 'major':
            return timedelta(days=30)
        elif severity == 'permanent':
            return None
        return timedelta(days=1)  # Default to 1 day


class ResolveReportForm(forms.Form):
    ACTION_CHOICES = [
        ('warn', 'Warn User'),
        ('ban_minor', 'Ban User (1 day)'),
        ('ban_moderate', 'Ban User (7 days)'),
        ('ban_major', 'Ban User (30 days)'),
        ('ban_permanent', 'Ban User (Permanent)'),
        ('dismiss', 'Dismiss Report'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='Select the action to take'
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Admin notes...'}),
        required=False,
        help_text='Additional notes about the resolution'
    )


