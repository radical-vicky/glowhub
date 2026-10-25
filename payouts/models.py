from django.conf import settings
from django.db import models


class LedgerEntry(models.Model):
    """Append-only. Positive = owed to provider, negative = fee/refund/payout."""
    business = models.ForeignKey("marketplace.Business", on_delete=models.PROTECT, related_name="ledger")
    kind = models.CharField(max_length=20)  # DEPOSIT FEE REFUND FEE_REVERSAL PAYOUT PAYOUT_REVERSAL ADJUST
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.PROTECT)
    ref = models.CharField(max_length=60, unique=True, null=True, blank=True)  # idempotency key
    note = models.CharField(max_length=200, blank=True)
    available_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class Payout(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED"
        APPROVED = "APPROVED"
        PROCESSING = "PROCESSING"
        PAID = "PAID"
        FAILED = "FAILED"
        REJECTED = "REJECTED"

    business = models.ForeignKey("marketplace.Business", on_delete=models.PROTECT, related_name="payouts")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    phone = models.CharField(max_length=15)
    status = models.CharField(max_length=12, choices=Status, default=Status.REQUESTED, db_index=True)
    decision_note = models.CharField(max_length=200, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    originator_id = models.CharField(max_length=60, blank=True, db_index=True)
    receipt = models.CharField(max_length=30, blank=True)
    failure_reason = models.CharField(max_length=200, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [("approve_payout", "Can approve and pay provider payouts")]
