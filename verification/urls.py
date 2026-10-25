from django.urls import path
from . import views as v

urlpatterns = [
    path("", v.submit, name="verification"),
    path("file/<int:pk>/<str:field>/", v.private_file, name="verification_file"),
]
