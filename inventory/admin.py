from django.contrib import admin
from .models import InventoryItem, StockMovement
admin.site.register(InventoryItem)
admin.site.register(StockMovement)
