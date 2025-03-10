from django import forms
from .models import Dorm, DormImage ,  Amenity

class DormForm(forms.ModelForm):
    amenities = forms.ModelMultipleChoiceField(
        queryset=Amenity.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Amenities"
    )

    class Meta:
        model = Dorm
        fields = ['name', 'address', 'price', 'description', 'permit', 'available', 'amenities']

class DormImageForm(forms.ModelForm):
    class Meta:
        model = DormImage
        fields = ['image']
