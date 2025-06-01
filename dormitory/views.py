from django.shortcuts import redirect, get_object_or_404 , render
from django.contrib.auth.mixins import LoginRequiredMixin , UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from .models import (
    Dorm, DormImage, Amenity, RoommatePost, Review, School, 
    Reservation, Dorm, Message, ReservationMessage
)
from .forms import DormForm ,  RoommatePostForm , ReviewForm , ReservationForm
from django.db.models import Avg , Q
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, ListView
from accounts.models import CustomUser
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import os
from django.views.generic import View
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST



# 🚀 Add Dorm (For Landlords)
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

        messages.success(self.request, "Dorm successfully created!")
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
        """Filter dorms based on search parameters"""
        queryset = Dorm.objects.filter(available=True, approval_status="approved").annotate(
            avg_rating=Avg("reviews__rating")
        )
        
        # Get filter parameters from request
        search_query = self.request.GET.get('search', '')
        target_price = self.request.GET.get('target_price')
        amenities = self.request.GET.getlist('amenities')
        school_id = self.request.GET.get('school')
        sort_by = self.request.GET.get('sort')
        
        # Apply filters
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | 
                Q(address__icontains=search_query) |
                Q(description__icontains=search_query)
            )
            
        if target_price:
            try:
                target_price = float(target_price)
                # Show dorms within ±500 of target price
                price_range = 500
                queryset = queryset.filter(
                    price__gte=target_price - price_range,
                    price__lte=target_price + price_range
                )
            except (ValueError, TypeError):
                pass
            
        if amenities:
            queryset = queryset.filter(amenities__id__in=amenities).distinct()
            
        if school_id:
            queryset = queryset.filter(nearby_schools__id=school_id)
            
        # Apply sorting
        if sort_by == 'price_asc':
            queryset = queryset.order_by('price')
        elif sort_by == 'price_desc':
            queryset = queryset.order_by('-price')
        elif sort_by == 'rating':
            queryset = queryset.order_by('-avg_rating')
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add filter-related context
        context['amenities'] = Amenity.objects.all()
        context['schools'] = School.objects.all()
        
        # Pass current filter values back to template
        context['current_search'] = self.request.GET.get('search', '')
        context['current_target_price'] = self.request.GET.get('target_price', '1000')
        context['selected_amenities'] = [int(a) for a in self.request.GET.getlist('amenities')]
        context['selected_school'] = self.request.GET.get('school', '')
        context['selected_sort'] = self.request.GET.get('sort', '')
        
        return context

# 🚀 Dorm Details

class DormDetailView(LoginRequiredMixin, DetailView):
    model = Dorm
    template_name = "dormitory/dorm_detail.html"
    context_object_name = "dorm"

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
        """Check if user has a completed reservation for this dorm."""
        self.dorm = get_object_or_404(Dorm, id=self.kwargs["dorm_id"])
        
        # Check if user has a completed reservation
        completed_reservation = Reservation.objects.filter(
            dorm=self.dorm,
            student=request.user,
            status='completed'
        ).first()
        
        if not completed_reservation:
            messages.error(request, "You can only review dorms after completing a reservation.")
            return redirect("dormitory:dorm_detail", pk=self.dorm.id)
            
        # Check if user has already reviewed this reservation
        if Review.objects.filter(reservation=completed_reservation).exists():
            messages.error(request, "You have already reviewed this reservation.")
            return redirect("dormitory:dorm_detail", pk=self.dorm.id)
            
        self.reservation = completed_reservation
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
        if request.user.user_type != 'student':
            messages.error(request, "Only students can make reservations.")
            return redirect('accounts:dashboard')
        
        # Get the dorm and store it as an instance variable
        self.dorm = get_object_or_404(Dorm, id=self.kwargs['dorm_id'])
        
        # Check if user already has a reservation for this dorm
        existing_reservation = Reservation.objects.filter(
            dorm=self.dorm,
            student=request.user,
            status__in=['pending_payment', 'pending', 'confirmed']
        ).first()
        
        if existing_reservation:
            return redirect('dormitory:reservation_detail', pk=existing_reservation.pk)
            
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dorm'] = self.dorm
        return context

    def form_valid(self, form):
        form.instance.dorm = self.dorm
        form.instance.student = self.request.user
        
        # Handle payment proof upload
        payment_proof = self.request.FILES.get('payment_proof')
        if payment_proof:
            form.instance.payment_proof = payment_proof
            form.instance.status = 'pending'
            form.instance.payment_submitted_at = timezone.now()
        else:
            form.instance.status = 'pending_payment'
        
        # Save the form
        self.object = form.save()
        messages.success(self.request, "Your reservation has been submitted successfully!")
        
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('dormitory:reservation_detail', kwargs={'pk': self.object.pk})

@method_decorator(login_required, name='dispatch')
class ReservationDetailView(DetailView):
    model = Reservation
    context_object_name = 'reservation'

    def get_template_names(self):
        """Return different templates based on user type"""
        if self.request.user.user_type == 'landlord':
            return ['dormitory/landlord_reservation_detail.html']
        return ['dormitory/student_reservation_detail.html']

    def get_queryset(self):
        # Students can only view their own reservations
        # Landlords can only view reservations for their dorms
        if self.request.user.user_type == 'student':
            return Reservation.objects.filter(student=self.request.user)
        elif self.request.user.user_type == 'landlord':
            return Reservation.objects.filter(dorm__landlord=self.request.user)
        return Reservation.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dorm'] = self.object.dorm
        context['messages'] = self.object.messages.all().order_by('timestamp')
        
        # Add state-based context
        context['can_edit'] = self.object.status in ['pending_payment', 'pending']
        context['can_chat'] = self.object.status not in ['declined', 'cancelled']
        context['show_payment_form'] = (
            self.request.user.user_type == 'student' and 
            self.object.status == 'pending_payment'
        )
        
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Handle message sending
        if 'message' in request.POST:
            content = request.POST.get('message')
            if content:
                ReservationMessage.objects.create(
                    reservation=self.object,
                    sender=request.user,
                    content=content
                )
                messages.success(request, "Message sent successfully!")
        
        # Handle status updates (for landlords only)
        elif 'status' in request.POST and request.user == self.object.dorm.landlord:
            new_status = request.POST.get('status')
            if new_status in ['confirmed', 'declined']:
                self.object.status = new_status
                self.object.save()
                
                # Create a system message about the status change
                ReservationMessage.objects.create(
                    reservation=self.object,
                    sender=request.user,
                    content=f"Reservation has been {new_status}."
                )
                messages.success(request, f"Reservation status updated to {new_status}.")
        
        # Handle payment proof upload (for students only)
        elif 'payment_proof' in request.FILES and request.user == self.object.student:
            payment_proof = request.FILES['payment_proof']
            self.object.payment_proof = payment_proof
            self.object.status = 'pending'
            self.object.payment_submitted_at = timezone.now()
            self.object.save()
            
            # Create a system message about the payment submission
            ReservationMessage.objects.create(
                reservation=self.object,
                sender=request.user,
                content="Payment proof has been submitted."
            )
            messages.success(request, "Payment proof uploaded successfully!")
        
        return redirect('dormitory:reservation_detail', pk=self.object.pk)

@login_required
@require_POST
def send_reservation_message(request, reservation_id):
    """Handle sending messages for a reservation."""
    reservation = get_object_or_404(Reservation, id=reservation_id)
    
    # Check if user is allowed to send message (either student or landlord)
    if not (request.user == reservation.student or request.user == reservation.dorm.landlord):
        return JsonResponse({'error': 'Not authorized'}, status=403)
    
    # Get message content
    content = request.POST.get('content')
    if not content:
        return JsonResponse({'error': 'Message content is required'}, status=400)
    
    # Create the message
    message = ReservationMessage.objects.create(
        reservation=reservation,
        sender=request.user,
        content=content
    )
    
    # Return message data for JavaScript
    return JsonResponse({
        'status': 'success',
        'message': {
            'id': message.id,
            'content': message.content,
            'sender': message.sender.username,
            'timestamp': message.timestamp.strftime("%I:%M %p"),
            'is_sender': True
        }
    })

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
        Message.objects.create(sender=sender, receiver=receiver, content=content)
        return redirect('dormitory:chat')

@method_decorator(login_required, name='dispatch')
class ReservationPaymentView(DetailView):
    model = Reservation
    template_name = 'dormitory/reservation_payment.html'
    context_object_name = 'reservation'
    pk_url_kwarg = 'reservation_id'

    def get_queryset(self):
        # Only allow access to reservations that belong to the current user
        return Reservation.objects.select_related('dorm').filter(student=self.request.user)

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
        return Reservation.objects.select_related('dorm', 'student').filter(
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
                selected_reservation = queryset.prefetch_related('messages').get(id=selected_reservation_id)
                context['selected_reservation'] = selected_reservation
            except Reservation.DoesNotExist:
                messages.error(self.request, "Selected reservation not found.")
        
        return context

@method_decorator(login_required, name='dispatch')
class UpdateReservationStatusView(View):
    def post(self, request, reservation_id):
        reservation = get_object_or_404(Reservation, id=reservation_id, dorm__landlord=request.user)
        action = request.POST.get('action')
        
        if action == 'confirm':
            reservation.status = 'confirmed'
            messages.success(request, f"Reservation for {reservation.dorm.name} has been confirmed.")
        elif action == 'decline':
            reservation.status = 'declined'
            messages.warning(request, f"Reservation for {reservation.dorm.name} has been declined.")
        elif action == 'complete':
            if reservation.status == 'confirmed':
                reservation.status = 'completed'
                messages.success(request, f"Transaction for {reservation.dorm.name} has been marked as complete.")
                
                # Create a system message about completion
                ReservationMessage.objects.create(
                    reservation=reservation,
                    sender=request.user,
                    content="Transaction has been marked as complete by the landlord."
                )
            else:
                messages.error(request, "Only confirmed reservations can be marked as complete.")
        
        reservation.save()
        return redirect('dormitory:landlord_reservations')

# Update the context processor to include pending reservations
def user_context(request):
    context = {}
    if request.user.is_authenticated:
        if request.user.user_type == 'student':
            context['user_pending_reservations'] = Reservation.objects.filter(
                student=request.user,
                status__in=['pending_payment', 'pending', 'confirmed']
            ).select_related('dorm').order_by('-created_at')
        elif request.user.user_type == 'landlord':
            context['pending_count'] = Reservation.objects.filter(
                dorm__landlord=request.user,
                status='pending'
            ).count()
    return context

@method_decorator(login_required, name='dispatch')
class StudentReservationsView(ListView):
    model = Reservation
    template_name = 'dormitory/student_reservations.html'
    context_object_name = 'reservations'

    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'student':
            messages.error(request, "Only students can access this page.")
            return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Reservation.objects.select_related('dorm').filter(
            student=self.request.user
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