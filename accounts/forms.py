from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True, label="First Name")
    last_name = forms.CharField(max_length=30, required=True, label="Last Name")
    contact_number = forms.CharField(max_length=15, required=True, label="Contact Number")

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'username', 'email', 'contact_number', 'password1', 'password2', 'user_type']

