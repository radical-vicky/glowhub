from django.conf import settings
from django.db import models


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "PENDING_PAYMENT"
        CONFIRMED = "CONFIRMED"
        RESCHEDULE_REQUESTED = "RESCHEDULE_REQUESTED"
        CANCELLED_BY_CUSTOMER = "CANCELLED_BY_CUSTOMER"
        CANCELLED_BY_PROVIDER = "CANCELLED_BY_PROVIDER"
        COMPLETED = "COMPLETED"
        NO_SHOW = "NO_SHOW"
        EXPIRED = "EXPIRED"

    # Explicit transition rules: a late callback can never revive EXPIRED/CANCELLED.
    TRANSITIONS = {
        "PENDING_PAYMENT": {"CONFIRMED", "EXPIRED", "CANCELLED_BY_CUSTOMER"},
        "CONFIRMED": {"RESCHEDULE_REQUESTED", "CANCELLED_BY_CUSTOMER", "CANCELLED_BY_PROVIDER",
                      "COMPLETED", "NO_SHOW"},
        "RESCHEDULE_REQUESTED": {"CONFIRMED", "CANCELLED_BY_CUSTOMER", "CANCELLED_BY_PROVIDER"},
    }

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings")
    business = models.ForeignKey("marketplace.Business", on_delete=models.PROTECT, related_name="bookings")
    service = models.ForeignKey("marketplace.Service", on_delete=models.PROTECT)
    start = models.DateTimeField(db_index=True)
    end = models.DateTimeField()
    status = models.CharField(max_length=24, choices=Status, default=Status.PENDING_PAYMENT, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    # Snapshots: provider edits never change an existing booking
    service_name = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.PositiveIntegerField()
    policy_snapshot = models.TextField()
    contact_name = models.CharField(max_length=120)
    contact_phone = models.CharField(max_length=15)
    notes = models.TextField(blank=True)
    reminded = models.BooleanField(default=False)
    staff = models.ForeignKey("marketplace.Staff", null=True, blank=True, on_delete=models.SET_NULL)
    branch = models.ForeignKey("marketplace.Branch", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["business", "start"])]

    @property
    def balance(self):
        return self.price - self.deposit_amount

    def transition(self, new_status, actor=None, note=""):
        if new_status not in self.TRANSITIONS.get(self.status, set()):
            raise ValueError(f"Illegal transition {self.status} -> {new_status}")
        BookingEvent.objects.create(booking=self, from_status=self.status,
                                    to_status=new_status, actor=actor, note=note)
        old, self.status = self.status, new_status
        self.save(update_fields=["status"])
        from core.hooks import on_booking_transition
        on_booking_transition(self, old, new_status)


class BookingEvent(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=24)
    to_status = models.CharField(max_length=24)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    note = models.CharField(max_length=200, blank=True)
    at = models.DateTimeField(auto_now_add=True)


class PaymentAttempt(models.Model):
    class Status(models.TextChoices):
        INITIATED = "INITIATED"
        PENDING = "PENDING"
        SUCCESS = "SUCCESS"
        FAILED = "FAILED"
        EXPIRED = "EXPIRED"
        REVERSED = "REVERSED"
        REFUND_PENDING = "REFUND_PENDING"
        REFUNDED = "REFUNDED"
        RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"

    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name="payments")
    phone = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=24, choices=Status, default=Status.INITIATED, db_index=True)
    checkout_request_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    mpesa_receipt = models.CharField(max_length=30, unique=True, null=True, blank=True)
    result_desc = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PaymentEvent(models.Model):
    """Append-only log of every callback/query received."""
    attempt = models.ForeignKey(PaymentAttempt, null=True, on_delete=models.PROTECT, related_name="events")
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)


class Refund(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED"
        APPROVED = "APPROVED"
        PROCESSED = "PROCESSED"
        REJECTED = "REJECTED"

    payment = models.ForeignKey(PaymentAttempt, on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=Status, default=Status.REQUESTED, db_index=True)
    reference = models.CharField(max_length=40, blank=True, help_text="M-Pesa reversal/transfer reference")
    decision_note = models.CharField(max_length=200, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [("approve_refund", "Can approve and process refunds")]
