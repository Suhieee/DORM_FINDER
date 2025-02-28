from django.urls import path
from .views import add_dorm, dorm_list ,dorm_detail, my_dorms

app_name = 'dormitory'  # ✅ Add this line

urlpatterns = [
    path('add/', add_dorm, name='add_dorm'),
    path('list/', dorm_list, name='dorm_list'), 
    path('dormitory/<int:dorm_id>/', dorm_detail, name='dorm_detail'),
    path('my-dorms/', my_dorms, name='my_dorms'),
]