from django import forms
from .models import InventoryItem, StockMovement


class ItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ["name", "sku", "reorder_level", "unit", "is_consumable"]


class MovementForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ["kind", "delta", "reason"]
