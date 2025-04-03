from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin , UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.urls import reverse_lazy
from .models import Dorm, DormImage , Amenity ,  RoommatePost , Review
from .forms import DormForm ,  RoommatePostForm , ReviewForm
from django.db.models import Avg
from django.db import transaction





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

    def get_queryset(self):
        """Only show available & approved dorms."""
        return Dorm.objects.filter(available=True, approval_status="approved").annotate(avg_rating=Avg("reviews__rating"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass dorm locations to the template
        context["dorm_locations"] = list(Dorm.objects.filter(available=True, approval_status="approved").values("id", "latitude", "longitude", "name"))
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


# 🚀 Landlord’s Dorms (My Dorms)
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
class ReviewCreateView(CreateView):
    model = Review
    form_class = ReviewForm
    template_name = "dormitory/add_review.html"

    def form_valid(self, form):
        """Assign the user and dorm before saving."""
        dorm = get_object_or_404(Dorm, id=self.kwargs["dorm_id"])
        form.instance.dorm = dorm
        form.instance.user = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Review added successfully!")  # Fixed message
        return response

    def get_success_url(self):
        """Redirect to the dorm's review list after submission."""
        return reverse_lazy("dormitory:review_list", kwargs={"dorm_id": self.kwargs["dorm_id"]})

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
        """Redirect back to the dorm detail page after deletion."""
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
        return reverse_lazy("dormitory:dorm_detail", kwargs={"pk": self.object.dorm.id})  # ✅ Redirect to dorm detail
    
