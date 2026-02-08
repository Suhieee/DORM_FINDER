from django.urls import reverse_lazy
from django.contrib.auth import login , logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, CreateView, FormView, UpdateView ,ListView
from django.views.generic.edit import UpdateView
from django.contrib.auth.forms import AuthenticationForm
from .forms import (
    CustomUserCreationForm, AdminCreationForm, UserReportForm, BanUserForm, 
    ResolveReportForm, IdentityVerificationForm, VerificationReviewForm,
    TenantRegistrationForm, LandlordRegistrationForm
)
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib import messages
from dormitory.models import Dorm, Review, Reservation, Message, TransactionLog
from django.views import View
from .models import Notification, CustomUser, UserReport
from user_profile.models import UserProfile, UserInteraction, TenantPreferences
from user_profile.forms import TenantPreferencesForm
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
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited


class RegisterChoiceView(TemplateView):
    """View to let users choose between tenant or landlord registration"""
    template_name = "accounts/register_choice.html"


class TenantRegisterView(CreateView):
    """Registration view specifically for tenants"""
    form_class = TenantRegistrationForm
    template_name = "accounts/tenant_register.html"

    def form_valid(self, form):
        """Log in user after successful registration and redirect to preferences setup"""
        user = form.save()
        # Create user profile
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
        if not _:
            profile.verification_token = token
            profile.verification_token_created_at = now
            profile.save()

        # Send verification email
        try:
            self._send_verification_email(user, token)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f'Failed to send verification email to {user.email}: {str(e)}', exc_info=True)
            messages.warning(self.request, 'Registration successful, but email verification could not be sent.')

        login(self.request, user)
        messages.success(self.request, f"Welcome, {user.username}! Let's set up your preferences to find the perfect dorm.")
        return redirect('user_profile:setup_preferences')

    def _send_verification_email(self, user, token):
        """Helper method to send verification email"""
        from django.urls import reverse
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
        sendgrid_configured = bool(getattr(settings, 'SENDGRID_API_KEY', None))
        smtp_configured = bool(settings.EMAIL_HOST_PASSWORD) and bool(settings.DEFAULT_FROM_EMAIL)
        email_configured = sendgrid_configured or smtp_configured
        
        if email_configured:
            send_mail(
                'Verify your email address',
                '',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=True,
                html_message=html_message,
            )

    def form_invalid(self, form):
        messages.error(self.request, "Registration failed. Please check the form.")
        return super().form_invalid(form)


class LandlordRegisterView(CreateView):
    """Registration view specifically for landlords"""
    form_class = LandlordRegistrationForm
    template_name = "accounts/landlord_register.html"

    def form_valid(self, form):
        """Log in user after successful registration and redirect to verification"""
        user = form.save()
        # Create user profile
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
        if not _:
            profile.verification_token = token
            profile.verification_token_created_at = now
            profile.save()

        # Send verification email
        try:
            self._send_verification_email(user, token)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f'Failed to send verification email to {user.email}: {str(e)}', exc_info=True)
            messages.warning(self.request, 'Registration successful, but email verification could not be sent.')

        login(self.request, user)
        messages.success(self.request, f"Welcome, {user.username}! To list properties, you must verify your identity first.")
        return redirect('accounts:submit_verification')

    def _send_verification_email(self, user, token):
        """Helper method to send verification email"""
        from django.urls import reverse
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
        sendgrid_configured = bool(getattr(settings, 'SENDGRID_API_KEY', None))
        smtp_configured = bool(settings.EMAIL_HOST_PASSWORD) and bool(settings.DEFAULT_FROM_EMAIL)
        email_configured = sendgrid_configured or smtp_configured
        
        if email_configured:
            send_mail(
                'Verify your email address',
                '',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=True,
                html_message=html_message,
            )

    def form_invalid(self, form):
        messages.error(self.request, "Registration failed. Please check the form.")
        return super().form_invalid(form)


class RegisterView(CreateView):
    form_class = CustomUserCreationForm
    template_name = "accounts/register.html"

    def form_valid(self, form):
        """Log in user after successful registration, create profile, and redirect."""
        # Get user_type from POST data and set it on the user instance
        user_type = self.request.POST.get('user_type', 'tenant')
        user = form.save(commit=False)
        user.user_type = user_type
        user.save()
        
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
            # Check for SendGrid API key (HTTP API) or SMTP credentials
            sendgrid_configured = bool(getattr(settings, 'SENDGRID_API_KEY', None))
            smtp_configured = bool(settings.EMAIL_HOST_PASSWORD) and bool(settings.DEFAULT_FROM_EMAIL)
            email_configured = sendgrid_configured or smtp_configured
            
            if not email_configured:
                logger.error(f'Email not configured. SENDGRID_API_KEY={sendgrid_configured}, EMAIL_HOST_PASSWORD={bool(settings.EMAIL_HOST_PASSWORD)}, DEFAULT_FROM_EMAIL={bool(settings.DEFAULT_FROM_EMAIL)}')
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
        # Redirect based on user type
        if user.user_type == 'tenant':
            # Redirect tenant to preference setup
            return reverse_lazy("user_profile:setup_preferences")
        elif user.user_type == 'landlord':
            # Redirect landlord to verification page
            return reverse_lazy("accounts:submit_verification")
        else:
            # Admin or other types go to dashboard
            return reverse_lazy("accounts:dashboard")

    def form_invalid(self, form):
        """Handle errors if registration fails."""
        messages.error(self.request, "Registration failed. Please check the form.")
        return super().form_invalid(form)

# ✅ Login View (CBV)
@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True), name='post')
@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=False), name='post')
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

    def post(self, request, *args, **kwargs):
        """Handle POST requests with rate limit check."""
        if getattr(request, 'limited', False):
            messages.error(request, "Too many login attempts. Please wait a minute before trying again.")
            return render(request, '429.html', {
                'error_message': 'Too many login attempts. Please wait before trying again.'
            }, status=429)
        return super().post(request, *args, **kwargs)

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
            return ["accounts/tenant_dashboard.html"]

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
            context["total_tenants"] = User.objects.filter(user_type="tenant").count()
            context["total_landlords"] = User.objects.filter(user_type="landlord").count()
            context["total_reviews"] = Review.objects.count()
            context["total_dorms"] = Dorm.objects.count()
            
            # Get active users (landlords and tenants)
            context["active_landlords"] = User.objects.filter(user_type="landlord", is_active=True)
            context["active_tenants"] = User.objects.filter(user_type="tenant", is_active=True)

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
            
        elif user.user_type == "tenant":
            user_profile = UserProfile.objects.get(user=user)
            favorite_dorms = user_profile.favorite_dorms.all()
            recent_views = UserInteraction.objects.filter(user=user, interaction_type='view').order_by('-timestamp')[:10]
            viewed_dorms = Dorm.objects.filter(id__in=recent_views.values_list('dorm_id', flat=True))

            # Get tenant preferences for AI-based filtering
            try:
                preferences = TenantPreferences.objects.get(user=user)
                context['has_preferences'] = True
                context['preferences'] = preferences
            except TenantPreferences.DoesNotExist:
                preferences = None
                context['has_preferences'] = False

            # --- Prepare base queryset with SMART FILTERING based on preferences ---
            base_queryset = Dorm.objects.filter(approval_status="approved", available=True)
            
            # Apply preference-based filters if they exist
            if preferences:
                # Budget filter
                if preferences.min_budget > 0 or preferences.max_budget < 1000000:
                    base_queryset = base_queryset.filter(
                        price__gte=preferences.min_budget,
                        price__lte=preferences.max_budget
                    )
                
                # Gender preference filter (if dorm has gender field)
                if hasattr(Dorm, 'gender_preference') and preferences.preferred_gender != 'any':
                    base_queryset = base_queryset.filter(
                        Q(gender_preference=preferences.preferred_gender) | 
                        Q(gender_preference='any')
                    )
                
                # Room type filter
                if preferences.preferred_room_type == 'single':
                    base_queryset = base_queryset.filter(accommodation_type='whole_unit')
                elif preferences.preferred_room_type == 'shared':
                    base_queryset = base_queryset.filter(
                        accommodation_type__in=['bedspace', 'room_sharing']
                    )

            base_queryset = base_queryset.annotate(
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

            # --- Calculate distance score based on preferences or school ---
            if preferences and preferences.preferred_location:
                # Use Google Geocoding API or simple text matching for now
                # For now, we'll use simple text matching and distance if coords available
                for dorm in dorms:
                    if dorm.latitude and dorm.longitude:
                        # Calculate distance from preferred location (would need geocoding in production)
                        # For now, give bonus if address contains preferred location
                        if preferences.preferred_location.lower() in dorm.address.lower():
                            dorm.distance_score = 1.0
                        else:
                            dorm.distance_score = 0.5
                    else:
                        dorm.distance_score = 0.5
            else:
                # No preferences, use default distance scoring
                for dorm in dorms:
                    dorm.distance_score = 0.5
            
            # --- AI-POWERED scoring with preferences ---
            scored_dorms = []
            for i, dorm in enumerate(dorms):
                # Base scoring
                final_score = (
                    float(getattr(dorm, 'avg_rating', dorm.get_average_rating())) * 0.20 +
                    dorm.distance_score * 0.20 +
                    (dorm.amenity_count / 10) * 0.15 +
                    float(getattr(dorm, 'review_count', 0)) * 0.05 +
                    float(dorm.price) * -0.00001
                )
                
                # AI bonuses
                ml_bonus = 0.15 if i in ml_recommended_indices else 0
                collab_bonus = 0.15 if dorm.id in collab_dorm_ids else 0
                
                # PREFERENCE-BASED BONUS (makes it smart!)
                preference_bonus = 0
                amenity_matches = 0
                if preferences:
                    # Get dorm amenities
                    dorm_amenity_names = set(dorm.amenities.values_list('name', flat=True))
                    
                    # Check amenity matches
                    if preferences.wifi_required and any('wifi' in a.lower() or 'internet' in a.lower() for a in dorm_amenity_names):
                        amenity_matches += 1
                    if preferences.parking_required and any('parking' in a.lower() for a in dorm_amenity_names):
                        amenity_matches += 1
                    if preferences.laundry_required and any('laundry' in a.lower() for a in dorm_amenity_names):
                        amenity_matches += 1
                    if preferences.kitchen_required and any('kitchen' in a.lower() for a in dorm_amenity_names):
                        amenity_matches += 1
                    if preferences.aircon_required and any('aircon' in a.lower() or 'air con' in a.lower() for a in dorm_amenity_names):
                        amenity_matches += 1
                    if preferences.security_required and any('security' in a.lower() for a in dorm_amenity_names):
                        amenity_matches += 1
                    if preferences.pet_friendly_required and any('pet' in a.lower() for a in dorm_amenity_names):
                        amenity_matches += 1
                    if preferences.study_area_required and any('study' in a.lower() for a in dorm_amenity_names):
                        amenity_matches += 1
                    if preferences.near_public_transport and any('transport' in a.lower() or 'jeep' in a.lower() or 'mrt' in a.lower() for a in dorm_amenity_names):
                        amenity_matches += 1
                    
                    # Calculate preference bonus (0-0.30 based on amenity matches)
                    total_required_amenities = sum([
                        preferences.wifi_required,
                        preferences.parking_required,
                        preferences.laundry_required,
                        preferences.kitchen_required,
                        preferences.aircon_required,
                        preferences.security_required,
                        preferences.pet_friendly_required,
                        preferences.study_area_required,
                        preferences.near_public_transport
                    ])
                    if total_required_amenities > 0:
                        preference_bonus = (amenity_matches / total_required_amenities) * 0.30
                    
                    # Budget match bonus
                    if preferences.min_budget <= dorm.price <= preferences.max_budget:
                        preference_bonus += 0.10
                
                total_score = final_score + ml_bonus + collab_bonus + preference_bonus

                # --- Enhanced explanation logic with preferences ---
                reasons = []
                dorm.preference_match_percentage = 0
                if preferences and total_required_amenities > 0:
                    match_pct = int((amenity_matches / total_required_amenities) * 100)
                    dorm.preference_match_percentage = match_pct
                    if match_pct >= 80:
                        reasons.append(f" {match_pct}% match with your preferences")
                    elif match_pct >= 50:
                        reasons.append(f" {match_pct}% match with your preferences")
                
                if preferences and preferences.min_budget <= dorm.price <= preferences.max_budget:
                    reasons.append(" Within your budget")
                
                if i in ml_recommended_indices:
                    reasons.append(" Similar to your favorites")
                if dorm.id in collab_dorm_ids:
                    reasons.append(" Popular among similar tenants")
                if getattr(dorm, 'avg_rating', dorm.get_average_rating()) >= 4.5:
                    reasons.append(" Highly rated")
                if dorm.distance_score >= 0.8:
                    reasons.append(" Near your preferred location")
                if dorm.amenity_count >= 7:
                    reasons.append(" Many amenities")
                
                explanation = " • ".join(reasons[:3]) if reasons else "Recommended for you"

                scored_dorms.append((dorm, total_score, explanation, amenity_matches if preferences else 0))
            
            # --- Sort by score (AI-powered ranking!) ---
            scored_dorms.sort(key=lambda x: x[1], reverse=True)
            regular_dorms = [(d, e) for d, s, e, a in scored_dorms if d.accommodation_type == 'whole_unit'][:12]
            bedspace_dorms = [(d, e) for d, s, e, a in scored_dorms if d.accommodation_type in ['bedspace', 'room_sharing']][:12]
            
            # Top matches specifically for preference-based users
            if preferences:
                top_matches = [(d, e, a) for d, s, e, a in scored_dorms if a >= 3][:6]  # At least 3 amenity matches
                context['top_preference_matches'] = top_matches

            context.update({
                "dorms": regular_dorms,
                "bedspace_dorms": bedspace_dorms,
            })
            
        elif user.user_type == 'landlord':
            # Recent reservations
            context['recent_reservations'] = Reservation.objects.select_related('dorm', 'tenant').filter(
                dorm__landlord=user
            ).order_by('-reservation_date')[:5]

            # Core collections
            landlord_dorms = Dorm.objects.filter(landlord=user)
            reservations = Reservation.objects.select_related('dorm', 'tenant').filter(dorm__landlord=user)
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

            # Sales metrics - Use TransactionLog for accurate revenue tracking
            now = timezone.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Get successful payment transactions for this landlord
            # Note: payment_received transactions are created when payment is initiated
            # and updated to status='success' when payment is confirmed via webhook
            successful_transactions = TransactionLog.objects.filter(
                landlord=user,
                transaction_type='payment_received',
                status='success',
                amount__isnull=False  # Ensure amount is present
            )
            
            monthly_sales = successful_transactions.filter(
                created_at__gte=month_start
            ).aggregate(total=Coalesce(Sum('amount'), Value(0), output_field=DecimalField(max_digits=10, decimal_places=2)))['total']
            
            total_income = successful_transactions.aggregate(
                total=Coalesce(Sum('amount'), Value(0), output_field=DecimalField(max_digits=10, decimal_places=2))
            )['total']

            context['monthly_sales'] = monthly_sales or 0
            context['total_income'] = total_income or 0
            
            # Calculate month-over-month sales growth
            from datetime import timedelta
            if month_start.month == 1:
                last_month_start = month_start.replace(year=month_start.year - 1, month=12)
            else:
                last_month_start = month_start.replace(month=month_start.month - 1)
            
            last_month_sales = successful_transactions.filter(
                created_at__gte=last_month_start,
                created_at__lt=month_start
            ).aggregate(total=Coalesce(Sum('amount'), Value(0), output_field=DecimalField(max_digits=10, decimal_places=2)))['total'] or 0
            
            if last_month_sales > 0:
                sales_growth = round(((float(monthly_sales) - float(last_month_sales)) / float(last_month_sales)) * 100, 1)
            else:
                sales_growth = 100 if monthly_sales > 0 else 0
            context['sales_growth'] = sales_growth
            
            # Calculate week-over-week views growth
            week_ago = now - timedelta(days=7)
            two_weeks_ago = now - timedelta(days=14)
            
            recent_views_count = landlord_dorms.filter(
                reservations__created_at__gte=week_ago
            ).aggregate(total=Coalesce(Sum('recent_views'), 0))['total']
            
            previous_views_count = landlord_dorms.filter(
                reservations__created_at__gte=two_weeks_ago,
                reservations__created_at__lt=week_ago
            ).aggregate(total=Coalesce(Sum('recent_views'), 0))['total']
            
            if previous_views_count > 0:
                views_growth = round(((recent_views_count - previous_views_count) / previous_views_count) * 100, 1)
            else:
                views_growth = 100 if recent_views_count > 0 else 0
            context['views_growth'] = views_growth
            
            # Calculate unread inquiries percentage
            unread_count = messages_qs.filter(receiver=user, is_read=False).count()
            total_inquiries = messages_qs.count()
            context['unread_inquiries'] = unread_count
            context['unread_percentage'] = round((unread_count / total_inquiries * 100) if total_inquiries > 0 else 0, 1)

            # Popularity: most viewed dorm and top list
            popular_dorm = landlord_dorms.order_by('-recent_views').first()
            context['popular_dorm'] = popular_dorm
            context['top_dorms_by_views'] = landlord_dorms.order_by('-recent_views').values(
                'id', 'name', 'recent_views'
            )[:5]

            # Monthly reservations and revenue (last 6 months)
            from datetime import timedelta
            # Calculate 6 months ago (approximately 180 days)
            six_months_ago = now - timedelta(days=180)
            
            # Get reservation counts
            last_six_months = Reservation.objects.filter(
                dorm__landlord=user,
                created_at__gte=six_months_ago
            ).annotate(
                month=TruncMonth('created_at')
            ).values('month').annotate(
                count=Count('id')
            ).order_by('month')
            
            # Get revenue from TransactionLog for accurate tracking
            revenue_six_months = TransactionLog.objects.filter(
                landlord=user,
                transaction_type='payment_received',
                status='success',
                amount__isnull=False,  # Ensure amount is present
                created_at__gte=six_months_ago
            ).annotate(
                month=TruncMonth('created_at')
            ).values('month').annotate(
                revenue=Coalesce(Sum('amount'), Value(0), output_field=DecimalField())
            ).order_by('month')

            # Generate last 6 months labels using calendar
            import calendar
            chart_months = []
            for i in range(5, -1, -1):
                # Calculate month offset
                target_month = now.month - i
                target_year = now.year
                
                # Handle year boundary
                while target_month <= 0:
                    target_month += 12
                    target_year -= 1
                
                month_name = calendar.month_abbr[target_month]
                chart_months.append(f"{month_name} {target_year}")
            
            # Map data to months
            reservations_data = {entry['month'].strftime('%b %Y'): entry['count'] for entry in last_six_months if entry['month']}
            revenue_data = {entry['month'].strftime('%b %Y'): float(entry['revenue']) for entry in revenue_six_months if entry['month']}
            
            reservations_counts = [reservations_data.get(m, 0) for m in chart_months]
            revenue_values = [revenue_data.get(m, 0) for m in chart_months]
            
            context['chart_months'] = json.dumps(chart_months)
            context['chart_reservations'] = json.dumps(reservations_counts)
            context['chart_revenue'] = json.dumps(revenue_values)
            
            # Reservation status breakdown for pie chart
            context['status_pending'] = reservations.filter(status='pending').count()
            context['status_pending_payment'] = reservations.filter(status='pending_payment').count()
            context['status_confirmed'] = reservations.filter(status='confirmed').count()
            context['status_occupied'] = reservations.filter(status='occupied').count()
            context['status_completed'] = reservations.filter(status='completed').count()
            context['status_declined'] = reservations.filter(status='declined').count()
            context['status_cancelled'] = reservations.filter(status='cancelled').count()
            
            # Top performing dorms (by revenue and bookings)
            top_dorms_list = []
            top_dorms_revenue = landlord_dorms.annotate(
                total_revenue=Coalesce(
                    Sum('reservations__payment_amount', filter=Q(reservations__has_paid_reservation=True)),
                    Value(0),
                    output_field=DecimalField()
                ),
                total_bookings=Count('reservations', filter=Q(reservations__status__in=['confirmed', 'occupied', 'completed']))
            ).order_by('-total_revenue')[:5]
            
            # Calculate occupancy percentage for each dorm
            for dorm in top_dorms_revenue:
                occupied_beds = dorm.total_beds - dorm.available_beds
                occupancy_pct = round((occupied_beds / dorm.total_beds * 100) if dorm.total_beds > 0 else 0, 1)
                top_dorms_list.append({
                    'dorm': dorm,
                    'occupancy_pct': occupancy_pct
                })
            
            context['top_dorms'] = top_dorms_list

            # Calendar data for current month
            from datetime import datetime, timedelta
            import calendar as cal
            
            today = now.date()
            current_month = today.month
            current_year = today.year
            
            # Get all reservations for the current month (timezone-aware)
            from django.utils.timezone import make_aware
            month_start = make_aware(datetime(current_year, current_month, 1))
            if current_month == 12:
                month_end = make_aware(datetime(current_year + 1, 1, 1))
            else:
                month_end = make_aware(datetime(current_year, current_month + 1, 1))
            
            current_month_reservations = reservations.filter(
                created_at__gte=month_start,
                created_at__lt=month_end
            )
            
            # Prepare calendar events grouped by date
            calendar_events = {}
            for reservation in reservations.select_related('dorm', 'tenant'):
                # Visit dates
                if reservation.visit_date:
                    visit_day = reservation.visit_date.day
                    if visit_day not in calendar_events:
                        calendar_events[visit_day] = []
                    calendar_events[visit_day].append({
                        'type': 'visit',
                        'status': reservation.visit_status,
                        'dorm': reservation.dorm.name,
                        'tenant': reservation.tenant.get_full_name(),
                        'time': reservation.visit_time_slot
                    })
                
                # Move-in dates
                if reservation.move_in_date:
                    move_day = reservation.move_in_date.day
                    if move_day not in calendar_events:
                        calendar_events[move_day] = []
                    calendar_events[move_day].append({
                        'type': 'move_in',
                        'status': reservation.status,
                        'dorm': reservation.dorm.name,
                        'tenant': reservation.tenant.get_full_name()
                    })
            
            # Prepare calendar structure
            month_calendar = cal.monthcalendar(current_year, current_month)
            context['calendar_month_name'] = cal.month_name[current_month]
            context['calendar_year'] = current_year
            context['calendar_weeks'] = month_calendar
            context['calendar_events'] = calendar_events
            context['today_day'] = today.day
            
            # Occupancy rate
            total_beds = landlord_dorms.aggregate(
                total=Coalesce(Sum('total_beds'), 0)
            )['total']
            
            # Count occupied beds: for whole_unit dorms, count all beds if occupied
            # for bedspace dorms, count the number of occupied reservations
            occupied_beds = 0
            for dorm in landlord_dorms:
                active_reservations = reservations.filter(
                    dorm=dorm,
                    status__in=['confirmed', 'occupied']
                )
                if dorm.accommodation_type == 'whole_unit':
                    # If any reservation is active for whole unit, all beds are occupied
                    if active_reservations.exists():
                        occupied_beds += dorm.total_beds
                else:
                    # For bedspace, count individual reservations
                    occupied_beds += active_reservations.count()
            
            context['occupancy_rate'] = round((occupied_beds / total_beds * 100) if total_beds > 0 else 0, 1)
            context['occupied_beds'] = occupied_beds
            context['total_beds'] = total_beds
            
            # Upcoming events
            context['upcoming_visits'] = reservations.filter(
                visit_date__gte=today,
                visit_status__in=['pending', 'confirmed']
            ).count()
            context['upcoming_move_ins'] = reservations.filter(
                move_in_date__gte=today,
                status__in=['confirmed', 'pending_payment']
            ).count()
            
            # Active tenants
            context['active_tenants'] = reservations.filter(status='occupied').count()
        
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
        elif request.user.user_type == "tenant":
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
    paginate_by = 20

    def get_queryset(self):
        queryset = Notification.objects.filter(user=self.request.user).order_by("-created_at")
        
        # Filter by read/unread status
        filter_type = self.request.GET.get('filter', 'all')
        if filter_type == 'unread':
            queryset = queryset.filter(is_read=False)
        elif filter_type == 'read':
            queryset = queryset.filter(is_read=True)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_type'] = self.request.GET.get('filter', 'all')
        context['unread_count'] = Notification.objects.filter(user=self.request.user, is_read=False).count()
        context['read_count'] = Notification.objects.filter(user=self.request.user, is_read=True).count()
        context['total_count'] = Notification.objects.filter(user=self.request.user).count()
        return context

class MarkNotificationAsReadView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        from django.core.cache import cache
        
        notification = get_object_or_404(Notification, pk=pk, user=request.user)
        notification.is_read = True
        notification.save()
        
        # Clear notification cache for this user
        cache_key = f'notification_count_{request.user.id}'
        cache.delete(cache_key)
        
        return JsonResponse({"success": True})

class NotificationAPIView(LoginRequiredMixin, View):
    """API endpoint for fetching notifications as JSON"""
    def get(self, request, *args, **kwargs):
        from django.utils.timesince import timesince
        
        filter_type = request.GET.get('filter', 'all')
        
        # Build queryset
        queryset = Notification.objects.filter(user=request.user).order_by('-created_at')
        
        if filter_type == 'unread':
            queryset = queryset.filter(is_read=False)
        elif filter_type == 'read':
            queryset = queryset.filter(is_read=True)
        
        # Limit to most recent 50 notifications
        notifications = queryset[:50]
        
        # Serialize notifications
        notifications_data = []
        for notif in notifications:
            notifications_data.append({
                'id': notif.id,
                'message': notif.message,
                'is_read': notif.is_read,
                'created_at': notif.created_at.strftime('%b %d, %Y at %I:%M %p'),
                'time_ago': timesince(notif.created_at) + ' ago',
            })
        
        return JsonResponse({
            'notifications': notifications_data,
            'filter': filter_type
        })

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
        elif user.user_type == 'tenant':
            # Delete all reservations made by this tenant
            Reservation.objects.filter(tenant=user).delete()
            
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
        # Check for SendGrid API key (HTTP API) or SMTP credentials
        sendgrid_configured = bool(getattr(settings, 'SENDGRID_API_KEY', None))
        smtp_configured = bool(settings.EMAIL_HOST_PASSWORD) and bool(settings.DEFAULT_FROM_EMAIL)
        email_configured = sendgrid_configured or smtp_configured
        
        if not email_configured:
            logger.error(
                f'Email not configured. SENDGRID_API_KEY={sendgrid_configured}, '
                f'EMAIL_HOST_PASSWORD={bool(settings.EMAIL_HOST_PASSWORD)}, '
                f'DEFAULT_FROM_EMAIL={bool(settings.DEFAULT_FROM_EMAIL)}'
            )
            return False, 'Email service is not configured. Please set SENDGRID_API_KEY in Railway environment variables.'
        
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
        transactions = Reservation.objects.select_related('dorm', 'tenant').order_by('-created_at')
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
        
        # Get user's reviews if tenant
        user_reviews = []
        if profile_user.user_type == 'tenant':
            user_reviews = Review.objects.filter(user=profile_user)[:5]
        
        # Get user's reservations
        user_reservations = Reservation.objects.filter(tenant=profile_user)[:5]
        
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
        elif reported_user.user_type == 'tenant':
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


# Transaction Log View for Landlords and Admins
@method_decorator(login_required, name='dispatch')
class TransactionLogView(LoginRequiredMixin, ListView):
    """
    Display transaction log with filtering options
    - Landlords: see all their transactions
    - Admins: see only payment and reservation transactions across all landlords
    """
    model = TransactionLog
    template_name = 'accounts/transaction_log.html'
    context_object_name = 'transactions'
    paginate_by = 20
    
    def get_queryset(self):
        """Filter transactions based on user type"""
        user = self.request.user
        
        # Admin sees payment and reservation transactions from all landlords
        if user.user_type == 'admin':
            queryset = TransactionLog.objects.filter(
                transaction_type__in=[
                    'reservation_created',
                    'reservation_confirmed', 
                    'reservation_cancelled',
                    'payment_received',
                    'payment_verified',
                    'payment_rejected',
                ]
            ).select_related('landlord', 'dorm', 'reservation', 'tenant')
        
        # Landlords see only their own transactions
        elif user.user_type == 'landlord':
            queryset = TransactionLog.objects.filter(
                landlord=user
            ).select_related('dorm', 'reservation', 'tenant')
        
        else:
            return TransactionLog.objects.none()
        
        # Filter by transaction type
        transaction_type = self.request.GET.get('type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        # Filter by dorm
        dorm_id = self.request.GET.get('dorm')
        if dorm_id:
            queryset = queryset.filter(dorm_id=dorm_id)
        
        # Filter by landlord (admin only)
        if user.user_type == 'admin':
            landlord_id = self.request.GET.get('landlord')
            if landlord_id:
                queryset = queryset.filter(landlord_id=landlord_id)
        
        # Filter by date range
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                queryset = queryset.filter(created_at__gte=start_date)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d')
                # Add one day to include the entire end date
                end_date = end_date + timedelta(days=1)
                queryset = queryset.filter(created_at__lt=end_date)
            except ValueError:
                pass
        
        # Search by description or tenant
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(description__icontains=search) |
                Q(tenant__first_name__icontains=search) |
                Q(tenant__last_name__icontains=search) |
                Q(tenant__email__icontains=search) |
                Q(dorm__name__icontains=search)
            )
            
            # Admin can also search by landlord
            if user.user_type == 'admin':
                queryset = queryset | TransactionLog.objects.filter(
                    Q(landlord__first_name__icontains=search) |
                    Q(landlord__last_name__icontains=search) |
                    Q(landlord__email__icontains=search)
                ).filter(transaction_type__in=[
                    'reservation_created', 'reservation_confirmed', 'reservation_cancelled',
                    'payment_received', 'payment_verified', 'payment_rejected'
                ])
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Admin sees all dorms and landlords, landlord sees only their dorms
        if user.user_type == 'admin':
            context['user_dorms'] = Dorm.objects.all().select_related('landlord')
            context['all_landlords'] = CustomUser.objects.filter(user_type='landlord')
            # Filter transaction types to only show payment/reservation related
            context['transaction_types'] = [
                ('reservation_created', 'Reservation Created'),
                ('reservation_confirmed', 'Reservation Confirmed'),
                ('reservation_cancelled', 'Reservation Cancelled'),
                ('payment_received', 'Payment Received'),
                ('payment_verified', 'Payment Verified'),
                ('payment_rejected', 'Payment Rejected'),
            ]
        else:
            context['user_dorms'] = Dorm.objects.filter(landlord=user)
            context['transaction_types'] = TransactionLog.TRANSACTION_TYPES
        
        # Get filter values to maintain state
        context['selected_type'] = self.request.GET.get('type', '')
        context['selected_dorm'] = self.request.GET.get('dorm', '')
        context['selected_landlord'] = self.request.GET.get('landlord', '')
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')
        context['search_query'] = self.request.GET.get('search', '')
        
        # Statistics
        queryset = self.get_queryset()
        context['total_transactions'] = queryset.count()
        context['total_revenue'] = queryset.filter(
            transaction_type__in=['payment_received', 'payment_verified']
        ).aggregate(total=Coalesce(Sum('amount'), Value(0), output_field=DecimalField()))['total']
        
        # Transaction type breakdown
        context['transaction_breakdown'] = queryset.values('transaction_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return context


# ============== IDENTITY VERIFICATION VIEWS ==============

@method_decorator(login_required, name='dispatch')
class SubmitVerificationView(View):
    """View for landlords to submit identity verification documents"""
    
    def get(self, request):
        """Display verification submission form"""
        if request.user.user_type != 'landlord':
            messages.error(request, "Only landlords can submit verification requests.")
            return redirect('accounts:dashboard')
        
        # Check if already verified
        if request.user.is_identity_verified:
            messages.info(request, "Your identity is already verified!")
            return redirect('accounts:dashboard')
        
        # Check if already pending
        if request.user.verification_status == 'pending':
            messages.warning(request, "Your verification request is already pending review.")
            return redirect('accounts:dashboard')
        
        form = IdentityVerificationForm()
        return render(request, 'accounts/submit_verification.html', {'form': form})
    
    def post(self, request):
        """Handle verification submission"""
        if request.user.user_type != 'landlord':
            messages.error(request, "Only landlords can submit verification requests.")
            return redirect('accounts:dashboard')
        
        form = IdentityVerificationForm(request.POST, request.FILES)
        if form.is_valid():
            user = request.user
            user.government_id = form.cleaned_data['government_id']
            user.proof_of_ownership = form.cleaned_data['proof_of_ownership']
            user.selfie_with_id = form.cleaned_data['selfie_with_id']
            user.verification_status = 'pending'
            user.verification_submitted_at = timezone.now()
            user.save()
            
            messages.success(request, "Verification documents submitted successfully! An admin will review your request shortly.")
            return redirect('accounts:dashboard')
        
        return render(request, 'accounts/submit_verification.html', {'form': form})


@method_decorator(login_required, name='dispatch')
class VerificationRequestsView(UserPassesTestMixin, ListView):
    """View for admins to see all pending verification requests"""
    model = CustomUser
    template_name = 'accounts/verification_requests.html'
    context_object_name = 'verification_requests'
    
    def test_func(self):
        return self.request.user.user_type == 'admin'
    
    def get_queryset(self):
        return CustomUser.objects.filter(
            user_type='landlord',
            verification_status='pending'
        ).order_by('-verification_submitted_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add verified and rejected landlords for logs
        context['verified_landlords'] = CustomUser.objects.filter(
            user_type='landlord',
            verification_status='approved',
            is_identity_verified=True
        ).order_by('-verification_reviewed_at')
        
        context['rejected_landlords'] = CustomUser.objects.filter(
            user_type='landlord',
            verification_status='rejected'
        ).order_by('-verification_reviewed_at')
        
        return context


@method_decorator(login_required, name='dispatch')
class ReviewVerificationView(UserPassesTestMixin, View):
    """View for admins to review a specific verification request"""
    
    def test_func(self):
        return self.request.user.user_type == 'admin'
    
    def get(self, request, user_id):
        """Display verification review page"""
        landlord = get_object_or_404(CustomUser, id=user_id, user_type='landlord')
        form = VerificationReviewForm()
        
        return render(request, 'accounts/review_verification.html', {
            'landlord': landlord,
            'form': form
        })
    
    def post(self, request, user_id):
        """Handle verification approval/rejection"""
        landlord = get_object_or_404(CustomUser, id=user_id, user_type='landlord')
        form = VerificationReviewForm(request.POST)
        
        if form.is_valid():
            action = form.cleaned_data['action']
            rejection_reason = form.cleaned_data.get('rejection_reason')
            
            if action == 'approve':
                landlord.is_identity_verified = True
                landlord.verification_status = 'approved'
                landlord.verification_reviewed_at = timezone.now()
                landlord.verification_rejection_reason = None
                landlord.save()
                
                messages.success(request, f"Verification approved for {landlord.username}. They now have a verified badge!")
                
                # Notify landlord
                from dormitory.views import notify_user
                notify_user(
                    user=landlord,
                    message="Congratulations! Your identity verification has been approved. You now have a verified landlord badge!"
                )
                
            elif action == 'reject':
                landlord.is_identity_verified = False
                landlord.verification_status = 'rejected'
                landlord.verification_reviewed_at = timezone.now()
                landlord.verification_rejection_reason = rejection_reason
                landlord.save()
                
                messages.warning(request, f"Verification rejected for {landlord.username}.")
                
                # Notify landlord
                from dormitory.views import notify_user
                notify_user(
                    user=landlord,
                    message=f"Your identity verification was rejected. Reason: {rejection_reason}"
                )
            
            return redirect('accounts:verification_requests')
        
        return render(request, 'accounts/review_verification.html', {
            'landlord': landlord,
            'form': form
        })


class HowItWorksView(TemplateView):
    """View for the How It Works page - explains the system to tenants"""
    template_name = 'accounts/how_it_works.html'
