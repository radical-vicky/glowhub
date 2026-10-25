from django.urls import path
from . import views as v

urlpatterns = [
    path("<int:booking_id>/", v.thread, name="thread"),
    path("report/<int:message_id>/", v.report, name="report_message"),
]
