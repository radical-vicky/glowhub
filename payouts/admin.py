from django.contrib import admin
from .models import LedgerEntry, Payout
from .services import ALLOWED, finalize, reverse_payout, send_payout


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("id", "business", "amount", "phone", "status", "requested_at")
    list_filter = ("status",)
    fields = ("business", "amount", "phone", "status", "decision_note", "receipt", "failure_reason", "originator_id")
    readonly_fields = ("business", "amount", "phone", "failure_reason", "originator_id")

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_change_permission(self, request, obj=None): return request.user.has_perm("payouts.approve_payout")

    def save_model(self, request, obj, form, change):
        old = Payout.objects.get(pk=obj.pk).status
        if obj.status != old and obj.status not in ALLOWED.get(old, set()):
            self.message_user(request, f"{old} cannot change to {obj.status}.", level="ERROR")
            return
        if obj.status != old and not obj.decision_note:
            self.message_user(request, "A note is required for every payout decision.", level="ERROR")
            return
        obj.decided_by = request.user
        super().save_model(request, obj, form, change)
        finalize(obj, old, request.user, send=send_payout, reverse=reverse_payout)


@admin.register(LedgerEntry)
class LedgerAdmin(admin.ModelAdmin):
    list_display = ("created_at", "business", "kind", "amount", "available_at")
    list_filter = ("kind",)
    search_fields = ("business__name", "ref")

    def has_add_permission(self, r): return False
    def has_change_permission(self, r, obj=None): return False
    def has_delete_permission(self, r, obj=None): return False
