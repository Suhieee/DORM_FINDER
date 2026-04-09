from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import DetailView, ListView, UpdateView, View
from django.urls import reverse_lazy, reverse
from accounts.models import CustomUser  
from .models import UserProfile, FavoriteDorm, TenantPreferences
from .forms import UserProfileForm, TenantPreferencesForm, RoommatePreferencesForm
from django.contrib import messages
from .forms import PWDVerificationForm
from accounts.models import Notification

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from dormitory.models import Dorm
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
import random
import logging

logger = logging.getLogger(__name__)

class ProfileDetailView(LoginRequiredMixin, DetailView):
    model = CustomUser
    template_name = "user_profile/profile.html" 
    context_object_name = "profile_user"

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Ensure a profile exists; avoid RelatedObjectDoesNotExist
        user_profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        context['favorite_dorms'] = FavoriteDorm.objects.filter(
            user_profile=user_profile
        ).select_related('dorm')
        
        # Add listed dorms for landlords
        if self.request.user.user_type == 'landlord':
            context['listed_dorms'] = Dorm.objects.filter(landlord=self.request.user)
        
        # Add tenant preferences if user is a tenant
        if self.request.user.user_type == 'tenant':
            try:
                context['tenant_preferences'] = TenantPreferences.objects.get(user=self.request.user)
            except TenantPreferences.DoesNotExist:
                context['tenant_preferences'] = None
                
        return context
    
class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = UserProfile
    form_class = UserProfileForm
    template_name = "user_profile/edit_profile.html"
    success_url = reverse_lazy("user_profile:profile")

    def get_object(self, queryset=None):
        # Ensure profile exists when accessing edit
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    def form_valid(self, form):
        messages.success(self.request, 'Your profile has been updated successfully!')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'There was an error updating your profile. Please try again.')
        return super().form_invalid(form)


class SubmitPWDVerificationView(LoginRequiredMixin, View):
    template_name = 'user_profile/submit_pwd_verification.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'tenant':
            messages.warning(request, 'PWD discount requests are only for tenants.');
            return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.is_pwd_verified:
            messages.info(request, 'Your PWD discount is already approved.')
            return redirect('user_profile:profile')
        if profile.pwd_verification_status == 'pending':
            messages.warning(request, 'Your PWD discount request is already pending review.')
            return redirect('user_profile:profile')

        form = PWDVerificationForm()
        return render(request, self.template_name, {'form': form, 'profile': profile})

    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.is_pwd_verified:
            messages.info(request, 'Your PWD discount is already approved.')
            return redirect('user_profile:profile')

        form = PWDVerificationForm(request.POST, request.FILES)
        if form.is_valid():
            profile.pwd_document = form.cleaned_data['pwd_document']
            profile.pwd_id_photo = form.cleaned_data['pwd_id_photo']
            profile.pwd_reference_number = form.cleaned_data['pwd_reference_number']
            profile.pwd_verification_status = 'pending'
            profile.pwd_rejection_reason = None
            profile.pwd_submitted_at = timezone.now()
            profile.save(update_fields=[
                'pwd_document',
                'pwd_id_photo',
                'pwd_reference_number',
                'pwd_verification_status',
                'pwd_rejection_reason',
                'pwd_submitted_at',
            ])

            messages.success(request, 'PWD discount request submitted. An admin will review it shortly.')
            return redirect('user_profile:profile')

        return render(request, self.template_name, {'form': form, 'profile': profile})


@method_decorator(login_required, name='dispatch')
class PWDVerificationRequestsView(UserPassesTestMixin, ListView):
    model = UserProfile
    template_name = 'user_profile/pwd_verification_requests.html'
    context_object_name = 'requests_list'

    def test_func(self):
        return self.request.user.user_type == 'admin'

    def get_queryset(self):
        return UserProfile.objects.select_related('user').filter(
            user__user_type='tenant',
            pwd_verification_status='pending'
        ).order_by('-pwd_submitted_at')


@method_decorator(login_required, name='dispatch')
class ReviewPWDVerificationView(UserPassesTestMixin, View):
    template_name = 'user_profile/review_pwd_verification.html'

    def test_func(self):
        return self.request.user.user_type == 'admin'

    def get_profile(self, user_id):
        return get_object_or_404(UserProfile, user__id=user_id, user__user_type='tenant')

    def get(self, request, user_id):
        profile = self.get_profile(user_id)
        return render(request, self.template_name, {'profile': profile})

    def post(self, request, user_id):
        profile = self.get_profile(user_id)
        action = request.POST.get('action')
        rejection_reason = request.POST.get('rejection_reason', '').strip()

        if action == 'approve':
            profile.pwd_verification_status = 'approved'
            profile.is_pwd_verified = True
            profile.pwd_reviewed_at = timezone.now()
            profile.pwd_rejection_reason = None
            profile.save(update_fields=['pwd_verification_status', 'is_pwd_verified', 'pwd_reviewed_at', 'pwd_rejection_reason'])
            Notification.objects.create(
                user=profile.user,
                message='Your PWD discount request has been approved. The discount will now be applied automatically.',
                related_object_id=profile.user.id,
            )
            messages.success(request, f'PWD discount approved for {profile.user.username}.')
        elif action == 'reject':
            profile.pwd_verification_status = 'rejected'
            profile.is_pwd_verified = False
            profile.pwd_reviewed_at = timezone.now()
            profile.pwd_rejection_reason = rejection_reason or 'No reason provided.'
            profile.save(update_fields=['pwd_verification_status', 'is_pwd_verified', 'pwd_reviewed_at', 'pwd_rejection_reason'])
            Notification.objects.create(
                user=profile.user,
                message=f'Your PWD discount request was rejected. Reason: {profile.pwd_rejection_reason}',
                related_object_id=profile.user.id,
            )
            messages.warning(request, f'PWD discount rejected for {profile.user.username}.')
        else:
            messages.error(request, 'Invalid action.')

        return redirect('user_profile:pwd_verification_requests')

@method_decorator(ensure_csrf_cookie, name='dispatch')
class ToggleFavoriteDormView(LoginRequiredMixin, View):
    def post(self, request, dorm_id):
        try:
            dorm = Dorm.objects.get(id=dorm_id)
            profile = UserProfile.objects.get(user=request.user)
            
            if dorm in profile.favorite_dorms.all():
                profile.favorite_dorms.remove(dorm)
                messages.success(request, f'Removed {dorm.name} from favorites')
                is_favorite = False
            else:
                profile.favorite_dorms.add(dorm)
                messages.success(request, f'Added {dorm.name} to favorites')
                is_favorite = True
                
            return JsonResponse({
                'status': 'success',
                'is_favorite': is_favorite
            })
            
        except (Dorm.DoesNotExist, UserProfile.DoesNotExist) as e:
            messages.error(request, 'Failed to update favorites. Please try again.')
            return JsonResponse({
                'status': 'error'
            }, status=400)


class PublicLandlordProfileView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View for admins to see landlord profiles with verification documents"""
    model = CustomUser
    template_name = "user_profile/landlord_profile.html"
    context_object_name = "landlord"
    pk_url_kwarg = "user_id"
    
    def test_func(self):
        # Only admins can view this
        return self.request.user.is_staff
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        landlord = self.get_object()
        
        # Get user profile and dorms
        user_profile, _ = UserProfile.objects.get_or_create(user=landlord)
        context['user_profile'] = user_profile
        context['dorms'] = landlord.dorm_set.all()
        
        # Show verification documents
        context['show_documents'] = True
        
        return context


class SetupPreferencesView(LoginRequiredMixin, View):
    """Two-step wizard for setting up dorm and roommate preferences"""
    template_name = "user_profile/setup_preferences.html"

    def dispatch(self, request, *args, **kwargs):
        # Only tenants can access this
        if request.user.user_type != 'tenant':
            messages.warning(request, 'Preferences are only for tenants.')
            return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        # Get or create preferences
        preferences, created = TenantPreferences.objects.get_or_create(user=request.user)
        
        # Default to dorm_and_roommate so edit_preferences step 2 stays accessible
        if not preferences.preference_choice:
            preferences.preference_choice = 'dorm_and_roommate'
            preferences.save(update_fields=['preference_choice'])
        
        # Determine current step (default to step 1)
        step = request.GET.get('step', '1')
        
        if step == '2':
            # Show Step 2: Roommate preferences
            form = RoommatePreferencesForm(instance=preferences)
            context = {
                'form': form,
                'step': 2,
                'preferences': preferences,
            }
        else:
            # Step 1: Dorm preferences
            form = TenantPreferencesForm(instance=preferences)
            context = {
                'form': form,
                'step': 1,
                'preferences': preferences,
            }
        
        return render(request, self.template_name, context)

    def post(self, request):
        # Get or create preferences
        preferences, created = TenantPreferences.objects.get_or_create(user=request.user)
        
        # Ensure preference_choice is always set
        if not preferences.preference_choice:
            preferences.preference_choice = 'dorm_and_roommate'
            preferences.save(update_fields=['preference_choice'])
        
        # Determine current step
        step = request.POST.get('step', '1')
        
        if step == '1':
            # Process dorm preferences (step 1)
            form = TenantPreferencesForm(request.POST, instance=preferences)
            if form.is_valid():
                form.save()
                messages.success(request, 'Dorm preferences saved! Now set your roommate preferences.')
                return redirect(reverse('user_profile:setup_preferences') + '?step=2')
            else:
                messages.error(request, 'There was an error saving your preferences. Please try again.')
                context = {
                    'form': form,
                    'step': 1,
                    'preferences': preferences,
                }
                return render(request, self.template_name, context)
        
        elif step == '2':
            # Process roommate preferences (step 2)
            form = RoommatePreferencesForm(request.POST, instance=preferences)
            if form.is_valid():
                form.save()
                
                # Auto-create RoommatePost from preferences
                try:
                    roommate_post = preferences.sync_to_roommate_post()
                    messages.success(request, 'All preferences saved! Your roommate profile has been created. You\'re all set!')
                except Exception as e:
                    messages.warning(request, f'Preferences saved, but there was an issue creating your roommate profile: {str(e)}')
                
                return redirect('accounts:dashboard')
            else:
                messages.error(request, 'There was an error saving your roommate preferences. Please try again.')
                context = {
                    'form': form,
                    'step': 2,
                    'preferences': preferences,
                }
                return render(request, self.template_name, context)
        
        # Default fallback
        return redirect('user_profile:setup_preferences')



# ─────────────────────────────────────────────
# Change Password via OTP (email)
# ─────────────────────────────────────────────

class RequestPasswordOTPView(LoginRequiredMixin, View):
    """Generate a 6-digit OTP, store it in the session, and send it via SendGrid."""

    def post(self, request):
        user = request.user

        if not user.email:
            return JsonResponse(
                {'status': 'error', 'message': 'Please add an email to your profile before changing your password.'},
                status=400,
            )

        otp  = str(random.randint(100000, 999999))

        # Store OTP + expiry (10 minutes) in session
        request.session['pwd_otp']         = otp
        request.session['pwd_otp_expires'] = (
            timezone.now() + timezone.timedelta(minutes=10)
        ).isoformat()
        request.session['pwd_otp_uid']     = user.pk
        request.session.modified = True

        subject  = 'Your Password Change OTP – Dorm Finder'
        message  = (
            f'Hi {user.first_name or user.username},\n\n'
            f'Your one-time password (OTP) to change your Dorm Finder account password is:\n\n'
            f'    {otp}\n\n'
            f'This code expires in 10 minutes. If you did not request this, '
            f'you can safely ignore this email.\n\n'
            f'– The Dorm Finder Team'
        )
        html_message = f"""
        <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">
            <div style="background:#2563eb;padding:24px 32px;border-radius:12px 12px 0 0;">
                <h2 style="color:#fff;margin:0;font-size:20px;">Password Change OTP</h2>
            </div>
            <div style="background:#f8fafc;padding:32px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;">
                <p style="color:#374151;font-size:15px;">Hi <strong>{user.first_name or user.username}</strong>,</p>
                <p style="color:#374151;font-size:15px;">Use the code below to change your password. It expires in <strong>10 minutes</strong>.</p>
                <div style="text-align:center;margin:28px 0;">
                    <span style="font-size:40px;font-weight:800;letter-spacing:10px;color:#1d4ed8;">{otp}</span>
                </div>
                <p style="color:#6b7280;font-size:13px;">If you didn't request this, ignore this email.</p>
                <p style="color:#6b7280;font-size:13px;">– The Dorm Finder Team</p>
            </div>
        </div>
        """

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=html_message,
                fail_silently=False,
            )
            return JsonResponse({'status': 'ok', 'email': user.email})
        except Exception as e:
            logger.error(f'OTP email failed for user {user.pk}: {e}', exc_info=True)
            return JsonResponse({'status': 'error', 'message': 'Failed to send OTP. Please try again.'}, status=500)


class ChangePasswordWithOTPView(LoginRequiredMixin, View):
    """Validate the OTP from session, then change the password."""

    def post(self, request):
        user        = request.user
        otp_input   = request.POST.get('otp', '').strip()
        new_password = request.POST.get('new_password', '')
        confirm_pw  = request.POST.get('confirm_password', '')

        stored_otp     = request.session.get('pwd_otp')
        expires_str    = request.session.get('pwd_otp_expires')
        stored_uid     = request.session.get('pwd_otp_uid')

        # Basic checks
        if not stored_otp or not expires_str or stored_uid != user.pk:
            return JsonResponse({'status': 'error', 'message': 'No OTP request found. Please request a new code.'}, status=400)

        # Expiry check
        try:
            expires_at = timezone.datetime.fromisoformat(expires_str)
        except (TypeError, ValueError):
            self._clear_otp(request)
            return JsonResponse({'status': 'error', 'message': 'OTP data is invalid. Please request a new code.'}, status=400)

        if timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at)
        if timezone.now() > expires_at:
            self._clear_otp(request)
            return JsonResponse({'status': 'error', 'message': 'OTP has expired. Please request a new one.'}, status=400)

        # OTP match
        if otp_input != stored_otp:
            return JsonResponse({'status': 'error', 'message': 'Incorrect OTP. Please try again.'}, status=400)

        # Password match
        if new_password != confirm_pw:
            return JsonResponse({'status': 'error', 'message': 'Passwords do not match.'}, status=400)

        # Django password validation
        try:
            validate_password(new_password, user=user)
        except ValidationError as e:
            return JsonResponse({'status': 'error', 'message': ' '.join(e.messages)}, status=400)

        # All good — change password
        user.set_password(new_password)
        user.save()
        self._clear_otp(request)

        # Keep the user logged in after password change
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, user)

        return JsonResponse({'status': 'ok', 'message': 'Password changed successfully!'})

    @staticmethod
    def _clear_otp(request):
        for key in ('pwd_otp', 'pwd_otp_expires', 'pwd_otp_uid'):
            request.session.pop(key, None)
        request.session.modified = True


class EditPreferencesView(LoginRequiredMixin, View):
    """View for tenants to edit their preferences anytime (two-step)"""
    template_name = "user_profile/edit_preferences.html"

    def dispatch(self, request, *args, **kwargs):
        # Only tenants can access this
        if request.user.user_type != 'tenant':
            messages.warning(request, 'Preferences are only for tenants.')
            return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        # Get or create preferences
        preferences, created = TenantPreferences.objects.get_or_create(user=request.user)
        
        # Determine which step to display
        step = request.GET.get('step', '1')
        
        if step == '2':
            # Step 2: Roommate preferences
            form = RoommatePreferencesForm(instance=preferences)
        else:
            # Step 1: Dorm preferences
            form = TenantPreferencesForm(instance=preferences)
        
        return render(request, self.template_name, {
            'form': form,
            'step': step,
            'preferences': preferences
        })

    def post(self, request):
        # Get or create preferences
        preferences, created = TenantPreferences.objects.get_or_create(user=request.user)
        
        step = request.POST.get('step') or request.GET.get('step', '1')
        
        if step == '2':
            # Step 2: Save roommate preferences
            form = RoommatePreferencesForm(request.POST, instance=preferences)
            if form.is_valid():
                form.save()
                
                # If user has roommate matching enabled, sync to RoommatePost
                if preferences.preference_choice == 'dorm_and_roommate':
                    try:
                        preferences.sync_to_roommate_post()
                        messages.success(request, 'Your preferences and roommate profile have been updated successfully!')
                    except Exception as e:
                        messages.warning(request, f'Preferences updated, but there was an issue updating your roommate profile: {str(e)}')
                else:
                    messages.success(request, 'Your preferences have been updated successfully!')
                
                return redirect('user_profile:profile')
            else:
                messages.error(request, 'Please correct the errors below.')
                return render(request, self.template_name, {
                    'form': form,
                    'step': step,
                    'preferences': preferences
                })
        else:
            # Step 1: Save dorm preferences and redirect to step 2
            form = TenantPreferencesForm(request.POST, instance=preferences)
            if form.is_valid():
                form.save()
                # Redirect to step 2
                return redirect(reverse('user_profile:edit_preferences') + '?step=2')
            else:
                messages.error(request, 'Please correct the errors below.')
                return render(request, self.template_name, {
                    'form': form,
                    'step': step,
                    'preferences': preferences
                })