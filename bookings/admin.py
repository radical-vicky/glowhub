from django.contrib import admin
from core.services import audit, notify
from .models import Booking, BookingEvent, PaymentAttempt, PaymentEvent, Refund


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "business", "customer", "start", "status")
    list_filter = ("status",)


class ReadOnly(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


for m in (PaymentAttempt, PaymentEvent, BookingEvent):
    admin.site.register(m, ReadOnly)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("id", "payment", "amount", "status", "created_at")
    list_filter = ("status",)
    fields = ("payment", "amount", "reason", "status", "reference", "decision_note")

    def get_readonly_fields(self, request, obj=None):
        base = ("payment", "amount", "reason")
        return base if request.user.has_perm("bookings.approve_refund") else self.fields

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if not request.user.has_perm("bookings.approve_refund"):
            return
        if obj.status in ("APPROVED", "PROCESSED", "REJECTED") and not obj.decision_note:
            self.message_user(request, "A reason is required for every refund decision.", level="ERROR")
            return
        obj.decided_by = request.user
        super().save_model(request, obj, form, change)
        if obj.status == "PROCESSED":
            from payouts.services import reverse_booking
            from rewards.services import clawback_booking
            reverse_booking(obj.payment.booking)
            clawback_booking(obj.payment.booking)
            obj.payment.status = PaymentAttempt.Status.REFUNDED
            obj.payment.save(update_fields=["status"])
            notify(obj.payment.booking.customer, "Your refund", f"KSh {obj.amount:.0f} has been refunded.")
        audit(request.user, f"refund.{obj.status.lower()}", obj.pk, note=obj.decision_note, amount=str(obj.amount))

