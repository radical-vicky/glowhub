from django.contrib import admin
from .models import AuditEvent, Notification, SiteSettings


class Locked(admin.ModelAdmin):
    def has_add_permission(self, r): return False
    def has_change_permission(self, r, obj=None): return False
    def has_delete_permission(self, r, obj=None): return False


@admin.register(AuditEvent)
class AuditAdmin(Locked):
    list_display = ("at", "actor", "action", "target")
    search_fields = ("action", "target", "actor__email")
    list_filter = ("action",)


@admin.register(Notification)
class NotificationAdmin(Locked):
    list_display = ("created_at", "user", "subject", "status", "attempts")
    list_filter = ("status",)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fields = ("background_image", "overlay_percent")

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
