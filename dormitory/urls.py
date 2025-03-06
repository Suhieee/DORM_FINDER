from django.urls import path
from .views import (
    AddDormView, DormListView, DormDetailView,
    MyDormsView, EditDormView, DeleteDormView
)

app_name = "dormitory"

urlpatterns = [
    path("add/", AddDormView.as_view(), name="add_dorm"),
    path("list/", DormListView.as_view(), name="dorm_list"),
    path("dormitory/<int:pk>/", DormDetailView.as_view(), name="dorm_detail"),
    path("my-dorms/", MyDormsView.as_view(), name="my_dorms"),
    path("dormitory/edit/<int:pk>/", EditDormView.as_view(), name="edit_dorm"),
    path("dormitory/delete/<int:pk>/", DeleteDormView.as_view(), name="delete_dorm"),
]
