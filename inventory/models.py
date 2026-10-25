from django.conf import settings
from django.db import models


class InventoryItem(models.Model):
    business = models.ForeignKey("marketplace.Business", on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=120)
    sku = models.CharField(max_length=40, blank=True)
    quantity = models.IntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=5)
    unit = models.CharField(max_length=20, default="pcs")
    is_consumable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gte=0), name="stock_not_negative")]

    @property
    def status(self):
        return "Out" if self.quantity == 0 else "Low Stock" if self.quantity <= self.reorder_level else "In Stock"


class StockMovement(models.Model):
    class Kind(models.TextChoices):
        RECEIPT = "RECEIPT"
        SALE = "SALE"
        CONSUMED = "CONSUMED"
        DAMAGE = "DAMAGE"
        RETURN = "RETURN"
        ADJUST = "ADJUST"

    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="movements")
    kind = models.CharField(max_length=10, choices=Kind)
    delta = models.IntegerField()  # signed; append-only (corrections are new rows)
    reason = models.CharField(max_length=200, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    at = models.DateTimeField(auto_now_add=True)
