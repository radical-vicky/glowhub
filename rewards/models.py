from django.conf import settings
from django.db import models


class DiamondEntry(models.Model):
    """Append-only ledger. Positive = earned, negative = withdrawn/clawed back."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="diamond_entries")
    amount = models.IntegerField()
    kind = models.CharField(max_length=24)
    ref = models.CharField(max_length=60, unique=True, null=True, blank=True)  # idempotency: one reward per event
    note = models.CharField(max_length=200, blank=True)
    available_at = models.DateTimeField()  # earnings are held (default 7 days) so refunds/fraud can be caught
    created_at = models.DateTimeField(auto_now_add=True)


class Referral(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        REWARDED = "REWARDED"
        REJECTED = "REJECTED"

    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referrals")
    referee = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referred_by")
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rewarded_at = models.DateTimeField(null=True, blank=True)


class Withdrawal(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED"
        APPROVED = "APPROVED"
        PROCESSING = "PROCESSING"
        PAID = "PAID"
        FAILED = "FAILED"
        REJECTED = "REJECTED"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="withdrawals")
    diamonds = models.PositiveIntegerField()
    kes = models.DecimalField(max_digits=10, decimal_places=2)
    phone = models.CharField(max_length=15)
    status = models.CharField(max_length=12, choices=Status, default=Status.REQUESTED, db_index=True)
    decision_note = models.CharField(max_length=200, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    originator_id = models.CharField(max_length=60, blank=True, db_index=True)
    receipt = models.CharField(max_length=30, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [("approve_withdrawal", "Can approve and pay reward withdrawals")]
