from django.urls import path
from .views import (
    AddDormView, DormListView, DormDetailView,
    MyDormsView, EditDormView, DeleteDormView,
    RoommateListView, RoommateCreateView , RoommateDetailView,
    RoommateUpdateView, RoommateDeleteView,ReviewListView, 
    ReviewCreateView, ReviewUpdateView, ReviewDeleteView

)

app_name = "dormitory"

urlpatterns = [
    path("add/", AddDormView.as_view(), name="add_dorm"),
    path("list/", DormListView.as_view(), name="dorm_list"),
    path("dormitory/<int:pk>/", DormDetailView.as_view(), name="dorm_detail"),
    path("my-dorms/", MyDormsView.as_view(), name="my_dorms"),
    path("dormitory/edit/<int:pk>/", EditDormView.as_view(), name="edit_dorm"),
    path("dormitory/delete/<int:pk>/", DeleteDormView.as_view(), name="delete_dorm"),


    path("roommate-finder/", RoommateListView.as_view(), name="roommate_list"),
    path("roommate-finder/add/", RoommateCreateView.as_view(), name="add_roommate"),
    path("roommate-finder/<int:pk>/", RoommateDetailView.as_view(), name="roommate_detail"),
    path("roommate/edit/<int:pk>/", RoommateUpdateView.as_view(), name="roommate_edit"),
    path("roommate/delete/<int:pk>/", RoommateDeleteView.as_view(), name="roommate_delete"),

    path("dormitory/<int:dorm_id>/reviews/", ReviewListView.as_view(), name="review_list"),
    path("dormitory/<int:dorm_id>/reviews/add/", ReviewCreateView.as_view(), name="add_review"),
    path("dorms/<int:dorm_id>/reviews/<int:pk>/edit/", ReviewUpdateView.as_view(), name="edit_review"),
    path("dorms/<int:dorm_id>/reviews/<int:pk>/delete/", ReviewDeleteView.as_view(), name="delete_review"),

]
