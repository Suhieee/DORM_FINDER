from django.urls import reverse_lazy
from django.contrib.auth import login , logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, CreateView, FormView, UpdateView ,ListView
from django.views.generic.edit import UpdateView
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserCreationForm, AdminCreationForm, UserReportForm, BanUserForm, ResolveReportForm
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from dormitory.models import Dorm, Review, Reservation, Message
from django.views import View
from .models import Notification, CustomUser, UserReport
from user_profile.models import UserProfile, UserInteraction
from django.http import JsonResponse, HttpResponse
from django.db.models import Avg, Count, F, Q, ExpressionWrapper, FloatField, Value
from django.db.models.functions import Cast, Coalesce, Round
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Case, When
from django.core.mail import send_mail
from django.conf import settings
import secrets
from django.template.loader import render_to_string
import numpy as np
from sklearn.neighbors import NearestNeighbors
from django.core.paginator import Paginator
import json
from django.utils import timezone
from django.db.models.functions import TruncMonth
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Count, Q, DecimalField
import logging


class RegisterView(CreateView):
    form_class = CustomUserCreationForm
    template_name = "accounts/register.html"

    def form_valid(self, form):
        """Log in user after successful registration, create profile, and redirect."""
        user = form.save()
        # Ensure a UserProfile exists (signals also handle this; this is idempotent)
        token = secrets.token_urlsafe(32)
        now = timezone.now()
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                "profile_picture": "profile_pictures/default.jpg",
                "verification_token": token,
                "verification_token_created_at": now,
            },
        )
        # Update token and timestamp if profile already exists
        if not _:
            profile.verification_token = token
            profile.verification_token_created_at = now
            profile.save()

        # Send verification email (with proper error handling)
        try:
            from django.urls import reverse
            # Use SITE_URL from settings if available (for production), otherwise use request
            if settings.SITE_URL:
                verification_path = reverse('accounts:verify_email', kwargs={'token': token})
                verification_url = settings.SITE_URL.rstrip('/') + verification_path
            else:
                verification_path = reverse('accounts:verify_email', kwargs={'token': token})
                verification_url = self.request.build_absolute_uri(verification_path)
            
            html_message = render_to_string('email/verify_email.html', {
                'user': user,
                'verification_url': verification_url,
                'year': datetime.now().year,
            })
            
            logger = logging.getLogger(__name__)
            
            # Check if email settings are configured
            if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
                logger.error(f'Email not configured. EMAIL_HOST_USER={bool(settings.EMAIL_HOST_USER)}, EMAIL_HOST_PASSWORD={bool(settings.EMAIL_HOST_PASSWORD)}')
                messages.warning(self.request, 'Registration successful, but email verification could not be sent. Please use resend verification.')
            else:
                logger.info(f'Attempting to send verification email to {user.email} from {settings.DEFAULT_FROM_EMAIL}')
                # Send email with fail_silently=True to prevent crashes, but log errors
                try:
                    result = send_mail(
                        'Verify your email address',
                        '',  # plain text fallback (optional)
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                        fail_silently=True,  # Don't crash if email fails
                        html_message=html_message,
                    )
                    if result:
                        logger.info(f'✅ Verification email sent successfully to {user.email}')
                    else:
                        logger.warning(f'⚠️ Email send returned False for {user.email}')
                        messages.warning(self.request, 'Registration successful, but email verification could not be sent. Please use resend verification.')
                except Exception as email_error:
                    logger.error(f'❌ Email send failed for {user.email}: {str(email_error)}', exc_info=True)
                    messages.warning(self.request, 'Registration successful, but email verification could not be sent. Please use resend verification.')
        except Exception as e:
            # Log error but don't block registration
            logger = logging.getLogger(__name__)
            logger.error(f'Failed to send verification email to {user.email}: {str(e)}', exc_info=True)
            messages.warning(self.request, 'Registration successful, but email verification could not be sent. Please use resend verification.')

        login(self.request, user)
        messages.success(self.request, f"Registration successful! Welcome, {user.username}. Please check your email to verify your account.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        """Redirect to next parameter if provided, otherwise based on user type."""
        next_url = self.request.GET.get('next')
        if next_url and next_url.startswith('/'):
            return next_url
        
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

    def get_success_url(self):
        """Redirect to next parameter if provided, otherwise to dashboard."""
        next_url = self.request.GET.get('next')
        if next_url and next_url.startswith('/'):
            return next_url
        return super().get_success_url()

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

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points using Haversine formula."""
        R = 6371  # Earth's radius in kilometers

        lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Add verification status for all dashboards
        try:
            user_profile = UserProfile.objects.get(user=user)
            context['is_verified'] = user_profile.is_verified
        except UserProfile.DoesNotExist:
            context['is_verified'] = False

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

            # Dynamic chart data for analytics
            # Monthly user registrations (last 12 months)
            now = timezone.now()
            months = [((now - timezone.timedelta(days=30*i)).strftime('%b %Y')) for i in reversed(range(12))]
            user_months = User.objects.annotate(month=TruncMonth('date_joined')).values('month').annotate(count=Count('id')).order_by('month')
            dorm_months = Dorm.objects.annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('id')).order_by('month')
            # Dorm approval rates
            dorm_approved = Dorm.objects.filter(approval_status='approved').annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('id')).order_by('month')
            dorm_rejected = Dorm.objects.filter(approval_status='rejected').annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('id')).order_by('month')
            dorm_approved_dict = {d['month'].strftime('%b %Y'): d['count'] for d in dorm_approved}
            dorm_rejected_dict = {d['month'].strftime('%b %Y'): d['count'] for d in dorm_rejected}
            dorm_approved_counts = [dorm_approved_dict.get(m, 0) for m in months]
            dorm_rejected_counts = [dorm_rejected_dict.get(m, 0) for m in months]
            # Active vs Inactive users
            active_users = User.objects.filter(is_active=True).count()
            inactive_users = User.objects.filter(is_active=False).count()
            # Build dicts for quick lookup
            user_month_dict = {u['month'].strftime('%b %Y'): u['count'] for u in user_months}
            dorm_month_dict = {d['month'].strftime('%b %Y'): d['count'] for d in dorm_months}
            user_counts = [user_month_dict.get(m, 0) for m in months]
            dorm_counts = [dorm_month_dict.get(m, 0) for m in months]
            context['chart_labels'] = json.dumps(months)
            context['chart_user_counts'] = json.dumps(user_counts)
            context['chart_dorm_counts'] = json.dumps(dorm_counts)
            context['dorm_approved_counts'] = json.dumps(dorm_approved_counts)
            context['dorm_rejected_counts'] = json.dumps(dorm_rejected_counts)
            context['active_users'] = active_users
            context['inactive_users'] = inactive_users
            
        elif user.user_type == "student":
            user_profile = UserProfile.objects.get(user=user)
            favorite_dorms = user_profile.favorite_dorms.all()
            recent_views = UserInteraction.objects.filter(user=user, interaction_type='view').order_by('-timestamp')[:10]
            viewed_dorms = Dorm.objects.filter(id__in=recent_views.values_list('dorm_id', flat=True))

            # --- Prepare base queryset and dorm list ---
            base_queryset = Dorm.objects.filter(approval_status="approved", available=True).annotate(
                avg_rating=Coalesce(Avg('reviews__rating'), 0.0),
                review_count=Count('reviews'),
                amenity_count=Count('amenities'),
            ).annotate(
                avg_rating_rounded=Case(
                    When(avg_rating__isnull=True, then=Value(0.0)),
                    default=ExpressionWrapper(Round(F('avg_rating')), output_field=FloatField()),
                    output_field=FloatField()
                )
            )
            dorms = list(base_queryset)

            # --- Popular Dorms Logic ---
            popular_dorms = (
                Dorm.objects.filter(approval_status="approved", available=True)
                .annotate(
                    avg_rating=Coalesce(Avg('reviews__rating'), 0.0),
                    review_count=Count('reviews'),
                )
                .annotate(
                    avg_rating_rounded=Case(
                        When(avg_rating__isnull=True, then=Value(0.0)),
                        default=ExpressionWrapper(Round(F('avg_rating')), output_field=FloatField()),
                        output_field=FloatField()
                    )
                )
                .order_by('-recent_views', '-avg_rating')[:6]
            )
            context['popular_dorms'] = popular_dorms

            # --- Collaborative Filtering Logic ---
            user_favorites = set(user_profile.favorite_dorms.values_list('id', flat=True))
            similar_users = UserProfile.objects.filter(
                favorite_dorms__in=user_favorites
            ).exclude(user=user).distinct()
            collab_dorms = Dorm.objects.filter(
                favorited_by__in=similar_users
            ).exclude(
                id__in=user_favorites
            ).annotate(
                num_similar_favorites=Count('favorited_by')
            ).order_by('-num_similar_favorites', '-reviews__rating')[:12]
            collab_dorm_ids = set(collab_dorms.values_list('id', flat=True))

            # --- Prepare dorm features for ML ---
            dorm_features = []
            for dorm in dorms:
                dorm_features.append([
                    float(dorm.price),
                    float(getattr(dorm, 'avg_rating', dorm.get_average_rating())),
                    dorm.amenity_count,
                    float(dorm.latitude or 0),
                    float(dorm.longitude or 0),
                ])
            dorm_features = np.array(dorm_features)

            # --- ML: Find similar dorms to favorites/views ---
            if favorite_dorms.exists():
                user_pref_indices = [i for i, d in enumerate(dorms) if d in favorite_dorms]
            else:
                user_pref_indices = [i for i, d in enumerate(dorms) if d in viewed_dorms]
            if user_pref_indices:
                user_pref_features = dorm_features[user_pref_indices]
                n_neighbors = min(6, len(dorms))
                nn = NearestNeighbors(n_neighbors=n_neighbors, metric='euclidean')
                nn.fit(dorm_features)
                user_vector = np.mean(user_pref_features, axis=0).reshape(1, -1)
                distances, indices = nn.kneighbors(user_vector)
                ml_recommended_indices = indices[0]
            else:
                ml_recommended_indices = []

            # --- Calculate distance score if student has a school ---
            if hasattr(user, 'school') and user.school and user.school.latitude and user.school.longitude:
                for dorm in dorms:
                    distance = self.calculate_distance(
                        user.school.latitude, 
                        user.school.longitude,
                        dorm.latitude, 
                        dorm.longitude
                    )
                    dorm.distance_score = max(0, 1 - (distance / 10))  # 10km as max ideal distance
            else:
                for dorm in dorms:
                    dorm.distance_score = 0.5  # Neutral score if no school set

            # --- Rule-based + ML scoring and explanations ---
            scored_dorms = []
            for i, dorm in enumerate(dorms):
                final_score = (
                    float(getattr(dorm, 'avg_rating', dorm.get_average_rating())) * 0.25 +
                    dorm.distance_score * 0.25 +
                    (dorm.amenity_count / 10) * 0.25 +
                    float(getattr(dorm, 'review_count', 0)) * 0.05 +
                    float(dorm.price) * -0.00001
                )
                ml_bonus = 0.2 if i in ml_recommended_indices else 0
                collab_bonus = 0.2 if dorm.id in collab_dorm_ids else 0
                total_score = final_score + ml_bonus + collab_bonus

                # --- Explanation logic ---
                reasons = []
                if i in ml_recommended_indices:
                    reasons.append("Similar to your favorites/views")
                if dorm.id in collab_dorm_ids:
                    reasons.append("Liked by students with similar taste")
                if getattr(dorm, 'avg_rating', dorm.get_average_rating()) >= 4.5:
                    reasons.append("Highly rated by students")
                if dorm.distance_score >= 0.8:
                    reasons.append("Very close to your school")
                if dorm.amenity_count >= 7:
                    reasons.append("Has many amenities")
                if getattr(dorm, 'review_count', 0) >= 10:
                    reasons.append("Popular among students")
                explanation = " and ".join(reasons[:2]) if reasons else "Recommended for you"

                scored_dorms.append((dorm, total_score, explanation))

            # --- Sort and split as before, but keep explanations ---
            scored_dorms.sort(key=lambda x: x[1], reverse=True)
            regular_dorms = [(d, e) for d, s, e in scored_dorms if d.accommodation_type == 'whole_unit'][:6]
            bedspace_dorms = [(d, e) for d, s, e in scored_dorms if d.accommodation_type in ['bedspace', 'room_sharing']][:6]

            context.update({
                "dorms": regular_dorms,
                "bedspace_dorms": bedspace_dorms,
            })
            
        elif user.user_type == 'landlord':
            # Recent reservations
            context['recent_reservations'] = Reservation.objects.select_related('dorm', 'student').filter(
                dorm__landlord=user
            ).order_by('-reservation_date')[:5]

            # Core collections
            landlord_dorms = Dorm.objects.filter(landlord=user)
            reservations = Reservation.objects.select_related('dorm', 'student').filter(dorm__landlord=user)
            messages_qs = Message.objects.select_related('sender', 'receiver', 'dorm', 'reservation').filter(dorm__landlord=user)

            # Top-line stats
            context['total_dorms'] = landlord_dorms.count()
            context['total_inquiries'] = messages_qs.count()
            context['total_reservations'] = reservations.count()
            context['total_views'] = landlord_dorms.aggregate(total=Coalesce(Sum('recent_views'), 0))['total']

            # Reservations breakdown
            context['pending_count'] = reservations.filter(status='pending').count()
            context['confirmed_count'] = reservations.filter(status='confirmed').count()
            context['declined_count'] = reservations.filter(status='declined').count()
            context['completed_count'] = reservations.filter(status='completed').count()

            # Unread messages for bell indicator
            context['unread_messages_count'] = messages_qs.filter(receiver=user, is_read=False).count()

            # Recent inquiries/messages
            context['recent_inquiries'] = messages_qs.order_by('-timestamp')[:5]

            # Sales metrics
            now = timezone.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_sales = reservations.filter(
                created_at__gte=month_start,
                has_paid_reservation=True
            ).aggregate(total=Coalesce(Sum('payment_amount'), Value(0), output_field=DecimalField(max_digits=10, decimal_places=2)))['total']
            total_income = reservations.filter(
                has_paid_reservation=True
            ).aggregate(total=Coalesce(Sum('payment_amount'), Value(0), output_field=DecimalField(max_digits=10, decimal_places=2)))['total']

            context['monthly_sales'] = monthly_sales or 0
            context['total_income'] = total_income or 0

            # Popularity: most viewed dorm and top list
            popular_dorm = landlord_dorms.order_by('-recent_views').first()
            context['popular_dorm'] = popular_dorm
            context['top_dorms_by_views'] = landlord_dorms.order_by('-recent_views').values(
                'id', 'name', 'recent_views'
            )[:5]

            # Monthly reservations (last 6 months)
            last_six_months = Reservation.objects.filter(dorm__landlord=user).annotate(
                month=TruncMonth('created_at')
            ).values('month').annotate(count=Count('id')).order_by('month')

            reservations_chart = []
            for entry in last_six_months:
                label = entry['month'].strftime('%b %Y') if entry['month'] else ''
                reservations_chart.append({'label': label, 'value': entry['count']})
            context['reservations_chart'] = reservations_chart
        
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

        # Ensure UserProfile exists for the new admin (idempotent with signals)
        UserProfile.objects.get_or_create(
            user=user,
            defaults={"profile_picture": "profile_pictures/default.jpg"}
        )
        
        messages.success(self.request, 'New admin user created successfully!')
        return super().form_valid(form)

class ManageUsersView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'accounts/manage_users.html'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'admin'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['users'] = CustomUser.objects.all().order_by('user_type', 'username')
        context['user_roles'] = CustomUser.USER_TYPES
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
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        # Toggle status
        if user.is_active:
            # Banning: require reason
            ban_reason = request.POST.get('ban_reason', '').strip()
            if not ban_reason:
                if is_ajax:
                    return JsonResponse({'error': 'Ban reason is required.'}, status=400)
                messages.error(request, 'Ban reason is required.')
                return redirect('accounts:manage_users')
            user.is_active = False
            user.ban_reason = ban_reason
        else:
            # Unbanning: clear reason
            user.is_active = True
            user.ban_reason = ''
        user.save()
        action = "activated" if user.is_active else "deactivated"
        if is_ajax:
            return JsonResponse({'success': True, 'action': action, 'ban_reason': user.ban_reason})
        messages.success(request, f"User {user.username} has been {action}.")
        return redirect('accounts:manage_users')

class UpdateUserRoleView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'admin'

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk)
        new_role = request.POST.get('new_role')
        valid_roles = [choice[0] for choice in CustomUser.USER_TYPES]

        if new_role not in valid_roles:
            messages.error(request, "Invalid role selected.")
            return redirect('accounts:manage_users')

        if user == request.user and new_role != 'admin':
            messages.error(request, "You cannot change your own role.")
            return redirect('accounts:manage_users')

        # Update role and privilege flags
        user.user_type = new_role
        if new_role == 'admin':
            user.is_staff = True
            user.is_superuser = True
        else:
            user.is_staff = False
            user.is_superuser = False

        user.save()
        messages.success(request, f"{user.username}'s role has been updated to {user.get_user_type_display()}.")
        return redirect('accounts:manage_users')

class VerifyEmailView(View):
    def get(self, request, token):
        try:
            profile = UserProfile.objects.get(verification_token=token)
            
            # Check if already verified
            if profile.is_verified:
                messages.info(request, 'Your email is already verified!')
                return redirect('accounts:login')
            
            # Check if token has expired (48 hours)
            if profile.verification_token_created_at:
                expiration_time = profile.verification_token_created_at + timedelta(hours=48)
                if timezone.now() > expiration_time:
                    # Token expired
                    profile.verification_token = None
                    profile.verification_token_created_at = None
                    profile.save()
                    messages.error(request, 'This verification link has expired. Please request a new verification email.')
                    return redirect('accounts:resend_verification')
            
            # Token is valid, verify the email
            profile.is_verified = True
            profile.verification_token = None
            profile.verification_token_created_at = None
            profile.save()
            messages.success(request, 'Your email has been verified!')
            return redirect('accounts:login')
        except UserProfile.DoesNotExist:
            messages.error(request, 'Invalid verification link. The link may have already been used or expired.')
            return redirect('accounts:resend_verification')

def send_verification_email(request, user):
    """Helper function to send verification email to a user."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        
        # Check if already verified
        if profile.is_verified:
            logger.info(f'Email verification skipped for {user.email}: already verified')
            return False, 'Your email is already verified!'
        
        # Generate new token
        token = secrets.token_urlsafe(32)
        now = timezone.now()
        profile.verification_token = token
        profile.verification_token_created_at = now
        profile.save()
        
        # Send verification email
        from django.urls import reverse
        # Use SITE_URL from settings if available (for production), otherwise use request
        if settings.SITE_URL:
            verification_path = reverse('accounts:verify_email', kwargs={'token': token})
            verification_url = settings.SITE_URL.rstrip('/') + verification_path
            logger.info(f'Using SITE_URL from settings: {verification_url}')
        else:
            verification_path = reverse('accounts:verify_email', kwargs={'token': token})
            verification_url = request.build_absolute_uri(verification_path)
            logger.info(f'Using request.build_absolute_uri: {verification_url}')
        
        # Check if email settings are configured
        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            logger.error(
                f'Email not configured. EMAIL_HOST_USER={bool(settings.EMAIL_HOST_USER)}, '
                f'EMAIL_HOST_PASSWORD={bool(settings.EMAIL_HOST_PASSWORD)}'
            )
            return False, 'Email service is not configured. Please contact support.'
        
        html_message = render_to_string('email/verify_email.html', {
            'user': user,
            'verification_url': verification_url,
            'year': datetime.now().year,
        })
        
        logger.info(f'Attempting to send verification email to {user.email} from {settings.DEFAULT_FROM_EMAIL}')
        result = send_mail(
            'Verify your email address',
            '',  # plain text fallback
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,  # Changed to True to prevent crashes
            html_message=html_message,
        )
        
        if result:
            logger.info(f'✅ Verification email sent successfully to {user.email}')
            return True, 'A new verification email has been sent to your email address. Please check your inbox.'
        else:
            logger.warning(f'⚠️ Email send returned False for {user.email}')
            return False, 'Failed to send verification email. Please try again later.'
        
    except Exception as e:
        logger.error(f'❌ Error sending verification email to {user.email}: {str(e)}', exc_info=True)
        return False, f'An error occurred while sending the verification email: {str(e)}'

class ResendVerificationEmailLoggedInView(LoginRequiredMixin, View):
    """Simple view for logged-in users to resend verification email."""
    
    def post(self, request):
        """Resend verification email for logged-in user."""
        success, message = send_verification_email(request, request.user)
        
        if success:
            messages.success(request, message)
        else:
            messages.info(request, message)
        
        # Redirect back to profile or dashboard
        next_url = request.GET.get('next', 'user_profile:profile')
        return redirect(next_url)
    
    def get(self, request):
        """Handle GET request by redirecting to POST."""
        return self.post(request)

class ResendVerificationEmailView(FormView):
    """View to resend verification email to users (for logged-out users)."""
    template_name = 'accounts/resend_verification.html'
    form_class = AuthenticationForm
    
    def dispatch(self, request, *args, **kwargs):
        # If user is already logged in, redirect to the logged-in version
        if request.user.is_authenticated:
            success, message = send_verification_email(request, request.user)
            if success:
                messages.success(request, message)
            else:
                messages.info(request, message)
            return redirect('user_profile:profile')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Resend verification email if user is not verified."""
        user = form.get_user()
        success, message = send_verification_email(self.request, user)
        
        if success:
            messages.success(self.request, message)
            return redirect('accounts:login')
        else:
            messages.info(self.request, message)
            return redirect('accounts:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Resend Verification Email'
        return context

class TransactionLogView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'accounts/transaction_log.html'

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'admin'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        transactions = Reservation.objects.select_related('dorm', 'student').order_by('-created_at')
        paginator = Paginator(transactions, 25)  # 25 per page
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        context['page_obj'] = page_obj
        return context

class ViewUserProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/view_user_profile.html'
    
    def get_template_names(self):
        user_id = self.kwargs.get('user_id')
        profile_user = get_object_or_404(CustomUser, id=user_id)
        if profile_user.user_type == 'landlord':
            return ['accounts/view_landlord_profile.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = self.kwargs.get('user_id')
        profile_user = get_object_or_404(CustomUser, id=user_id)
        
        # Get user profile
        try:
            user_profile = UserProfile.objects.get(user=profile_user)
        except UserProfile.DoesNotExist:
            user_profile = None
        
        # Get user's dorms if landlord
        user_dorms = []
        if profile_user.user_type == 'landlord':
            user_dorms = Dorm.objects.filter(landlord=profile_user, approval_status='approved')[:5]
        
        # Get user's reviews if student
        user_reviews = []
        if profile_user.user_type == 'student':
            user_reviews = Review.objects.filter(user=profile_user)[:5]
        
        # Get user's reservations
        user_reservations = Reservation.objects.filter(student=profile_user)[:5]
        
        # Add the report form for the modal
        report_form = UserReportForm()
        
        context.update({
            'profile_user': profile_user,
            'user_profile': user_profile,
            'user_dorms': user_dorms,
            'user_reviews': user_reviews,
            'user_reservations': user_reservations,
            'can_report': self.request.user != profile_user and not profile_user.user_type == 'admin',
            'report_form': report_form,
        })
        return context

class ReportUserView(LoginRequiredMixin, CreateView):
    model = UserReport
    form_class = UserReportForm
    template_name = 'accounts/report_user.html'
    success_url = reverse_lazy('accounts:dashboard')
    
    def dispatch(self, request, *args, **kwargs):
        reported_user_id = self.kwargs.get('user_id')
        reported_user = get_object_or_404(CustomUser, id=reported_user_id)
        # Prevent self-reporting
        if request.user == reported_user:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'You cannot report yourself.'}, status=400)
            messages.error(request, "You cannot report yourself.")
            return redirect('accounts:dashboard')
        # Prevent reporting admins
        if reported_user.user_type == 'admin':
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'You cannot report admin users.'}, status=400)
            messages.error(request, "You cannot report admin users.")
            return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        reported_user_id = self.kwargs.get('user_id')
        reported_user = get_object_or_404(CustomUser, id=reported_user_id)
        report = form.save(commit=False)
        report.reporter = self.request.user
        report.reported_user = reported_user
        report.save()
        # Notify admins about the report
        admins = CustomUser.objects.filter(user_type='admin')
        for admin in admins:
            Notification.objects.create(
                user=admin,
                message=f"New report received: {self.request.user.username} reported {reported_user.username} for {report.get_reason_display()}",
                related_object_id=report.id
            )
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Report submitted successfully. Admins will review your report.'})
        messages.success(self.request, f"Report submitted successfully. Admins will review your report.")
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            errors = {field: [str(e) for e in errs] for field, errs in form.errors.items()}
            return JsonResponse({'success': False, 'errors': errors}, status=400)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reported_user_id = self.kwargs.get('user_id')
        reported_user = get_object_or_404(CustomUser, id=reported_user_id)
        context['reported_user'] = reported_user
        return context

class ManageReportsView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = UserReport
    template_name = 'accounts/manage_reports.html'
    context_object_name = 'reports'
    paginate_by = 20
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'admin'
    
    def get_queryset(self):
        status_filter = self.request.GET.get('status', '')
        queryset = UserReport.objects.select_related('reporter', 'reported_user', 'resolved_by').all()
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset

class ReportDetailView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'accounts/report_detail.html'
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'admin'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report_id = self.kwargs.get('report_id')
        report = get_object_or_404(UserReport, id=report_id)
        
        # Get additional context about the reported user
        reported_user = report.reported_user
        user_dorms = []
        user_reviews = []
        
        if reported_user.user_type == 'landlord':
            user_dorms = Dorm.objects.filter(landlord=reported_user)[:10]
        elif reported_user.user_type == 'student':
            user_reviews = Review.objects.filter(user=reported_user)[:10]
        
        context.update({
            'report': report,
            'user_dorms': user_dorms,
            'user_reviews': user_reviews,
            'resolve_form': ResolveReportForm(),
        })
        return context

@method_decorator(login_required, name='dispatch')
class ResolveReportView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'admin'
    
    def post(self, request, report_id):
        report = get_object_or_404(UserReport, id=report_id)
        form = ResolveReportForm(request.POST)
        
        if form.is_valid():
            action = form.cleaned_data['action']
            notes = form.cleaned_data['notes']
            
            if action == 'dismiss':
                report.status = 'dismissed'
                report.resolved_by = request.user
                report.resolved_at = timezone.now()
                report.admin_notes = f"Report dismissed.\nNotes: {notes}"
                report.save()
                messages.success(request, "Report dismissed successfully.")
            
            elif action.startswith('ban_'):
                # Ban the reported user
                reported_user = report.reported_user
                ban_type = action.split('_')[1]
                
                if ban_type == 'minor':
                    duration = timedelta(days=1)
                    severity = 'minor'
                elif ban_type == 'moderate':
                    duration = timedelta(days=7)
                    severity = 'moderate'
                elif ban_type == 'major':
                    duration = timedelta(days=30)
                    severity = 'major'
                elif ban_type == 'permanent':
                    duration = None
                    severity = 'permanent'
                
                reported_user.is_active = False
                reported_user.ban_reason = f"Banned due to report: {report.get_reason_display()}. {notes}"
                reported_user.ban_severity = severity
                if duration:
                    reported_user.ban_expires_at = timezone.now() + duration
                else:
                    reported_user.ban_expires_at = None
                reported_user.save()
                
                # Resolve the report
                report.resolve(request.user, f"User banned ({ban_type})", notes)
                
                messages.success(request, f"User {reported_user.username} has been banned ({ban_type}).")
            
            elif action == 'warn':
                # Send warning notification to the reported user
                Notification.objects.create(
                    user=report.reported_user,
                    message=f"Warning: You have been reported for {report.get_reason_display()}. Please review your behavior. {notes}"
                )
                
                # Resolve the report
                report.resolve(request.user, "User warned", notes)
                
                messages.success(request, f"Warning sent to {report.reported_user.username}.")
        
        return redirect('accounts:report_detail', report_id=report_id)

class EnhancedToggleUserStatusView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'admin'

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk)
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        
        if user.is_active:
            # Banning: use the new form
            form = BanUserForm(request.POST)
            if form.is_valid():
                ban_duration = form.get_ban_duration()
                ban_reason = form.cleaned_data['ban_reason']
                ban_severity = form.cleaned_data['ban_severity']
                
                user.is_active = False
                user.ban_reason = ban_reason
                user.ban_severity = ban_severity
                if ban_duration:
                    user.ban_expires_at = timezone.now() + ban_duration
                else:
                    user.ban_expires_at = None  # Permanent ban
                user.save()
                
                action = "banned"
                if is_ajax:
                    return JsonResponse({
                        'success': True, 
                        'action': action, 
                        'ban_reason': user.ban_reason,
                        'ban_expires_at': user.ban_expires_at.isoformat() if user.ban_expires_at else None,
                        'ban_severity': user.ban_severity
                    })
                messages.success(request, f"User {user.username} has been banned ({ban_severity}).")
            else:
                if is_ajax:
                    return JsonResponse({'error': 'Invalid form data.'}, status=400)
                messages.error(request, 'Please provide valid ban information.')
        else:
            # Unbanning: clear all ban-related fields
            user.is_active = True
            user.ban_reason = ''
            user.ban_severity = None
            user.ban_expires_at = None
            user.save()
            
            action = "unbanned"
            if is_ajax:
                return JsonResponse({'success': True, 'action': action})
            messages.success(request, f"User {user.username} has been unbanned.")
        
        return redirect('accounts:manage_users')