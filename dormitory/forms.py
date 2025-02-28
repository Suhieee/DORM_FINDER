from django import forms
from .models import Dorm

class DormForm(forms.ModelForm):
    class Meta:
        model = Dorm
        fields = ['name', 'address', 'price', 'description', 'image', 'available']
