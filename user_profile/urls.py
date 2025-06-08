from django.urls import path
from .views import ProfileDetailView, ProfileUpdateView, ToggleFavoriteDormView

app_name = "user_profile"  # Make sure this matches in `reverse()`

urlpatterns = [
    path("profile/", ProfileDetailView.as_view(), name="profile"),
    path("profile/edit/", ProfileUpdateView.as_view(), name="edit_profile"),
    path("favorite/toggle/<int:dorm_id>/", ToggleFavoriteDormView.as_view(), name="toggle_favorite"),
]