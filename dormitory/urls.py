from django.urls import path
from .views import (
    AddDormView, DormListView, DormDetailView,
    MyDormsView, EditDormView, DeleteDormView,
    RoommateListView, RoommateCreateView , RoommateDetailView,
    RoommateUpdateView, RoommateDeleteView,ReviewListView, 
    ReviewCreateView, ReviewUpdateView, ReviewDeleteView, ReservationCreateView ,ReservationPaymentView, ChatView,
    LandlordReservationsView, UpdateReservationStatusView, ReservationDetailView, send_reservation_message, update_reservation_status,
    StudentReservationsView
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

    path("dormitory/<int:dorm_id>/reserve/", ReservationCreateView.as_view(), name="reserve_dorm"),
    path("chat/", ChatView.as_view(), name="chat"),
    path('reservation/payment/<int:reservation_id>/', ReservationPaymentView.as_view(), name='reservation_payment'),
    path('landlord/reservations/', LandlordReservationsView.as_view(), name='landlord_reservations'),
    path('my-reservations/', StudentReservationsView.as_view(), name='student_reservations'),
    path('landlord/reservations/<int:reservation_id>/update/', UpdateReservationStatusView.as_view(), name='update_reservation_status'),
    path('reservation/<int:pk>/', ReservationDetailView.as_view(), name='reservation_detail'),
    path('reservation/<int:reservation_id>/message/', send_reservation_message, name='send_message'),
    path('reservation/<int:reservation_id>/status/', update_reservation_status, name='update_status'),
]
