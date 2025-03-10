from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.urls import reverse_lazy
from .models import Dorm, DormImage , Amenity
from .forms import DormForm

# 🚀 Add Dorm (For Landlords)
class AddDormView(LoginRequiredMixin, CreateView):
    model = Dorm
    form_class = DormForm
    template_name = "dormitory/add_dorm.html"
    success_url = reverse_lazy("accounts:dashboard")  

    def form_valid(self, form):
        """Set the landlord before saving and handle multiple images."""
        if self.request.user.user_type != "landlord":
            return redirect("accounts:dashboard")  

        form.instance.landlord = self.request.user
        response = super().form_valid(form)

        images = self.request.FILES.getlist('images')  # Get multiple images
        for image in images:
            DormImage.objects.create(dorm=self.object, image=image)

        messages.success(self.request, "Dorm successfully created!")
        return response

    def get_context_data(self, **kwargs):
        """Pass amenities to the template context."""
        context = super().get_context_data(**kwargs)
        context['amenities'] = Amenity.objects.all()  # Pass all amenities to the template
        return context


# 🚀 List of Dorms (For Students)
# 🚀 Dorm List
class DormListView(LoginRequiredMixin, ListView):
    model = Dorm
    template_name = "dormitory/dorm_list.html"
    context_object_name = "dorms"

    def get_queryset(self):
        """Only show available & approved dorms."""
        return Dorm.objects.filter(available=True, approval_status="approved")


# 🚀 Dorm Details
class DormDetailView(LoginRequiredMixin, DetailView):
    model = Dorm
    template_name = "dormitory/dorm_detail.html"
    context_object_name = "dorm"

    # Pass additional context for amenities
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['amenities'] = self.object.amenities.all()  # Get amenities for this dorm
        return context



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


# 🚀 Edit Dorm (For Landlords)
class EditDormView(LoginRequiredMixin, UpdateView):
    model = Dorm
    form_class = DormForm
    template_name = "dormitory/edit_dorm.html"

    def get_queryset(self):
        """Ensure only the landlord can edit their dorms."""
        return Dorm.objects.filter(landlord=self.request.user)

    def form_valid(self, form):
        dorm = form.save()
        images = self.request.FILES.getlist('images')  # Get new images

        # Handle image deletion
        for image in dorm.images.all():
            if self.request.POST.get(f'delete_image_{image.id}'):
                image.delete()

        # Save new images
        for image in images:
            DormImage.objects.create(dorm=dorm, image=image)

        # Handle amenities selection
        amenities = self.request.POST.getlist('amenities')
        dorm.amenities.set(amenities)

        messages.success(self.request, "Dorm successfully updated!")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dorm'] = self.get_object()  # Pass dorm to template for existing images
        context['all_amenities'] = Amenity.objects.all()  # Pass all amenities to template
        return context

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