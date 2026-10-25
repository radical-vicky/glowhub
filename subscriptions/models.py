from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=40, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    period_days = models.PositiveIntegerField(default=30)
    max_services = models.PositiveIntegerField(default=5)
    inventory_enabled = models.BooleanField(default=False)
    reports_enabled = models.BooleanField(default=False)
    staff_enabled = models.BooleanField(default=False)
    branches_enabled = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Subscription(models.Model):
    class Status(models.TextChoices):
        TRIAL = "TRIAL"
        ACTIVE = "ACTIVE"
        CANCELLED = "CANCELLED"

    business = models.OneToOneField("marketplace.Business", on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=10, choices=Status, default=Status.TRIAL)
    period_end = models.DateTimeField()

    @property
    def in_grace(self):
        now = timezone.now()
        return self.period_end < now <= self.period_end + timedelta(days=settings.SUBSCRIPTION_GRACE_DAYS)

    @property
    def entitled(self):
        """Server-side entitlement check used by every protected feature."""
        if self.status == self.Status.CANCELLED and self.period_end < timezone.now():
            return False
        return timezone.now() <= self.period_end + timedelta(days=settings.SUBSCRIPTION_GRACE_DAYS)


class SubscriptionPayment(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name="payments")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone = models.CharField(max_length=15)
    status = models.CharField(max_length=12, default="PENDING", db_index=True)  # PENDING/SUCCESS/FAILED
    checkout_request_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    receipt = models.CharField(max_length=30, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
