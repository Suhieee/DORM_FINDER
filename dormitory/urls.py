from django.urls import path
from .views import (
    AddDormView, DormListView, DormDetailView,
    MyDormsView, EditDormView, DeleteDormView,
    RoommateListView, RoommateCreateView, RoommateDetailView,
    RoommateUpdateView, RoommateDeleteView, ReviewListView, 
    ReviewCreateView, ReviewUpdateView, ReviewDeleteView,
    ReservationCreateView, LandlordReservationsView, tenantReservationsView,
    MessagesView, SendMessageView, CheckNewMessagesView, UpdateReservationStatusView,
    ManageRoomsView, PublicDormListView, PublicDormDetailView, 
    PublicRoommateListView, PublicRoommateDetailView, HomePageView
)
from .payment_views import (
    payment_booking_intent, payment_gateway_checkout, payment_webhook,
    payment_success, payment_failure, cancel_reservation_with_refund,
    paymongo_gcash_checkout, paymongo_success, paymongo_failure, paymongo_webhook,
    paymongo_checkout, checkout_success
)
from . import views
from . import chatbot_views

app_name = "dormitory"

urlpatterns = [
    # Home page
    path("", HomePageView.as_view(), name="home"),
    
    # Public URLs (no login required)
    path("browse/", PublicDormListView.as_view(), name="public_dorm_list"),
    path("dorm/<int:pk>/", PublicDormDetailView.as_view(), name="public_dorm_detail"),
    path("roommates/", PublicRoommateListView.as_view(), name="public_roommate_list"),
    path("roommate/<int:pk>/", PublicRoommateDetailView.as_view(), name="public_roommate_detail"),
    
    # Protected URLs (login required)
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
    path('my-reservations/', tenantReservationsView.as_view(), name='tenant_reservations'),
    path('landlord/reservations/', LandlordReservationsView.as_view(), name='landlord_reservations'),

    # Messaging URLs
    path('messages/', MessagesView.as_view(), name='messages'),
    path('messages/send/', SendMessageView.as_view(), name='send_message'),
    path('messages/check-new/<int:reservation_id>/', CheckNewMessagesView.as_view(), name='check_new_messages'),
    path('reservation/<int:reservation_id>/update-status/', UpdateReservationStatusView.as_view(), name='update_reservation_status'),

    # Roommate matching URLs
    path('roommate-matches/', views.RoommateMatchesView.as_view(), name='roommate_matches'),
    path('roommate-match/initiate/<int:target_id>/', views.InitiateRoommateMatchView.as_view(), name='initiate_match'),
    path('roommate-match/status/<int:match_id>/', views.UpdateRoommateMatchStatusView.as_view(), name='update_match_status'),
    path('roommate-match/chat/<int:match_id>/', views.SendRoommateChatMessageView.as_view(), name='send_roommate_message'),
    path('roommate-message/<int:message_id>/react/', views.ToggleMessageReactionView.as_view(), name='toggle_message_reaction'),

    # Room management for landlords
    path('dorms/<int:dorm_id>/rooms/', ManageRoomsView.as_view(), name='manage_rooms'),
    
    # Move-in checklist
    path('reservation/<int:reservation_id>/update-checklist/', views.update_checklist, name='update_checklist'),
    
    # Payment Gateway URLs
    path('payment/booking-intent/<int:reservation_id>/', payment_booking_intent, name='payment_booking_intent'),
    path('payment/checkout/<int:reservation_id>/', payment_gateway_checkout, name='payment_gateway_checkout'),
    path('payment/webhook/', payment_webhook, name='payment_webhook'),
    path('payment/success/<int:reservation_id>/', payment_success, name='payment_success'),
    path('payment/failure/<int:reservation_id>/', payment_failure, name='payment_failure'),
    path('payment/cancel-with-refund/<int:reservation_id>/', cancel_reservation_with_refund, name='cancel_reservation_with_refund'),
    
    # PayMongo GCash Payment URLs (Sources API - Legacy)
    path('payment/gcash/checkout/<int:reservation_id>/', paymongo_gcash_checkout, name='paymongo_gcash_checkout'),
    path('payment/gcash/success/<int:reservation_id>/', paymongo_success, name='paymongo_success'),
    path('payment/gcash/failure/<int:reservation_id>/', paymongo_failure, name='paymongo_failure'),
    path('payment/gcash/webhook/', paymongo_webhook, name='paymongo_webhook'),
    
    # PayMongo Checkout Sessions URLs (RECOMMENDED - Full UI)
    path('payment/checkout-session/<int:reservation_id>/', paymongo_checkout, name='paymongo_checkout'),
    path('payment/checkout-success/<int:reservation_id>/', checkout_success, name='checkout_success'),
    
    # Chatbot AI Assistant URLs
    path('chatbot/message/', chatbot_views.chatbot_message, name='chatbot_message'),
    path('chatbot/reset/', chatbot_views.chatbot_reset, name='chatbot_reset'),
    path('chatbot/save-faq/', chatbot_views.chatbot_save_faq, name='chatbot_save_faq'),
    
    # Cron Job Endpoint for Production (Railway)
    path('cron/cancel-expired/', views.cron_cancel_expired, name='cron_cancel_expired'),
]
