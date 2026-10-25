from django.contrib import admin
from .models import Branch, Business, BusinessHours, BusinessPhoto, Category, Review, Service, Staff


class HoursInline(admin.TabularInline):
    model = BusinessHours
    extra = 0


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "status", "verified", "created_at")
    list_filter = ("status", "verified")
    search_fields = ("name", "slug", "owner__email")
    inlines = [HoursInline]
    actions = ["approve", "suspend"]

    @admin.action(description="Approve and verify selected providers")
    def approve(self, request, qs):
        from django.conf import settings
        from django.contrib import messages
        for b in qs:
            v = getattr(b, "verification", None)
            if settings.REQUIRE_VERIFICATION_TO_LIST and not (v and v.status == "APPROVED"):
                self.message_user(request, f"{b.name}: identity verification not approved yet.", messages.WARNING)
                continue
            b.status, b.verified = Business.Status.APPROVED, True
            b.save(update_fields=["status", "verified"])

    @admin.action(description="Suspend selected providers")
    def suspend(self, request, qs):
        qs.update(status=Business.Status.SUSPENDED)




@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}


admin.site.register(Service)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("business", "rating", "is_hidden", "created_at")
    list_filter = ("is_hidden",)
    actions = ["hide"]

    @admin.action(description="Hide selected reviews (moderation)")
    def hide(self, request, qs):
        from core.services import audit
        for r in qs:
            audit(request.user, "review.hidden", r.pk)
        qs.update(is_hidden=True)


admin.site.register(Branch)
admin.site.register(Staff, list_display=("name", "business", "branch", "is_active"))
admin.site.register(BusinessPhoto)
