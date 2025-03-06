from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.urls import reverse_lazy
from .models import Dorm
from .forms import DormForm

# 🚀 Add Dorm (For Landlords)
class AddDormView(LoginRequiredMixin, CreateView):
    model = Dorm
    form_class = DormForm
    template_name = "dormitory/add_dorm.html"
    success_url = reverse_lazy("accounts:dashboard")  # Redirect after success

    def form_valid(self, form):
        """Set the landlord before saving."""
        if self.request.user.user_type != "landlord":
            return redirect("accounts:dashboard")  # Restrict to landlords
        
        form.instance.landlord = self.request.user
        messages.success(self.request, "Dorm successfully created!")
        return super().form_valid(form)


# 🚀 List of Dorms (For Students)
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
        messages.success(self.request, "Dorm successfully updated!")
        return super().form_valid(form)

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
