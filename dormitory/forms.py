from django import forms
from .models import Dorm, DormImage ,  Amenity ,  RoommatePost, RoommateAmenity , Review ,  Reservation, Room, RoomImage

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
        fields = [
            'name', 'address', 'latitude', 'longitude', 'price', 'description', 'payment_terms',
            'permit', 'payment_qr', 'available', 'amenities', 'accommodation_type',
            'total_beds', 'available_beds','max_occupants', 'key_features',

        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'payment_terms': forms.Textarea(attrs={'rows': 2, 'placeholder': 'e.g., 3 months deposit, 1 month advance'}),
            'key_features': forms.Textarea(attrs={'rows': 3, 'placeholder': 'One feature per line'}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'price': forms.NumberInput(attrs={'step': '0.01'}),
            'permit': forms.FileInput(attrs={'accept': 'image/*'}),
            'payment_qr': forms.FileInput(attrs={'accept': 'image/*'}),
            'accommodation_type': forms.Select(attrs={'class': 'form-control'}),
            'total_beds': forms.NumberInput(attrs={'min': '1', 'class': 'form-control'}),
            'available_beds': forms.NumberInput(attrs={'min': '0', 'class': 'form-control'}),
            'max_occupants': forms.NumberInput(attrs={'min': '1', 'class': 'form-control'}),
        }
        help_texts = {
            'payment_qr': 'Upload your GCash/Maya QR code for accepting payments',
            'permit': 'Upload your business permit or registration',
            'price': 'Enter the price per month in PHP',
            'payment_terms': 'Enter payment terms (e.g., "3 months deposit, 1 month advance")',
            'total_beds': 'Total number of beds in the unit',
            'available_beds': 'Number of beds currently available for rent',
            'max_occupants': 'Maximum number of people allowed in the unit',
        }
        labels = {
            'permit': 'Business Permit (Image only)',
            'payment_qr': 'Payment QR Code (GCash/Maya)',
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
    
    preferred_budget_min = forms.DecimalField(
        required=True,
        min_value=0,
        max_digits=8,
        decimal_places=2,
        help_text="Minimum monthly budget"
    )
    
    preferred_budget_max = forms.DecimalField(
        required=True,
        min_value=0,
        max_digits=8,
        decimal_places=2,
        help_text="Maximum monthly budget"
    )

    class Meta:
        model = RoommatePost
        fields = [
            "name", "age", "profile_image", "contact_number", "hobbies", "mood",
            "preferred_location", "amenities", "description",
            "preferred_budget_min", "preferred_budget_max"
        ]

    def clean(self):
        cleaned_data = super().clean()
        min_budget = cleaned_data.get('preferred_budget_min')
        max_budget = cleaned_data.get('preferred_budget_max')

        if min_budget and max_budget:
            if max_budget < min_budget:
                raise forms.ValidationError("Maximum budget cannot be less than minimum budget")
            # Calculate average budget for the model
            cleaned_data['preferred_budget'] = (min_budget + max_budget) / 2

        return cleaned_data

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
    

class ReservationForm(forms.ModelForm):
    room = forms.ModelChoiceField(queryset=Room.objects.none(), required=False, label="Select Room")

    class Meta:
        model = Reservation
        fields = ['room']

    def __init__(self, *args, **kwargs):
        dorm = kwargs.pop('dorm', None)
        super().__init__(*args, **kwargs)
        if dorm is not None:
            if dorm.accommodation_type == 'whole_unit':
                self.fields['room'].widget = forms.HiddenInput()
                self.fields['room'].required = False
            else:
                self.fields['room'].queryset = dorm.rooms.filter(is_available=True)
                self.fields['room'].required = True

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['name', 'price', 'is_available', 'description', 'room_type', 'capacity', 'size', 'floor_number']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter room name (e.g., Room 1, Bed A)',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'e.g. 4500',
            }),
            'is_available': forms.CheckboxInput(attrs={
                'class': 'rounded text-blue-600 focus:ring-blue-500',
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'rows': 3,
                'placeholder': 'Optional description...',
            }),
            'room_type': forms.Select(attrs={
                'class': 'w-full border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500',
            }),
            'capacity': forms.NumberInput(attrs={
                'class': 'w-full border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Number of people',
            }),
            'size': forms.NumberInput(attrs={
                'class': 'w-full border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Square meters',
            }),
            'floor_number': forms.NumberInput(attrs={
                'class': 'w-full border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Floor number',
            }),
        }

class RoomImageForm(forms.ModelForm):
    class Meta:
        model = RoomImage
        fields = ['image']