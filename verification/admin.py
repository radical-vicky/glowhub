from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from core.services import audit, notify
from .models import ProviderVerification


@admin.register(ProviderVerification)
class VerificationAdmin(admin.ModelAdmin):
    list_display = ("business", "doc_type", "id_last4", "status", "submitted_at")
    list_filter = ("status", "doc_type")
    fields = ("business", "doc_type", "full_name", "id_last4", "challenge_code", "front", "back", "face",
              "consent_at", "status", "reject_reason")
    readonly_fields = ("business", "doc_type", "full_name", "id_last4", "challenge_code", "front", "back", "face", "consent_at")

    def _link(self, obj, field, label):
        if not getattr(obj, field):
            return "Deleted or not provided"
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', reverse("verification_file", args=[obj.pk, field]), label)

    @admin.display(description="ID front")
    def front(self, o): return self._link(o, "id_front", "View (audited)")

    @admin.display(description="ID back")
    def back(self, o): return self._link(o, "id_back", "View (audited)")

    @admin.display(description="Selfie (must show the code on paper)")
    def face(self, o): return self._link(o, "selfie", "View (audited)")

    def _ok(self, request):
        return request.user.has_perm("verification.review_verification")

    def has_module_permission(self, request): return self._ok(request)
    def has_view_permission(self, request, obj=None): return self._ok(request)
    def has_change_permission(self, request, obj=None): return self._ok(request)
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False

    def save_model(self, request, obj, form, change):
        old = ProviderVerification.objects.get(pk=obj.pk).status
        if obj.status == "REJECTED" and not obj.reject_reason:
            self.message_user(request, "Give a reason when rejecting.", level="ERROR")
            return
        obj.reviewed_by, obj.reviewed_at = request.user, timezone.now()
        super().save_model(request, obj, form, change)
        if obj.status != old:
            b = obj.business
            if obj.status == "APPROVED":
                b.verified = True
                if b.status == "PENDING":
                    b.status = "APPROVED"
                b.save(update_fields=["verified", "status"])
                try:
                    from rewards.services import on_subscription_paid
                    on_subscription_paid(b)
                except Exception:
                    pass
                notify(b.owner, "Identity verified", "Your business is verified and listed.", urgent=True)
            elif obj.status == "REJECTED":
                notify(b.owner, "Verification needs attention", f"Reason: {obj.reject_reason}. You can resubmit.", urgent=True)
            audit(request.user, f"verification.{obj.status.lower()}", obj.pk, reason=obj.reject_reason)
