from django.shortcuts import redirect, get_object_or_404 , render
from django.contrib.auth.mixins import LoginRequiredMixin , UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from .models import (
    Dorm, DormImage, Amenity, RoommatePost, Review, School,
    Reservation, Dorm, Message, ReservationMessage, RoommateMatch, RoommateChat, Room, RoomImage, RoommateChatReaction,
    RoommateAmenity
)
from .forms import DormForm ,  RoommatePostForm , ReviewForm , ReservationForm
from django.db.models import Avg , Q
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, ListView
from accounts.models import CustomUser, Notification

from io import BytesIO
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
import os
from django.views.generic import View
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import connection
from django.db.models import Count, Max
import time
from decimal import Decimal
from django.db import models
from .services import RoommateMatchingService
from django.views.decorators.csrf import csrf_exempt
from .forms import RoomForm, RoomImageForm
from django.forms import modelformset_factory
from django.views.generic import TemplateView
import json




def notify_user(user, message, related_object_id=None):
    """Create a notification for a user (fails silently if user missing)."""
    if not user:
        return
    Notification.objects.create(
        user=user,
        message=message,
        related_object_id=related_object_id
    )


class LoginRequiredActionMixin:
    """Mixin to handle login required actions with proper redirect"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Store the current URL to redirect back after login
            next_url = request.get_full_path()
            messages.info(request, "Please log in to access this feature.")
            return redirect(f"{reverse('accounts:login')}?next={next_url}")
        return super().dispatch(request, *args, **kwargs)



class PublicDormListView(ListView):
    """Public view for browsing dorms without login requirement"""
    model = Dorm
    template_name = "dormitory/public_dorm_list.html"
    context_object_name = "dorms"
    paginate_by = 12

    def get_queryset(self):
        queryset = Dorm.objects.select_related('landlord').prefetch_related(
            'images', 'amenities', 'reviews'
        ).filter(
            available=True, 
            approval_status="approved"
        ).annotate(
            avg_rating=models.Avg('reviews__rating'),
            review_count=models.Count('reviews')
        )

        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                models.Q(name__icontains=search_query) |
                models.Q(address__icontains=search_query) |
                models.Q(description__icontains=search_query)
            )

        # Price filtering
        min_price = self.request.GET.get('min_price')
        target_price = self.request.GET.get('target_price')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if target_price:
            queryset = queryset.filter(price__lte=target_price)

        # Amenities filtering
        amenities = self.request.GET.getlist('amenities')
        if amenities:
            queryset = queryset.filter(amenities__id__in=amenities).distinct()

        # Location-based filtering
        lat = self.request.GET.get('lat')
        lng = self.request.GET.get('lng')
        if lat and lng:
            try:
                lat = float(lat)
                lng = float(lng)
                # Filter dorms within 5km radius
                from math import radians, sin, cos, sqrt, atan2
                
                # Haversine formula for distance calculation
                def calculate_distance(lat1, lon1, lat2, lon2):
                    R = 6371  # Earth's radius in kilometers
                    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
                    dlat = lat2 - lat1
                    dlon = lon2 - lon1
                    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                    c = 2 * atan2(sqrt(a), sqrt(1-a))
                    distance = R * c
                    return distance
                
                # Filter dorms within 5km
                nearby_dorms = []
                for dorm in queryset:
                    if dorm.latitude and dorm.longitude:
                        distance = calculate_distance(lat, lng, float(dorm.latitude), float(dorm.longitude))
                        if distance <= 5.0:  # 5km radius
                            nearby_dorms.append(dorm.id)
                
                queryset = queryset.filter(id__in=nearby_dorms)
            except (ValueError, TypeError):
                pass  # Invalid coordinates, ignore location filter

        # Accommodation type filtering
        accommodation_type = self.request.GET.get('accommodation_type')
        if accommodation_type and accommodation_type != 'all':
            queryset = queryset.filter(accommodation_type=accommodation_type)

        # Sorting
        sort_by = self.request.GET.get('sort')
        if sort_by == 'price_asc':
            queryset = queryset.order_by('price')
        elif sort_by == 'price_desc':
            queryset = queryset.order_by('-price')
        elif sort_by == 'rating':
            queryset = queryset.order_by('-avg_rating')
        else:
            queryset = queryset.order_by('-created_at')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['amenities'] = Amenity.objects.all()
        context['selected_amenities'] = self.request.GET.getlist('amenities')
        
        # Add dorm data for map
        dorms_data = []
        for dorm in context['dorms']:
            dorms_data.append({
                'id': dorm.id,
                'name': dorm.name,
                'address': dorm.address,
                'price': float(dorm.price),  # Convert Decimal to float
                'latitude': float(dorm.latitude) if dorm.latitude else None,  # Convert Decimal to float
                'longitude': float(dorm.longitude) if dorm.longitude else None,  # Convert Decimal to float
            })
        context['dorms_json'] = json.dumps(dorms_data)
        
        # Add schools data for map
        from dormitory.models import School
        schools_data = []
        for school in School.objects.all():
            if school.latitude and school.longitude:
                schools_data.append({
                    'id': school.id,
                    'name': school.name,
                    'address': school.address,
                    'latitude': float(school.latitude),
                    'longitude': float(school.longitude),
                })
        context['schools_json'] = json.dumps(schools_data)
        
        return context


class PublicDormDetailView(DetailView):
    """Public view for viewing dorm details without login"""
    model = Dorm
    template_name = "dormitory/public_dorm_detail.html"
    context_object_name = "dorm"

    def get(self, request, *args, **kwargs):
        """Increment the view count when the dorm is viewed"""
        response = super().get(request, *args, **kwargs)
        dorm = self.object
        dorm.recent_views += 1
        dorm.save(update_fields=['recent_views'])
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['amenities'] = self.object.amenities.all()
        context['dorm_id'] = self.object.id
        context['latitude'] = self.object.latitude
        context['longitude'] = self.object.longitude
        
        # Add schools to the context
        context['schools'] = School.objects.all()
        
        # Add schools JSON for map functionality
        schools_data = []
        for school in School.objects.all():
            if school.latitude and school.longitude:
                schools_data.append({
                    'id': school.id,
                    'name': school.name,
                    'address': school.address,
                    'latitude': float(school.latitude),
                    'longitude': float(school.longitude),
                })
        context['schools_json'] = json.dumps(schools_data)
        
        # Get similar dorms based on price range, amenities, and location
        current_dorm = self.object
        price_range = (
            current_dorm.price * Decimal('0.7'), 
            current_dorm.price * Decimal('1.3')
        )
        
        similar_dorms = Dorm.objects.select_related('landlord').prefetch_related(
            'images', 'amenities', 'reviews'
        ).filter(
            available=True,
            approval_status="approved",
            price__range=price_range,
            accommodation_type=current_dorm.accommodation_type
        ).exclude(
            id=current_dorm.id
        ).annotate(
            avg_rating=models.Avg('reviews__rating'),
            review_count=models.Count('reviews'),
            amenity_match=models.Count(
                'amenities',
                filter=models.Q(amenities__in=current_dorm.amenities.all())
            )
        ).order_by('-amenity_match', '-avg_rating')[:4]

        context['similar_dorms'] = similar_dorms
        
        return context


class PublicRoommateListView(ListView):
    """Public view for browsing roommate listings without login"""
    model = RoommatePost
    template_name = "dormitory/public_roommate_list.html"
    context_object_name = "roommates"
    ordering = ["-date_posted"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add amenities for filtering
        context['amenities'] = RoommateAmenity.objects.all()
        return context


class PublicRoommateDetailView(DetailView):
    """Public view for viewing roommate details without login"""
    model = RoommatePost
    template_name = "dormitory/public_roommate_detail.html"
    context_object_name = "roommate"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


#  Add Dorm (For Landlords)
class AddDormView(LoginRequiredMixin, CreateView):
    model = Dorm
    form_class = DormForm
    template_name = "dormitory/add_dorm.html"
    success_url = reverse_lazy("accounts:dashboard")

    def form_valid(self, form):
        """Set the landlord before saving, handle multiple images, and save location data."""
        if self.request.user.user_type != "landlord":
            return redirect("accounts:dashboard")

        form.instance.landlord = self.request.user

        # The form validation will now handle the latitude/longitude requirement
        # No need for separate checks since we made the fields required

        # Save the dorm object
        response = super().form_valid(form)

        # Handle multiple images
        images = self.request.FILES.getlist('images')
        for image in images:
            DormImage.objects.create(dorm=self.object, image=image)

        # Notify all admins that a new dorm is awaiting review
        admins = CustomUser.objects.filter(user_type="admin")
        for admin in admins:
            Notification.objects.create(
                user=admin,
                message=f"New dorm '{self.object.name}' submitted by {self.request.user.username} is awaiting review.",
                related_object_id=self.object.id,
            )

        messages.success(self.request, "Dorm successfully created and sent for admin review!")
        return response

    def form_invalid(self, form):
        """Handle invalid form submission."""
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        """Pass amenities and map-related data to the template."""
        context = super().get_context_data(**kwargs)
        context["amenities"] = Amenity.objects.all()
        
        # Set default coordinates
        context["default_latitude"] = 14.5995  # Manila coordinates
        context["default_longitude"] = 120.9842
        
        return context


class DormListView(LoginRequiredMixin, ListView):
    model = Dorm
    template_name = "dormitory/dorm_list.html"
    context_object_name = "dorms"
    paginate_by = 12

    def get_queryset(self):
        """Filter dorms based on search parameters with optimized queries"""
        start_time = time.time()
        
        # Start with an optimized base queryset
        queryset = Dorm.objects.select_related('landlord').prefetch_related(
            'images',
            'amenities',
            'reviews',
            'nearby_schools'
        ).filter(
            available=True, 
            approval_status="approved"
        ).annotate(
            avg_rating=models.Avg('reviews__rating'),
            review_count=models.Count('reviews')
        ).annotate(
            avg_rating_rounded=models.Case(
                models.When(avg_rating__isnull=True, then=0),
                default=models.ExpressionWrapper(
                    models.functions.Round(models.F('avg_rating')), 
                    output_field=models.FloatField()
                ),
                output_field=models.FloatField()
            )
        )

        # Get filter parameters from request
        search_query = self.request.GET.get('search', '')
        target_price = self.request.GET.get('target_price')
        amenities = self.request.GET.getlist('amenities')
        school_id = self.request.GET.get('school')
        sort_by = self.request.GET.get('sort')
        accommodation_type = self.request.GET.get('accommodation_type')
        
        # Debug print statements
        print(f"Received filters - accommodation_type: {accommodation_type}, target_price: {target_price}")
        
        # Apply search filter if provided
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | 
                Q(address__icontains=search_query) |
                Q(description__icontains=search_query)
            )
            
        # Apply price filter if provided and not default max value
        if target_price and target_price != '50000':
            try:
                target_price = Decimal(target_price)
                queryset = queryset.filter(price__lte=target_price)
                print(f"Applying price filter: <= {target_price}")
                # Debug the filtered queryset
                print("Filtered dorms:")
                for dorm in queryset:
                    print(f"Dorm: {dorm.name}, Price: {dorm.price}")
            except (ValueError, TypeError) as e:
                print(f"Error converting price: {e}")
                pass

        # Apply accommodation type filter if provided and not 'all'
        if accommodation_type and accommodation_type != 'all':
            queryset = queryset.filter(accommodation_type=accommodation_type)
            print(f"Applying accommodation filter: {accommodation_type}")
            
        # Apply amenities filter if provided
        if amenities:
            queryset = queryset.filter(amenities__id__in=amenities).distinct()
            
        # Apply school filter if provided
        if school_id:
            queryset = queryset.filter(nearby_schools__id=school_id)

        # Apply sorting
        if sort_by == 'price_asc':
            queryset = queryset.order_by('price')
        elif sort_by == 'price_desc':
            queryset = queryset.order_by('-price')
        else:
            # Default sorting by newest
            queryset = queryset.order_by('-id')

        # Debug print final query
        print(f"Final query: {queryset.query}")
        print(f"Number of results: {queryset.count()}")
        
        end_time = time.time()
        print(f"Query execution time: {end_time - start_time:.2f} seconds")
        
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all amenities and schools
        context['amenities'] = Amenity.objects.all()
        context['schools'] = School.objects.all()
        
        # Pass current filter values back to template
        context['current_search'] = self.request.GET.get('search', '')
        context['current_target_price'] = self.request.GET.get('target_price', '50000')
        context['selected_amenities'] = [int(a) for a in self.request.GET.getlist('amenities')]
        context['selected_school'] = self.request.GET.get('school', '')
        context['selected_sort'] = self.request.GET.get('sort', '')
        
        # Add dorm data for map (same as public version)
        dorms_data = []
        for dorm in context['dorms']:
            dorms_data.append({
                'id': dorm.id,
                'name': dorm.name,
                'address': dorm.address,
                'price': float(dorm.price),  # Convert Decimal to float
                'latitude': float(dorm.latitude) if dorm.latitude else None,  # Convert Decimal to float
                'longitude': float(dorm.longitude) if dorm.longitude else None,  # Convert Decimal to float
                'thumbnail': (dorm.images.first().image.url if dorm.images.first() else ''),
            })
        context['dorms_json'] = json.dumps(dorms_data)
        
        # Add schools data for map
        schools_data = []
        for school in School.objects.all():
            if school.latitude and school.longitude:
                schools_data.append({
                    'id': school.id,
                    'name': school.name,
                    'address': school.address,
                    'latitude': float(school.latitude),
                    'longitude': float(school.longitude),
                })
        context['schools_json'] = json.dumps(schools_data)
        
        return context

# 🚀 Dorm Details

class DormDetailView(LoginRequiredMixin, DetailView):
    model = Dorm
    template_name = "dormitory/dorm_detail.html"
    context_object_name = "dorm"

    def get(self, request, *args, **kwargs):
        """Increment the view count when the dorm is viewed"""
        response = super().get(request, *args, **kwargs)
        dorm = self.object
        dorm.recent_views += 1
        dorm.save(update_fields=['recent_views'])
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['amenities'] = self.object.amenities.all()  # Get amenities for this dorm
        context['dorm_id'] = self.object.id  # Pass dorm_id to context
        context['form'] = ReviewForm()  # Pass the review form to the template
        context['latitude'] = self.object.latitude  # Pass dorm latitude
        context['longitude'] = self.object.longitude  # Pass dorm longitude
        
        # Add schools to the context
        from dormitory.models import School  # Import your School model
        context['schools'] = School.objects.all()  # Or filter as needed

        # Get similar dorms based on price range, amenities, and location
        current_dorm = self.object
        # Convert float multipliers to Decimal
        price_range = (
            current_dorm.price * Decimal('0.7'), 
            current_dorm.price * Decimal('1.3')
        )  # ±30% price range
        
        similar_dorms = Dorm.objects.select_related('landlord').prefetch_related(
            'images', 'amenities', 'reviews'
        ).filter(
            available=True,
            approval_status="approved",
            price__range=price_range,
            accommodation_type=current_dorm.accommodation_type
        ).exclude(
            id=current_dorm.id  # Exclude current dorm
        ).annotate(
            avg_rating=models.Avg('reviews__rating'),
            review_count=models.Count('reviews'),
            amenity_match=models.Count(
                'amenities',
                filter=models.Q(amenities__in=current_dorm.amenities.all())
            )
        ).order_by('-amenity_match', '-avg_rating')[:4]  # Get top 4 similar dorms

        context['similar_dorms'] = similar_dorms

        # Get user's reviewable reservation for this dorm
        if self.request.user.is_authenticated and self.request.user != self.object.landlord:
            user_reservation = self.request.user.reservation_set.filter(
                dorm=self.object,
                status__in=['confirmed', 'completed']
            ).first()
            if user_reservation and not hasattr(user_reservation, 'review'):
                context['user_reservation'] = user_reservation
        
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()  # Get the dorm object
        form = ReviewForm(request.POST)

        if form.is_valid():
            review = form.save(commit=False)
            review.dorm = self.object  # Associate review with the dorm
            review.user = request.user  # Associate review with the logged-in user
            review.save()
            return redirect('dormitory:dorm_detail', pk=self.object.pk)  # Refresh the page

        return self.render_to_response(self.get_context_data(form=form))


# 🚀 Landlord's Dorms (My Dorms)
class MyDormsView(LoginRequiredMixin, ListView):
    model = Dorm
    template_name = "dormitory/my_dorms.html"
    context_object_name = "my_dorms"

    def get_queryset(self):
        """Ensure only landlords can access their own dorms."""
        if self.request.user.user_type != "landlord":
            return redirect("accounts:dashboard")
        return Dorm.objects.filter(landlord=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass landlord's dorm locations
        context["dorm_locations"] = list(Dorm.objects.filter(landlord=self.request.user).values("id", "latitude", "longitude", "name"))
        return context


# 🚀 Edit Dorm (For Landlords)
class EditDormView(LoginRequiredMixin, UpdateView):
    model = Dorm
    form_class = DormForm
    template_name = "dormitory/edit_dorm.html"

    def get_queryset(self):
        return Dorm.objects.filter(landlord=self.request.user)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                dorm = form.save(commit=False)
                
                # Debugging - print received coordinates
                print(f"Received coordinates - Lat: {form.cleaned_data['latitude']}, Lng: {form.cleaned_data['longitude']}")
                
                # Explicitly set coordinates
                dorm.latitude = form.cleaned_data['latitude']
                dorm.longitude = form.cleaned_data['longitude']
                
                # Handle file uploads/deletions
                self.handle_files(dorm)
                
                dorm.save()
                form.save_m2m()  # Save amenities
                
                messages.success(self.request, "Dorm updated successfully!")
                return super().form_valid(form)
                
        except Exception as e:
            messages.error(self.request, f"Error updating dorm: {str(e)}")
            return self.form_invalid(form)

    def handle_files(self, dorm):
        """Handle all file operations"""
        # Permit handling
        if 'permit' in self.request.FILES:
            dorm.permit = self.request.FILES['permit']
        elif 'delete_permit' in self.request.POST and dorm.permit:
            dorm.permit.delete(save=False)
            dorm.permit = None
        
        # Payment QR handling
        if 'payment_qr' in self.request.FILES:
            dorm.payment_qr = self.request.FILES['payment_qr']
        elif 'delete_payment_qr' in self.request.POST and dorm.payment_qr:
            dorm.payment_qr.delete(save=False)
            dorm.payment_qr = None
        
        # Image handling
        for image in dorm.images.all():
            if f'delete_image_{image.id}' in self.request.POST:
                image.delete()
        
        # Add new images
        for image in self.request.FILES.getlist('images'):
            DormImage.objects.create(dorm=dorm, image=image)

    def get_success_url(self):
        return reverse_lazy("accounts:dashboard")




# 🚀 Delete Dorm (For Landlords)
class DeleteDormView(LoginRequiredMixin, DeleteView):
    model = Dorm
    template_name = "dormitory/confirm_delete.html"
    success_url = reverse_lazy("accounts:dashboard")

    def get_queryset(self):
        """Ensure only the landlord can delete their dorms."""
        return Dorm.objects.filter(landlord=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Dorm successfully deleted!")
        return super().delete(request, *args, **kwargs)

class RoommateListView(LoginRequiredMixin, ListView):
    model = RoommatePost
    template_name = "dormitory/roommate_list.html"
    context_object_name = "roommates"
    ordering = ["-date_posted"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add user's own post to context
        context['user_post'] = RoommatePost.objects.filter(user=self.request.user).first()
        return context

# Create Roommate Post
class RoommateCreateView(LoginRequiredMixin, CreateView):
    model = RoommatePost
    form_class = RoommatePostForm
    template_name = "dormitory/add_roommate.html"
    success_url = reverse_lazy("dormitory:roommate_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Your roommate profile has been successfully created!")
        return response
    
class RoommateDetailView(LoginRequiredMixin, DetailView):
    model = RoommatePost
    template_name = "dormitory/roommate_detail.html"
    context_object_name = "roommate"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add user's own post to context for Connect button
        context['user_post'] = RoommatePost.objects.filter(user=self.request.user).first()
        return context

class RoommateUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = RoommatePost
    form_class = RoommatePostForm
    template_name = "dormitory/edit_roommate.html"

    def test_func(self):
        roommate = self.get_object()
        return self.request.user == roommate.user  # Only allow owner to edit

    def get_success_url(self):
        return reverse_lazy("dormitory:roommate_list")

class RoommateDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = RoommatePost
    template_name = "dormitory/delete_roommate.html"
    success_url = reverse_lazy("dormitory:roommate_list")

    def test_func(self):
        roommate = self.get_object()
        return self.request.user == roommate.user  # Only allow owner to delete
    

class ReviewListView(ListView):
    model = Review
    template_name = "dormitory/review_list.html"
    context_object_name = "reviews"

    def get_queryset(self):
        """Get all reviews for a specific dorm."""
        dorm = get_object_or_404(Dorm, id=self.kwargs["dorm_id"])
        return dorm.reviews.all()

    def get_context_data(self, **kwargs):
        """Pass the dorm object to the template."""
        context = super().get_context_data(**kwargs)
        context["dorm"] = get_object_or_404(Dorm, id=self.kwargs["dorm_id"])
        return context
    
# 🚀 Submit a new review
class ReviewCreateView(LoginRequiredMixin, CreateView):
    model = Review
    form_class = ReviewForm
    template_name = "dormitory/add_review.html"

    def dispatch(self, request, *args, **kwargs):
        """Check if user has a confirmed or completed reservation for this dorm."""
        self.dorm = get_object_or_404(Dorm, id=self.kwargs["dorm_id"])
        
        # Check if user has a confirmed or completed reservation
        valid_reservation = Reservation.objects.filter(
            dorm=self.dorm,
            tenant=request.user,
            status__in=['confirmed', 'completed']
        ).first()
        
        if not valid_reservation:
            messages.error(request, "You can only review dorms after your reservation is confirmed.")
            return redirect("dormitory:dorm_detail", pk=self.dorm.id)
            
        # Check if user has already reviewed this reservation
        if Review.objects.filter(reservation=valid_reservation).exists():
            messages.error(request, "You have already reviewed this reservation.")
            return redirect("dormitory:dorm_detail", pk=self.dorm.id)
            
        self.reservation = valid_reservation
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Assign the user, dorm, and reservation before saving."""
        form.instance.dorm = self.dorm
        form.instance.user = self.request.user
        form.instance.reservation = self.reservation
        response = super().form_valid(form)
        messages.success(self.request, "Review added successfully!")
        return response

    def get_success_url(self):
        """Redirect to the dorm's review list after submission."""
        return reverse_lazy("dormitory:dorm_detail", kwargs={"pk": self.kwargs["dorm_id"]})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["dorm"] = self.dorm
        context["reservation"] = self.reservation
        return context

class ReviewUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Review
    form_class = ReviewForm
    template_name = "dormitory/edit_review.html"

    def test_func(self):
        """Ensure only the review owner can edit."""
        review = self.get_object()
        return self.request.user == review.user

    def form_valid(self, form):
        messages.success(self.request, "Review updated successfully!")
        return super().form_valid(form)

    def get_success_url(self):
        """Redirect back to the dorm detail page after update."""
        return reverse_lazy("dormitory:dorm_detail", kwargs={"pk": self.object.dorm.id})

class ReviewDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Review
    template_name = "dormitory/delete_review.html"

    def test_func(self):
        """Ensure only the review owner can delete."""
        review = self.get_object()
        return self.request.user == review.user

    def delete(self, request, *args, **kwargs):
        """Add a success message when a review is deleted."""
        messages.success(request, "Review deleted successfully!")
        return super().delete(request, *args, **kwargs)

    def get_success_url(self):
        """Redirect back to the dorm detail page after deletion."""
        return reverse_lazy("dormitory:dorm_detail", kwargs={"pk": self.object.dorm.id})


@method_decorator(login_required, name='dispatch')
class ReservationCreateView(CreateView):
    model = Reservation
    form_class = ReservationForm
    template_name = "dormitory/reservation_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'tenant':
            messages.error(request, "Only tenants can make reservations.")
            return redirect('accounts:dashboard')
        
        # Get the dorm and store it as an instance variable
        self.dorm = get_object_or_404(Dorm, id=self.kwargs['dorm_id'])
        
        # Check if user already has a reservation for this dorm
        existing_reservation = Reservation.objects.filter(
            dorm=self.dorm,
            tenant=request.user,
            status__in=['pending', 'confirmed']
        ).first()
        
        if existing_reservation:
            return redirect(f"{reverse('dormitory:tenant_reservations')}?selected_reservation={existing_reservation.pk}")
            
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()
        return form_class(dorm=self.dorm, **self.get_form_kwargs())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dorm'] = self.dorm
        return context

    def form_valid(self, form):
        form.instance.dorm = self.dorm
        form.instance.tenant = self.request.user
        form.instance.status = 'pending'
        
        # Save the reservation
        self.object = form.save()
        
        # Create initial message
        Message.objects.create(
            sender=self.request.user,
            receiver=self.dorm.landlord,
            content=f"Hi! I'm interested in your dorm {self.dorm.name}. I would like to inquire about availability and make a reservation.",
            dorm=self.dorm,
            reservation=self.object
        )
        notify_user(
            user=self.dorm.landlord,
            message=f"{self.request.user.get_full_name() or self.request.user.username} requested a reservation for {self.dorm.name}.",
            related_object_id=self.object.id
        )
        
        messages.success(self.request, "Your reservation inquiry has been sent! Please wait for the landlord's confirmation.")
        
        return super().form_valid(form)

    def get_success_url(self):
        """Return the URL to redirect to after processing a valid form."""
        base_url = reverse('dormitory:tenant_reservations')
        return f"{base_url}?selected_reservation={self.object.pk}"

@login_required
@require_POST
def update_reservation_status(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)
    
    # Only landlords can update status
    if request.user != reservation.dorm.landlord:
        return JsonResponse({'error': 'Not authorized'}, status=403)
    
    new_status = request.POST.get('status')
    if new_status not in ['confirmed', 'declined']:
        return JsonResponse({'error': 'Invalid status'}, status=400)
    
    reservation.status = new_status
    # Update room availability if room is assigned
    if reservation.room is not None:
        if new_status == 'confirmed':
            reservation.room.is_available = False
        elif new_status == 'declined':
            reservation.room.is_available = True
        reservation.room.save()
    reservation.save()
    
    # Create a system message about the status change
    ReservationMessage.objects.create(
        reservation=reservation,
        sender=request.user,
        content=f"Reservation has been {new_status}."
    )
    
    return JsonResponse({'status': 'success', 'new_status': new_status})

@method_decorator(login_required, name='dispatch')
class ChatView(ListView):
    model = Message
    template_name = "dormitory/chat.html"
    context_object_name = "messages"



    def get_queryset(self):
        user = self.request.user
        return Message.objects.filter(Q(sender=user) | Q(receiver=user)).order_by("timestamp")


    def post(self, request, *args, **kwargs):
        sender = request.user
        receiver_id = request.POST.get('receiver_id')
        content = request.POST.get('content')


        if not receiver_id or not content:
            # You may want to handle error message
            return redirect('dormitory:chat')


        receiver = get_object_or_404(CustomUser, id=receiver_id)
        message = Message.objects.create(sender=sender, receiver=receiver, content=content)
        notify_user(
            user=receiver,
            message=f"New message from {sender.get_full_name() or sender.username}: {content[:60]}",
            related_object_id=message.id
        )
        return redirect('dormitory:chat')

@method_decorator(login_required, name='dispatch')
class ReservationPaymentView(DetailView):
    model = Reservation
    template_name = 'dormitory/reservation_payment.html'
    context_object_name = 'reservation'
    pk_url_kwarg = 'reservation_id'

    def get_queryset(self):
        # Only allow access to reservations that belong to the current user
        return Reservation.objects.select_related('dorm').filter(tenant=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.object.qr_code:
            messages.warning(self.request, "QR code not found. Please contact support.")
        return context

    def dispatch(self, request, *args, **kwargs):
        # Get the reservation first
        self.object = self.get_object()
        if not self.object:
            messages.error(request, "Reservation not found.")
            return redirect('dormitory:dorm_list')
        return super().dispatch(request, *args, **kwargs)

@method_decorator(login_required, name='dispatch')
class LandlordReservationsView(ListView):
    model = Reservation
    template_name = 'dormitory/landlord_reservations.html'
    context_object_name = 'reservations'

    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'landlord':
            messages.error(request, "Only landlords can access this page.")
            return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Reservation.objects.select_related('dorm', 'tenant').prefetch_related(
            'chat_messages'
        ).filter(
            dorm__landlord=self.request.user
        ).order_by('-reservation_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get counts for different reservation statuses
        queryset = self.get_queryset()
        context['pending_count'] = queryset.filter(status='pending').count()
        context['confirmed_count'] = queryset.filter(status='confirmed').count()
        context['declined_count'] = queryset.filter(status='declined').count()
        context['completed_count'] = queryset.filter(status='completed').count()
        
        # Get selected reservation for chat
        selected_reservation_id = self.request.GET.get('selected_reservation')
        if selected_reservation_id:
            try:
                selected_reservation = queryset.prefetch_related(
                    'chat_messages'
                ).get(id=selected_reservation_id)
                context['selected_reservation'] = selected_reservation
                # Mark messages as read
                Message.objects.filter(
                    reservation=selected_reservation,
                    receiver=self.request.user,
                    is_read=False
                ).update(is_read=True)
            except Reservation.DoesNotExist:
                messages.error(self.request, "Selected reservation not found.")
        
        return context

@method_decorator(login_required, name='dispatch')
class UpdateReservationStatusView(View):
    def post(self, request, reservation_id):
        # Check if the request is from a landlord or tenant
        if request.user.user_type == 'landlord':
            reservation = get_object_or_404(Reservation, id=reservation_id, dorm__landlord=request.user)
        else:
            reservation = get_object_or_404(Reservation, id=reservation_id, tenant=request.user)
        
        action = request.POST.get('action')
        
        if action == 'confirm':
            if request.user.user_type != 'landlord':
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'error': 'Only landlords can confirm reservations.'}, status=403)
                messages.error(request, "Only landlords can confirm reservations.")
                return redirect('dormitory:tenant_reservations')
                
            reservation.status = 'confirmed'
            # Decrement available_beds if greater than 0
            dorm = reservation.dorm
            if dorm.available_beds > 0:
                dorm.available_beds -= 1
                dorm.save()
            # Set room as unavailable if assigned
            if reservation.room is not None:
                reservation.room.is_available = False
                reservation.room.save()
            reservation.save()  # Save the reservation status change
            
            success_message = f"Reservation for {reservation.dorm.name} has been confirmed."
            messages.success(request, success_message)
            
            # Create a system message
            Message.objects.create(
                sender=request.user,
                receiver=reservation.tenant,
                content="Your reservation has been confirmed! You may proceed with the payment if you wish to secure your slot.",
                dorm=reservation.dorm,
                reservation=reservation
            )
            notify_user(
                user=reservation.tenant,
                message=f"Your reservation for {reservation.dorm.name} was confirmed.",
                related_object_id=reservation.id
            )
            
            # Return JSON response for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'message': success_message})
        elif action == 'verify_payment':
            if request.user.user_type != 'landlord':
                messages.error(request, "Only landlords can verify payments.")
                return redirect('dormitory:tenant_reservations')
                
            if reservation.payment_proof:
                reservation.has_paid_reservation = True
                messages.success(request, f"Payment for {reservation.dorm.name} has been verified.")
                # Create a system message
                Message.objects.create(
                    sender=request.user,
                    receiver=reservation.tenant,
                    content="Your payment has been verified. Your slot is now secured!",
                    dorm=reservation.dorm,
                    reservation=reservation
                )
                notify_user(
                    user=reservation.tenant,
                    message=f"Payment for {reservation.dorm.name} was verified.",
                    related_object_id=reservation.id
                )
            else:
                messages.error(request, "No payment proof found for this reservation.")
                return redirect('dormitory:landlord_reservations')
        elif action == 'reject_payment':
            if request.user.user_type != 'landlord':
                messages.error(request, "Only landlords can reject payments.")
                return redirect('dormitory:tenant_reservations')
                
            if reservation.payment_proof:
                # Clear the payment proof and reset payment status
                reservation.payment_proof.delete(save=False)
                reservation.payment_proof = None
                reservation.payment_submitted_at = None
                reservation.has_paid_reservation = False
                messages.warning(request, f"Payment proof for {reservation.dorm.name} has been rejected.")
                # Create a system message
                Message.objects.create(
                    sender=request.user,
                    receiver=reservation.tenant,
                    content="Your payment proof has been rejected. Please submit a new payment proof.",
                    dorm=reservation.dorm,
                    reservation=reservation
                )
                notify_user(
                    user=reservation.tenant,
                    message=f"Payment proof for {reservation.dorm.name} was rejected. Please upload a new copy.",
                    related_object_id=reservation.id
                )
            else:
                messages.error(request, "No payment proof found for this reservation.")
        elif action == 'decline':
            if request.user.user_type != 'landlord':
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'error': 'Only landlords can decline reservations.'}, status=403)
                messages.error(request, "Only landlords can decline reservations.")
                return redirect('dormitory:tenant_reservations')
            
            decline_reason = request.POST.get('decline_reason')
            if not decline_reason:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'error': 'Please provide a reason for declining the reservation.'}, status=400)
                messages.error(request, "Please provide a reason for declining the reservation.")
                return redirect('dormitory:landlord_reservations')
            
            reservation.status = 'declined'
            reservation.cancellation_reason = decline_reason
            # Set room as available if assigned
            if reservation.room is not None:
                reservation.room.is_available = True
                reservation.room.save()
            reservation.save()  # Save the reservation status change
            
            success_message = f"Reservation for {reservation.dorm.name} has been declined."
            messages.warning(request, success_message)
            
            # Create a system message
            Message.objects.create(
                sender=request.user,
                receiver=reservation.tenant,
                content=f"Your reservation has been declined. Reason: {decline_reason}",
                dorm=reservation.dorm,
                reservation=reservation
            )
            notify_user(
                user=reservation.tenant,
                message=f"Reservation for {reservation.dorm.name} was declined. Reason: {decline_reason}",
                related_object_id=reservation.id
            )
            
            # Return JSON response for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'message': success_message})
        elif action == 'cancel':
            if request.user.user_type != 'tenant':
                messages.error(request, "Only tenants can cancel their reservations.")
                return redirect('dormitory:landlord_reservations')
            
            if reservation.status not in ['pending', 'confirmed'] or reservation.has_paid_reservation:
                messages.error(request, "You cannot cancel this reservation at this stage.")
                return redirect('dormitory:tenant_reservations')
            
            # Get cancellation reason from form
            cancellation_reason = request.POST.get('cancellation_reason')
            if not cancellation_reason:
                messages.error(request, "Please provide a reason for cancellation.")
                return redirect('dormitory:tenant_reservations')
            
            reservation.status = 'cancelled'
            reservation.cancellation_reason = cancellation_reason
            # Set room as available if assigned
            if reservation.room is not None:
                reservation.room.is_available = True
                reservation.room.save()
            messages.warning(request, f"Your reservation for {reservation.dorm.name} has been cancelled.")
            
            # Create first system message about cancellation
            Message.objects.create(
                sender=request.user,
                receiver=reservation.dorm.landlord,
                content="The tenant has cancelled their reservation.",
                dorm=reservation.dorm,
                reservation=reservation
            )
            
            # Create second system message with the reason
            Message.objects.create(
                sender=request.user,
                receiver=reservation.dorm.landlord,
                content=f"Reason for cancellation: {cancellation_reason}",
                dorm=reservation.dorm,
                reservation=reservation
            )
            notify_user(
                user=reservation.dorm.landlord,
                message=f"{reservation.tenant.get_full_name() or reservation.tenant.username} cancelled their reservation for {reservation.dorm.name}.",
                related_object_id=reservation.id
            )
        elif action == 'complete':
            if request.user.user_type != 'landlord':
                messages.error(request, "Only landlords can complete transactions.")
                return redirect('dormitory:tenant_reservations')
            if reservation.status == 'confirmed':
                reservation.status = 'completed'
                messages.success(request, f"Transaction for {reservation.dorm.name} has been marked as complete.")
                # Create a system message
                Message.objects.create(
                    sender=request.user,
                    receiver=reservation.tenant,
                    content="Transaction has been marked as complete. Thank you for using our service!",
                    dorm=reservation.dorm,
                    reservation=reservation
                )
                notify_user(
                    user=reservation.tenant,
                    message=f"Transaction for {reservation.dorm.name} has been marked complete.",
                    related_object_id=reservation.id
                )
            else:
                messages.error(request, "Only confirmed reservations can be marked as complete.")
        elif action == 'make_available':
            if request.user.user_type != 'landlord':
                messages.error(request, "Only landlords can manage room availability.")
                return redirect('dormitory:tenant_reservations')
            if reservation.room is not None:
                reservation.room.is_available = True
                reservation.room.save()
                dorm = reservation.dorm
                if hasattr(dorm, 'available_beds'):
                    dorm.available_beds = (dorm.available_beds or 0) + 1
                    dorm.save()
                messages.success(request, f"Room set to available for {reservation.dorm.name}.")
                Message.objects.create(
                    sender=request.user,
                    receiver=reservation.tenant,
                    content="The room you reserved has been marked available by the landlord.",
                    dorm=reservation.dorm,
                    reservation=reservation
                )
                notify_user(
                    user=reservation.tenant,
                    message=f"The room for {reservation.dorm.name} is available again.",
                    related_object_id=reservation.id
                )
            else:
                messages.error(request, "No room is assigned to this reservation.")
        
        reservation.save()
        
        # Redirect based on user type (only for non-AJAX requests)
        if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
            if request.user.user_type == 'landlord':
                return redirect('dormitory:landlord_reservations')
            else:
                return redirect('dormitory:tenant_reservations')
        else:
            # For AJAX requests that didn't return earlier, return a generic success
            return JsonResponse({'status': 'success', 'message': 'Action completed successfully.'})

# Update the context processor to include pending reservations
def user_context(request):
    """Context processor optimized to reduce database queries."""
    from django.core.cache import cache
    
    context = {}
    if not request.user.is_authenticated:
        return context
    
    # Cache reservation data for 30 seconds to reduce queries
    if request.user.user_type == 'tenant':
        cache_key = f'tenant_reservations_{request.user.id}'
        reservations = cache.get(cache_key)
        if reservations is None:
            reservations = list(Reservation.objects.filter(
                tenant=request.user,
                status__in=['pending_payment', 'pending', 'confirmed']
            ).select_related('dorm').order_by('-created_at')[:5])  # Limit to 5
            cache.set(cache_key, reservations, 30)
        context['user_pending_reservations'] = reservations
    elif request.user.user_type == 'landlord':
        cache_key = f'landlord_pending_count_{request.user.id}'
        pending_count = cache.get(cache_key)
        if pending_count is None:
            pending_count = Reservation.objects.filter(
                dorm__landlord=request.user,
                status='pending'
            ).count()
            cache.set(cache_key, pending_count, 30)
        context['pending_count'] = pending_count
    return context

@method_decorator(login_required, name='dispatch')
class tenantReservationsView(ListView):
    model = Reservation
    template_name = 'dormitory/tenant_reservations.html'
    context_object_name = 'reservations'

    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'tenant':
            messages.error(request, "Only tenants can access this page.")
            return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Reservation.objects.select_related('dorm').filter(
            tenant=self.request.user
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get counts for different reservation statuses
        queryset = self.get_queryset()
        context['pending_payment_count'] = queryset.filter(status='pending_payment').count()
        context['pending_count'] = queryset.filter(status='pending').count()
        context['confirmed_count'] = queryset.filter(status='confirmed').count()
        context['completed_count'] = queryset.filter(status='completed').count()
        context['declined_count'] = queryset.filter(status='declined').count()
        
        # Get selected reservation for chat
        selected_reservation_id = self.request.GET.get('selected_reservation')
        if selected_reservation_id:
            try:
                selected_reservation = queryset.prefetch_related('messages').get(id=selected_reservation_id)
                context['selected_reservation'] = selected_reservation
            except Reservation.DoesNotExist:
                messages.error(self.request, "Selected reservation not found.")
        
        return context

    def post(self, request, *args, **kwargs):
        reservation_id = request.GET.get('selected_reservation')
        if not reservation_id:
            messages.error(request, "No reservation selected.")
            return redirect('dormitory:tenant_reservations')

        try:
            reservation = Reservation.objects.get(
                id=reservation_id,
                tenant=request.user
            )

            if 'payment_proof' in request.FILES:
                # Handle payment proof upload
                payment_proof = request.FILES['payment_proof']
                reservation.payment_proof = payment_proof
                reservation.payment_submitted_at = timezone.now()
                reservation.has_paid_reservation = True
                reservation.payment_amount = reservation.dorm.price  # Set amount to dorm price
                reservation.save()

                # Create a message about the payment submission
                Message.objects.create(
                    sender=request.user,
                    receiver=reservation.dorm.landlord,
                    content="Payment proof has been submitted.",
                    dorm=reservation.dorm,
                    reservation=reservation
                )

                messages.success(request, "Payment proof uploaded successfully!")
            elif 'cancellation_reason' in request.POST:
                # If cancelling, set the cancellation reason
                cancellation_reason = request.POST.get('cancellation_reason')
                reservation.cancellation_reason = cancellation_reason
                reservation.status = 'cancelled'
                reservation.save()
                messages.success(request, "Reservation cancelled.")
            else:
                messages.error(request, "No payment proof file was uploaded.")

        except Reservation.DoesNotExist:
            messages.error(request, "Reservation not found.")

        base_url = reverse('dormitory:tenant_reservations')
        return redirect(f"{base_url}?selected_reservation={reservation_id}")

@method_decorator(login_required, name='dispatch')
class MessagesView(ListView):
    template_name = 'dormitory/messages.html'
    context_object_name = 'conversations'

    def get_queryset(self):
        user = self.request.user
        base_query = Message.objects.values('dorm', 'sender', 'receiver')
        base_query = base_query.annotate(
            last_message=Max('timestamp'),
            unread_count=Count('id', Q(is_read=False, receiver=user))
        )

        if user.user_type == 'landlord':
            # For landlords, get all messages related to their dorms
            return base_query.filter(dorm__landlord=user).order_by('-last_message')
        else:
            # For tenants, get all messages they're involved in
            return base_query.filter(
                Q(sender=user) | Q(receiver=user)
            ).order_by('-last_message')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversation_id = self.request.GET.get('conversation')
        
        if conversation_id:
            # Get the selected conversation
            conversation = Message.objects.filter(id=conversation_id).first()
            if conversation:
                context['selected_conversation'] = conversation
                # Mark messages as read
                Message.objects.filter(
                    dorm=conversation.dorm,
                    receiver=self.request.user,
                    is_read=False
                ).update(is_read=True)
                # Get messages for this conversation
                context['messages'] = Message.objects.filter(
                    dorm=conversation.dorm
                ).filter(
                    Q(sender=conversation.sender, receiver=conversation.receiver) |
                    Q(sender=conversation.receiver, receiver=conversation.sender)
                ).order_by('timestamp')
        
        return context

@method_decorator(login_required, name='dispatch')
class SendMessageView(View):
    def post(self, request, *args, **kwargs):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request'})
        
        content = request.POST.get('content', '')
        reservation_id = request.POST.get('reservation_id')
        
        if not reservation_id:
            return JsonResponse({'status': 'error', 'message': 'Missing reservation ID'})
        
        try:
            # Fix: Move Q objects to filter() instead of get()
            reservation = Reservation.objects.filter(
                Q(tenant=request.user) | Q(dorm__landlord=request.user)
            ).get(id=reservation_id)
            
            # Determine the receiver
            if request.user == reservation.tenant:
                receiver = reservation.dorm.landlord
            else:
                receiver = reservation.tenant
            
            # Handle file uploads
            attachment = request.FILES.get('attachment')
            image = request.FILES.get('image')
            
            # Create the message
            message = Message.objects.create(
                sender=request.user,
                receiver=receiver,
                content=content,
                dorm=reservation.dorm,
                reservation=reservation,
                attachment=attachment if attachment else None,
                image=image if image else None
            )
            snippet = content or ("[Attachment]" if attachment else "[Image]")
            notify_user(
                user=receiver,
                message=f"New reservation chat message about {reservation.dorm.name}: {snippet[:60]}",
                related_object_id=reservation.id
            )
            
            # Prepare response data
            response_data = {
                'status': 'success',
                'message': {
                    'id': message.id,
                    'content': message.content,
                    'timestamp': message.timestamp.strftime('%I:%M %p'),
                    'sender_name': message.sender.get_full_name(),
                    'has_attachment': bool(message.attachment),
                    'has_image': bool(message.image),
                    'file_url': message.attachment.url if message.attachment else None,
                    'image_url': message.image.url if message.image else None,
                    'file_name': message.get_file_name if message.attachment else None,
                    'is_image': message.is_image
                }
            }
            
            return JsonResponse(response_data)
            
        except Reservation.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Reservation not found'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

@method_decorator(login_required, name='dispatch')
class CheckNewMessagesView(View):
    def get(self, request, reservation_id):
        try:
            # Fix: Move Q objects to filter() instead of get()
            reservation = Reservation.objects.filter(
                Q(tenant=request.user) | Q(dorm__landlord=request.user)
            ).get(id=reservation_id)
            
            # Check for unread messages
            has_new_messages = Message.objects.filter(
                reservation=reservation,
                receiver=request.user,
                is_read=False
            ).exists()
            
            return JsonResponse({
                'hasNewMessages': has_new_messages
            })
        except Reservation.DoesNotExist:
            return JsonResponse({
                'error': 'Reservation not found'
            }, status=404)

class RoommateMatchesView(LoginRequiredMixin, ListView):
    model = RoommateMatch
    template_name = 'dormitory/roommate_matches.html'
    context_object_name = 'matches'

    def get_queryset(self):
        user_post = RoommatePost.objects.filter(user=self.request.user).first()
        if not user_post:
            return RoommateMatch.objects.none()
            
        return RoommateMatch.objects.filter(
            models.Q(initiator=user_post) | models.Q(target=user_post)
        ).select_related('initiator', 'target').prefetch_related('messages')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_post = RoommatePost.objects.filter(user=self.request.user).first()
        
        if user_post:
            # Get potential matches
            potential_matches = RoommateMatchingService.find_matches(user_post)
            context['potential_matches'] = potential_matches
            context['user_post'] = user_post
            
            # Get selected match for chat
            selected_match_id = self.request.GET.get('selected_match')
            if selected_match_id:
                try:
                    selected_match = self.get_queryset().get(id=selected_match_id)
                    context['selected_match'] = selected_match
                    # Get chat messages with reactions
                    context['chat_messages'] = selected_match.messages.all().prefetch_related('reactions')
                    if selected_match.initiator.user == self.request.user:
                        context['chat_partner'] = selected_match.target
                    else:
                        context['chat_partner'] = selected_match.initiator
                    # Mark messages as read
                    RoommateChat.objects.filter(
                        match=selected_match,
                        receiver=self.request.user,
                        is_read=False
                    ).update(is_read=True)
                except RoommateMatch.DoesNotExist:
                    messages.error(self.request, "Selected match not found.")
        
        context['unread_message_count'] = RoommateChat.objects.filter(
            match__in=context.get('matches', []),
            receiver=self.request.user,
            is_read=False
        ).count()
        
        return context

@method_decorator([csrf_exempt, login_required], name='dispatch')
class InitiateRoommateMatchView(LoginRequiredMixin, View):
    def post(self, request, target_id):
        try:
            target_post = get_object_or_404(RoommatePost, id=target_id)
            user_post = RoommatePost.objects.filter(user=request.user).first()
            
            if not user_post:
                return JsonResponse({'error': 'You need to create a roommate post first'}, status=400)
                
            if target_post.user == request.user:
                return JsonResponse({'error': 'You cannot match with yourself'}, status=400)
                
            # Check if active match exists (pending or accepted)
            existing_match = RoommateMatch.objects.filter(
                (models.Q(initiator=user_post, target=target_post) |
                models.Q(initiator=target_post, target=user_post)) &
                models.Q(status__in=['pending', 'accepted'])
            ).first()
            
            if existing_match:
                return JsonResponse({
                    'error': 'Active match already exists',
                    'match_id': existing_match.id
                }, status=400)
                
            # Create new match
            match = RoommateMatchingService.create_match(user_post, target_post)
            
            # Create initial system message
            RoommateChat.objects.create(
                match=match,
                sender=request.user,
                receiver=target_post.user,
                content=f"{request.user.get_full_name()} has initiated a match with you!"
            )
            
            return JsonResponse({
                'status': 'success',
                'match_id': match.id,
                'compatibility_score': float(match.compatibility_score)
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

@method_decorator(login_required, name='dispatch')
class UpdateRoommateMatchStatusView(LoginRequiredMixin, View):
    def post(self, request, match_id):
        match = get_object_or_404(RoommateMatch, id=match_id)
        
        # Only allow target user to update status
        if request.user != match.target.user:
            return JsonResponse({'error': 'Not authorized'}, status=403)
            
        new_status = request.POST.get('status')
        if new_status not in ['accepted', 'rejected']:
            return JsonResponse({'error': 'Invalid status'}, status=400)
            
        match.status = new_status
        match.save()
        
        # Create system message about the status change
        RoommateChat.objects.create(
            match=match,
            sender=request.user,
            receiver=match.initiator.user,
            content=f"Match has been {new_status}."
        )
        
        return JsonResponse({'status': 'success', 'new_status': new_status})

@method_decorator(login_required, name='dispatch')
class SendRoommateChatMessageView(View):
    def post(self, request, match_id):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Invalid request'}, status=400)
            
        match = get_object_or_404(RoommateMatch, id=match_id)
        
        # Verify user is involved in the match
        if request.user not in [match.initiator.user, match.target.user]:
            return JsonResponse({'error': 'Not authorized'}, status=403)
            
        content = (request.POST.get('content') or '').strip()
        image_file = request.FILES.get('image')

        # Allow sending either text or image (or both)
        if not content and not image_file:
            return JsonResponse({'error': 'Please enter a message or choose an image.'}, status=400)

        # If an image is present, store it and encode the URL in content with a prefix marker
        image_url = None
        if image_file:
            # Reuse media storage; keep folder consistent with other chats
            saved_path = default_storage.save(f"chat_images/{image_file.name}", image_file)
            image_url = settings.MEDIA_URL + saved_path
            if not content:
                content = f"[image]{image_url}"

        # Create the message
        message = RoommateChat.objects.create(
            match=match,
            sender=request.user,
            content=content
        )
        notify_user(
            user=message.receiver,
            message=f"New roommate chat from {request.user.get_full_name() or request.user.username}: {content[:60]}",
            related_object_id=match.id
        )

        return JsonResponse({
            'status': 'success',
            'message': {
                'id': message.id,
                'content': message.content,
                'timestamp': message.timestamp.strftime('%I:%M %p'),
                'sender_name': message.sender.get_full_name(),
                'has_image': bool(image_url),
                'image_url': image_url
            }
        })

@method_decorator([csrf_exempt, login_required], name='dispatch')
class ToggleMessageReactionView(View):
    def post(self, request, message_id):
        try:
            message = get_object_or_404(RoommateChat, id=message_id)
            emoji = request.POST.get('emoji')
            
            # Check if user is part of this conversation
            if request.user not in [message.match.initiator.user, message.match.target.user]:
                return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
            
            # Check if reaction already exists
            reaction, created = RoommateChatReaction.objects.get_or_create(
                message=message,
                user=request.user,
                emoji=emoji
            )
            
            if not created:
                # Remove reaction if it already exists
                reaction.delete()
                action = 'removed'
            else:
                action = 'added'
            
            # Get updated reaction summary
            reactions_summary = message.get_reactions_summary()
            
            return JsonResponse({
                'status': 'success',
                'action': action,
                'reactions': reactions_summary
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@method_decorator(login_required, name='dispatch')
class ManageRoomsView(View):
    def get(self, request, dorm_id):
        dorm = get_object_or_404(Dorm, id=dorm_id, landlord=request.user)
        rooms = dorm.rooms.all().prefetch_related("images")  # optimize query
        room_form = RoomForm()
        return render(request, 'dormitory/manage_rooms.html', {
            'dorm': dorm,
            'rooms': rooms,
            'room_form': room_form,
        })

    def post(self, request, dorm_id):
        dorm = get_object_or_404(Dorm, id=dorm_id, landlord=request.user)
        action = request.POST.get('action')

        # ✅ Toggle availability
        if action == 'toggle_availability':
            room_id = request.POST.get('room_id')
            room = get_object_or_404(Room, id=room_id, dorm=dorm)
            room.is_available = not room.is_available
            room.save()

            # ✅ Keep dorm’s available_beds updated if exists
            if hasattr(dorm, 'available_beds') and hasattr(dorm, 'total_beds'):
                dorm.available_beds = dorm.rooms.filter(is_available=True).count()
                dorm.save()

            messages.success(
                request, 
                f"Room '{room.name}' set to {'available' if room.is_available else 'unavailable'}."
            )
            return redirect('dormitory:manage_rooms', dorm_id=dorm.id)

        if action == 'edit_room':
            room_id = request.POST.get('room_id')
            room = get_object_or_404(Room, id=room_id, dorm=dorm)
            edit_form = RoomForm(request.POST, request.FILES, instance=room)
            if edit_form.is_valid():
                edit_form.save()
                new_images = request.FILES.getlist('images')
                for image in new_images:
                    RoomImage.objects.create(room=room, image=image)
                messages.success(request, f"Room '{room.name}' updated successfully!")
                return redirect('dormitory:manage_rooms', dorm_id=dorm.id)

            messages.error(request, "Unable to update room. Please check the form for errors.")
            return redirect('dormitory:manage_rooms', dorm_id=dorm.id)

        if action == 'delete_room':
            room_id = request.POST.get('room_id')
            room = get_object_or_404(Room, id=room_id, dorm=dorm)
            room_name = room.name
            room.delete()
            messages.success(request, f"Room '{room_name}' has been deleted.")
            return redirect('dormitory:manage_rooms', dorm_id=dorm.id)

        # ✅ Add new room
        room_form = RoomForm(request.POST, request.FILES)
        if room_form.is_valid():
            room = room_form.save(commit=False)
            room.dorm = dorm
            room.save()

            # Handle multiple images
            images = request.FILES.getlist('images')
            for image in images:
                RoomImage.objects.create(room=room, image=image)

            messages.success(request, f"Room '{room.name}' added successfully!")
            return redirect('dormitory:manage_rooms', dorm_id=dorm.id)

        if action != 'add_room':
            messages.error(request, "Invalid action.")
            return redirect('dormitory:manage_rooms', dorm_id=dorm.id)

        # If form invalid → redisplay with errors
        rooms = dorm.rooms.all().prefetch_related("images")
        return render(request, 'dormitory/manage_rooms.html', {
            'dorm': dorm,
            'rooms': rooms,
            'room_form': room_form,
        })

# Add this new home page view after the imports and before the existing views

class HomePageView(TemplateView):
    """Home page for non-logged-in users with recommendations"""
    template_name = "dormitory/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get popular dorms (most viewed, highest rated)
        popular_dorms = Dorm.objects.select_related('landlord').prefetch_related(
            'images', 'amenities', 'reviews'
        ).filter(
            available=True, 
            approval_status="approved"
        ).annotate(
            avg_rating=models.Avg('reviews__rating'),
            review_count=models.Count('reviews')
        ).order_by('-recent_views', '-avg_rating')[:6]

        # Get latest dorms
        latest_dorms = Dorm.objects.select_related('landlord').prefetch_related(
            'images', 'amenities', 'reviews'
        ).filter(
            available=True, 
            approval_status="approved"
        ).annotate(
            avg_rating=models.Avg('reviews__rating'),
            review_count=models.Count('reviews')
        ).order_by('-created_at')[:6]

        # Get roommate listings
        roommate_listings = RoommatePost.objects.select_related('user').prefetch_related(
            'amenities'
        ).order_by('-date_posted')[:4]

        # Get statistics
        total_dorms = Dorm.objects.filter(approval_status="approved", available=True).count()
        total_roommates = RoommatePost.objects.count()
        total_schools = School.objects.count()

        context.update({
            'popular_dorms': popular_dorms,
            'latest_dorms': latest_dorms,
            'roommate_listings': roommate_listings,
            'total_dorms': total_dorms,
            'total_roommates': total_roommates,
            'total_schools': total_schools,
        })
        
        return context