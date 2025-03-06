from django.urls import path
from .views import add_dorm, dorm_list ,dorm_detail, my_dorms , edit_dorm, delete_dorm

app_name = 'dormitory' 

urlpatterns = [
    path('add/', add_dorm, name='add_dorm'),
    path('list/', dorm_list, name='dorm_list'), 
    path('dormitory/<int:dorm_id>/', dorm_detail, name='dorm_detail'),
    path('my-dorms/', my_dorms, name='my_dorms'),
     path('dormitory/edit/<int:dorm_id>/', edit_dorm, name='edit_dorm'),
    path('dormitory/delete/<int:dorm_id>/', delete_dorm, name='delete_dorm'),
]