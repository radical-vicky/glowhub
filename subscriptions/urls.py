from django.urls import path
from . import views as v

urlpatterns = [
    path("", v.plans, name="subscription"),
    path("mpesa/callback/<str:secret>/", v.callback, name="sub_callback"),
]
