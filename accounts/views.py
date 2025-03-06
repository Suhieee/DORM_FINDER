from django.urls import reverse_lazy
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, CreateView, FormView
from django.views.generic.edit import UpdateView
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from .forms import CustomUserCreationForm
from django.shortcuts import redirect
from django.contrib import messages
from dormitory.models import Dorm


# ✅ Register View (CBV)
class RegisterView(CreateView):
    form_class = CustomUserCreationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:dashboard")

    def form_valid(self, form):
        """Log in user after successful registration."""
        user = form.save()
        login(self.request, user)
        messages.success(self.request, f"Registration successful! Welcome, {user.username}")
        return super().form_valid(form)

    def form_invalid(self, form):
        """Handle errors if registration fails."""
        messages.error(self.request, "Registration failed. Please check the form.")
        return super().form_invalid(form)

# ✅ Login View (CBV)
class LoginView(FormView):
    form_class = AuthenticationForm
    template_name = "accounts/login.html"
    success_url = reverse_lazy("accounts:dashboard")

    def form_valid(self, form):
        """Log in the user after successful authentication."""
        user = form.get_user()
        login(self.request, user)
        messages.success(self.request, f"Welcome, {user.username}! You have successfully logged in.")
        return super().form_valid(form)

    def form_invalid(self, form):
        """Handle errors for invalid login attempts."""
        messages.error(self.request, "Invalid username or password. Please try again.")
        return super().form_invalid(form)

    def dispatch(self, request, *args, **kwargs):
        """Redirect already logged-in users to the dashboard."""
        if request.user.is_authenticated:
            messages.info(request, f"Welcome back, {request.user.username}! You are already logged in.")
            return redirect("accounts:dashboard")
        return super().dispatch(request, *args, **kwargs)

# ✅ Dashboard View (CBV)
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/dashboard.html"

    def get_template_names(self):
        """Return different dashboard templates based on user type."""
        user = self.request.user
        if user.user_type == "admin":
            return ["accounts/admin_dashboard.html"]
        elif user.user_type == "landlord":
            return ["accounts/landlord_dashboard.html"]
        else:
            return ["accounts/student_dashboard.html"]

    def get_context_data(self, **kwargs):
        """Pass additional context to templates based on user type."""
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.user_type == "admin":
            context["pending_dorms"] = Dorm.objects.filter(approval_status="pending")
        elif user.user_type == "student":
            context["dorms"] = Dorm.objects.filter(approval_status="approved", available=True)

        return context

# ✅ Approve Dorm View (CBV)
class ApproveDormView(LoginRequiredMixin, UpdateView):
    model = Dorm
    fields = ["approval_status"]
    success_url = reverse_lazy("accounts:dashboard")

    def dispatch(self, request, *args, **kwargs):
        """Ensure only admins can approve dorms."""
        if request.user.user_type != "admin":
            messages.error(request, "You are not authorized to approve dorms.")
            return redirect("accounts:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Approve the dorm."""
        dorm = form.save(commit=False)
        dorm.approval_status = "approved"
        dorm.save()
        messages.success(self.request, f"Dorm '{dorm.name}' has been approved.")
        return super().form_valid(form)

# ✅ Reject Dorm View (CBV)
class RejectDormView(LoginRequiredMixin, UpdateView):
    model = Dorm
    fields = ["approval_status", "available"]
    success_url = reverse_lazy("accounts:dashboard")

    def dispatch(self, request, *args, **kwargs):
        """Ensure only admins can reject dorms."""
        if request.user.user_type != "admin":
            messages.error(request, "You are not authorized to reject dorms.")
            return redirect("accounts:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Reject the dorm and mark it as unavailable."""
        dorm = form.save(commit=False)
        dorm.approval_status = "rejected"
        dorm.available = False
        dorm.save()
        messages.error(self.request, f"Dorm '{dorm.name}' has been rejected.")
        return super().form_valid(form)

# ✅ Review Dorm View (CBV)
class ReviewDormView(LoginRequiredMixin, UpdateView):
    model = Dorm
    fields = ["approval_status", "rejection_reason"]
    template_name = "accounts/review_dorm.html"
    success_url = reverse_lazy("accounts:dashboard")

    def dispatch(self, request, *args, **kwargs):
        """Ensure only admins can review dorms."""
        if request.user.user_type != "admin":
            messages.error(request, "You are not authorized to review dorms.")
            return redirect("accounts:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Handle dorm review."""
        dorm = form.save()
        if dorm.approval_status == "approved":
            messages.success(self.request, f"The dorm '{dorm.name}' has been approved.")
        elif dorm.approval_status == "rejected":
            messages.error(self.request, f"The dorm '{dorm.name}' has been rejected.")
        return super().form_valid(form)

class RoleBasedRedirectView(LoginRequiredMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        """Redirect users based on their role."""
        if request.user.is_superuser:
            return redirect("/admin/")
        elif request.user.user_type == "landlord":
            return redirect("accounts:dashboard")
        elif request.user.user_type == "student":
            return redirect("accounts:dashboard")
        else:
            return redirect("accounts:login")
