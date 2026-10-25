from django.urls import path
from . import views as v

urlpatterns = [
    path("", v.earnings, name="earnings"),
    path("mpesa/result/<str:secret>/", v.b2c_result),
    path("mpesa/timeout/<str:secret>/", v.b2c_timeout),
]
