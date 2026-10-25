from django.urls import path
from . import views as v

urlpatterns = [
    path("service/<int:service_id>/", v.book_service, name="book"),
    path("<int:booking_id>/pay/", v.pay, name="pay"),
    path("<int:booking_id>/status/", v.pay_status, name="pay_status"),
    path("<int:booking_id>/confirmed/", v.confirmation, name="confirmation"),
    path("<int:booking_id>/cancel/", v.cancel, name="cancel"),
    path("manage/", v.provider_bookings, name="provider_bookings"),
    path("manage/<int:booking_id>/<str:action>/", v.provider_action, name="provider_action"),
    path("mpesa/callback/<str:secret>/", v.mpesa_callback, name="mpesa_callback"),
]
