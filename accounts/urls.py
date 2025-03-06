from django.urls import path
from .views import register, dashboard, approve_dorm, reject_dorm , review_dorm, user_login
from django.contrib.auth import views as auth_views


app_name = "accounts"

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', user_login, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('dashboard/', dashboard, name='dashboard'),

    path('approve-dorm/<int:dorm_id>/', approve_dorm, name='approve_dorm'),
    path('reject-dorm/<int:dorm_id>/', reject_dorm, name='reject_dorm'),
    path('review-dorm/<int:dorm_id>/', review_dorm, name='review_dorm'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
]

