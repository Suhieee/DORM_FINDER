from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
        RegisterView, LoginView, DashboardView,
        ApproveDormView, RejectDormView, ReviewDormView , RoleBasedRedirectView , LogoutView , MarkNotificationAsReadView, NotificationListView
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
]
