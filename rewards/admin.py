from django import forms
from django.contrib import admin
from core.services import audit
from payouts.services import ALLOWED, finalize
from .models import DiamondEntry, Referral, Withdrawal
from .services import reverse_withdrawal, send_withdrawal


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "diamonds", "kes", "phone", "status", "requested_at")
    list_filter = ("status",)
    fields = ("user", "diamonds", "kes", "phone", "status", "decision_note", "receipt", "originator_id")
    readonly_fields = ("user", "diamonds", "kes", "phone", "originator_id")

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_change_permission(self, request, obj=None): return request.user.has_perm("rewards.approve_withdrawal")

    def save_model(self, request, obj, form, change):
        old = Withdrawal.objects.get(pk=obj.pk).status
        if obj.status != old and obj.status not in ALLOWED.get(old, set()):
            self.message_user(request, f"{old} cannot change to {obj.status}.", level="ERROR")
            return
        if obj.status != old and not obj.decision_note:
            self.message_user(request, "A note is required for every decision.", level="ERROR")
            return
        obj.decided_by = request.user
        super().save_model(request, obj, form, change)
        finalize(obj, old, request.user, send=send_withdrawal, reverse=reverse_withdrawal)


class AdjustForm(forms.ModelForm):
    class Meta:
        model = DiamondEntry
        fields = ["user", "amount", "note"]


@admin.register(DiamondEntry)
class DiamondAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "amount", "kind", "available_at")
    list_filter = ("kind",)
    search_fields = ("user__email", "ref")
    form = AdjustForm

    def has_change_permission(self, r, obj=None): return False
    def has_delete_permission(self, r, obj=None): return False

    def save_model(self, request, obj, form, change):  # manual adjustments are ledger entries, never edits
        from django.utils import timezone
        obj.kind, obj.available_at = "ADJUST", timezone.now()
        super().save_model(request, obj, form, change)
        audit(request.user, "diamonds.adjusted", obj.pk, amount=obj.amount, note=obj.note)


admin.site.register(Referral, list_display=("referrer", "referee", "status", "rewarded_at"), list_filter=("status",))
