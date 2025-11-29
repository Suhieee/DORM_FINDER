from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
        RegisterView, LoginView, DashboardView,
        ApproveDormView, RejectDormView, ReviewDormView , RoleBasedRedirectView , LogoutView , MarkNotificationAsReadView, NotificationListView, CreateAdminView, ManageUsersView, ToggleUserStatusView, DeleteUserView, UpdateUserRoleView, VerifyEmailView, ResendVerificationEmailView, ResendVerificationEmailLoggedInView, TransactionLogView,
        ViewUserProfileView, ReportUserView, ManageReportsView, ReportDetailView, ResolveReportView, EnhancedToggleUserStatusView
    )

app_name = "accounts"
urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),

    path("approve-dorm/<int:pk>/", ApproveDormView.as_view(), name="approve_dorm"),
    path("reject-dorm/<int:pk>/", RejectDormView.as_view(), name="reject_dorm"),
    path("review-dorm/<int:pk>/", ReviewDormView.as_view(), name="review_dorm"),

    path("role-based-redirect/", RoleBasedRedirectView.as_view(), name="role_based_redirect"),

    path("notifications/", NotificationListView.as_view(), name="notification_list"),
    path("notifications/read/<int:pk>/", MarkNotificationAsReadView.as_view(), name="mark_notification_read"),

    path('create-admin/', CreateAdminView.as_view(), name='create_admin'),
    path('manage-users/', ManageUsersView.as_view(), name='manage_users'),
    path('manage-users/<int:pk>/role/', UpdateUserRoleView.as_view(), name='update_user_role'),
    path('toggle-user-status/<int:pk>/', ToggleUserStatusView.as_view(), name='toggle_user_status'),
    path('enhanced-toggle-user-status/<int:pk>/', EnhancedToggleUserStatusView.as_view(), name='enhanced_toggle_user_status'),
    path('delete-user/<int:pk>/', DeleteUserView.as_view(), name='delete_user'),
    path("verify-email/<str:token>/", VerifyEmailView.as_view(), name="verify_email"),
    path("resend-verification/", ResendVerificationEmailView.as_view(), name="resend_verification"),
    path("resend-verification-logged-in/", ResendVerificationEmailLoggedInView.as_view(), name="resend_verification_logged_in"),
    path('transaction-log/', TransactionLogView.as_view(), name='transaction_log'),
    
    # Password reset flow
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='accounts/password_reset_form.html',
             email_template_name='accounts/password_reset_email.html',
             subject_template_name='accounts/password_reset_subject.txt',
             success_url='/accounts/password-reset/done/'
         ),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset_confirm.html',
             success_url='/accounts/reset/done/'
         ),
         name='password_reset_confirm'),
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password_reset_complete.html'
         ),
         name='password_reset_complete'),
    
    # New profile and reporting URLs
    path('profile/<int:user_id>/', ViewUserProfileView.as_view(), name='view_user_profile'),
    path('report-user/<int:user_id>/', ReportUserView.as_view(), name='report_user'),
    path('manage-reports/', ManageReportsView.as_view(), name='manage_reports'),
    path('report-detail/<int:report_id>/', ReportDetailView.as_view(), name='report_detail'),
    path('resolve-report/<int:report_id>/', ResolveReportView.as_view(), name='resolve_report'),
]
