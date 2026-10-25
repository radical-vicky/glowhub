from django.urls import path
from . import views as v

urlpatterns = [path("", v.tickets, name="tickets"), path("<int:pk>/", v.ticket, name="ticket")]
