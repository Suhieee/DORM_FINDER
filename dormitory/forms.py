from django import forms
from .models import Dorm, DormImage ,  Amenity ,  RoommatePost, RoommateAmenity , Review

class DormForm(forms.ModelForm):
    amenities = forms.ModelMultipleChoiceField(
        queryset=Amenity.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Amenities"
    )
    latitude = forms.DecimalField(
        required=True,
        widget=forms.HiddenInput(),
        max_digits=9,
        decimal_places=6,
        initial=14.5995  # Default Manila coordinates
    )
    longitude = forms.DecimalField(
        required=True,
        widget=forms.HiddenInput(),
        max_digits=9,
        decimal_places=6,
        initial=120.9842  # Default Manila coordinates
    )

    class Meta:
        model = Dorm
        fields = ['name', 'address', 'latitude', 'longitude', 'price', 'description', 'permit', 'available', 'amenities']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'permit': forms.FileInput(attrs={'accept': 'image/*'})
        }
        labels = {
            'permit': 'Business Permit (Image only)'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['latitude'].initial = self.instance.latitude
            self.fields['longitude'].initial = self.instance.longitude

class DormImageForm(forms.ModelForm):
    class Meta:
        model = DormImage
        fields = ['image']

class RoommatePostForm(forms.ModelForm):
    amenities = forms.ModelMultipleChoiceField(
        queryset=RoommateAmenity.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = RoommatePost
        fields = [
            "name", "age","profile_image", "contact_number", "hobbies", "mood",
            "preferred_budget", "preferred_location", "amenities", "description"
        ]

class ReviewForm(forms.ModelForm):
    rating = forms.IntegerField(
        required=False,
        widget=forms.Select(choices=Review.RATING_CHOICES)
    )
    
    comment = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"rows": 3}),
        max_length=500
    )

    class Meta:
        model = Review
        fields = ["rating", "comment"]

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if rating is not None and (rating < 1 or rating > 5):
            raise forms.ValidationError("Rating must be between 1 and 5")
        return rating

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("rating") and not cleaned_data.get("comment"):
            raise forms.ValidationError(
                "Please provide either a rating or a comment (or both)"
            )
        return cleaned_data