from django.urls import reverse_lazy
from django.contrib.auth import login , logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, CreateView, FormView, UpdateView ,ListView
from django.views.generic.edit import UpdateView
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserCreationForm, AdminCreationForm
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from dormitory.models import Dorm, Review, Reservation
from django.views import View
from .models import Notification, CustomUser
from user_profile.models import UserProfile
from django.http import JsonResponse
from django.db.models import Avg, Count, F
from datetime import datetime
from django.db.models import FloatField
from django.db.models.functions import Cast
from django.db.models import ExpressionWrapper
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model


class RegisterView(CreateView):
    form_class = CustomUserCreationForm
    template_name = "accounts/register.html"

    def form_valid(self, form):
        """Log in user after successful registration, create profile, and redirect."""
        user = form.save()
        # ✅ Create a UserProfile with default image
        UserProfile.objects.create(user=user, profile_picture="profile_pictures/default.jpg")

        login(self.request, user)
        messages.success(self.request, f"Registration successful! Welcome, {user.username}")
        return redirect(self.get_success_url())

    def get_success_url(self):
        """Redirect users based on their type."""
        user = self.request.user
        if user.user_type == "Student":
            return reverse_lazy("accounts:student_dashboard")
        elif user.user_type == "Teacher":
            return reverse_lazy("accounts:teacher_dashboard")
        elif user.user_type == "Admin":
            return reverse_lazy("accounts:admin_dashboard")
        else:
            return reverse_lazy("accounts:dashboard")  # Default fallback

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
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.user_type == "admin":
            # Get pending dorms
            context["pending_dorms"] = Dorm.objects.filter(approval_status="pending")
            
            # Get user statistics
            User = get_user_model()
            
            context["total_users"] = User.objects.count()
            context["total_students"] = User.objects.filter(user_type="student").count()
            context["total_landlords"] = User.objects.filter(user_type="landlord").count()
            context["total_reviews"] = Review.objects.count()
            context["total_dorms"] = Dorm.objects.count()
            
            # Get active users (landlords and students)
            context["active_landlords"] = User.objects.filter(user_type="landlord", is_active=True)
            context["active_students"] = User.objects.filter(user_type="student", is_active=True)
            
        elif user.user_type == "student":
            # Get current week number for rotation
            week_num = datetime.now().isocalendar()[1]
            
            # Get student-specific seed if you want personalized rotation
            student_seed = user.id if hasattr(user, 'id') else 0
            
            # First get all approved dorms with their scores
            queryset = Dorm.objects.filter(
                approval_status="approved",
                available=True
            ).annotate(
                avg_rating=Avg('reviews__rating'),
                review_count=Count('reviews'),
                value_score=ExpressionWrapper(
                    F('avg_rating') * 0.7 + (1 - (Cast(F('price'), FloatField())/50000)) * 0.3,
                    output_field=FloatField()
                )
            ).order_by('-value_score', '-review_count')
            
            # Convert to list to enable slicing
            dorm_list = list(queryset)
            
            # Implement rotation logic
            rotation_group = (week_num + student_seed) % 3
            group_size = max(len(dorm_list) // 3, 1)  # Ensure at least 1
            start_index = rotation_group * group_size
            end_index = min(start_index + 12, len(dorm_list))  # Prevent overflow
            
            # Get the rotated slice
            context["dorms"] = dorm_list[start_index:end_index]
            
        elif user.user_type == 'landlord':
            # Get recent reservations for the landlord's dorms
            context['recent_reservations'] = Reservation.objects.select_related('dorm', 'student').filter(
                dorm__landlord=user
            ).order_by('-reservation_date')[:5]  # Show last 5 reservations
            
            # Get reservation statistics
            reservations = Reservation.objects.filter(dorm__landlord=user)
            context['pending_count'] = reservations.filter(status='pending').count()
            context['confirmed_count'] = reservations.filter(status='confirmed').count()
            context['declined_count'] = reservations.filter(status='declined').count()
        
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

class LogoutView(View):
    """Logs out the user and redirects to the login page."""
    
    def get(self, request, *args, **kwargs):
        logout(request)
        messages.success(request, "You have been logged out successfully.")
        return redirect("accounts:login")  # Adjust this to your login route

class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = "accounts/notifications.html"
    context_object_name = "notifications"

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by("-created_at").all()

class MarkNotificationAsReadView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({"success": True})

class CreateAdminView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = CustomUser
    template_name = 'accounts/create_admin.html'
    form_class = AdminCreationForm
    success_url = reverse_lazy('accounts:dashboard')

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'admin'

    def form_valid(self, form):
        user = form.save(commit=False)
        user.user_type = 'admin'
        user.is_staff = True
        user.is_superuser = True
        user.save()

        # Create UserProfile for the new admin
        UserProfile.objects.create(
            user=user,
            profile_picture="profile_pictures/default.jpg"
        )
        
        messages.success(self.request, 'New admin user created successfully!')
        return super().form_valid(form)

class ManageUsersView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'accounts/manage_users.html'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'admin'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['landlords'] = CustomUser.objects.filter(user_type='landlord')
        context['students'] = CustomUser.objects.filter(user_type='student')
        return context

class DeleteUserView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'admin'

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk)
        
        # Don't allow deleting yourself
        if user == request.user:
            messages.error(request, "You cannot delete your own account.")
            return redirect('accounts:manage_users')
        
        # Don't allow deleting other admins
        if user.user_type == 'admin':
            messages.error(request, "You cannot delete admin accounts.")
            return redirect('accounts:manage_users')
        
        # Delete associated data
        if user.user_type == 'landlord':
            # Delete all dorms owned by this landlord
            Dorm.objects.filter(landlord=user).delete()
        elif user.user_type == 'student':
            # Delete all reservations made by this student
            Reservation.objects.filter(student=user).delete()
            
        # Delete user profile
        if hasattr(user, 'userprofile'):
            user.userprofile.delete()
            
        # Delete notifications
        Notification.objects.filter(user=user).delete()
        
        # Delete the user
        username = user.username
        user.delete()
        
        messages.success(request, f"User {username} has been deleted successfully.")
        return redirect('accounts:manage_users')

class ToggleUserStatusView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'admin'

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk)
        user.is_active = not user.is_active
        user.save()
        
        action = "activated" if user.is_active else "deactivated"
        messages.success(request, f"User {user.username} has been {action}.")
        
        return redirect('accounts:manage_users')