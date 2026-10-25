from django.urls import path
from . import views as v

urlpatterns = [
    path("", v.item_list, name="inventory"),
    path("new/", v.item_create, name="item_create"),
    path("<int:pk>/move/", v.move_stock, name="move_stock"),
]
