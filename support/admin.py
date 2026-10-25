from django.contrib import admin
from .models import SupportTicket, TicketReply
from core.services import audit, notify


class ReplyInline(admin.TabularInline):
    model = TicketReply
    extra = 1
    fields = ("body",)


@admin.register(SupportTicket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "subject", "user", "status", "assigned_to", "due_at")
    list_filter = ("kind", "status", "assigned_to")
    search_fields = ("subject", "user__email")
    inlines = [ReplyInline]

    def save_formset(self, request, form, formset, change):
        for obj in formset.save(commit=False):
            if isinstance(obj, TicketReply) and not obj.pk:
                obj.author = request.user
                obj.save()
                notify(obj.ticket.user, f"Reply to your request #{obj.ticket_id}", obj.body)
        formset.save_m2m()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and ("status" in form.changed_data or "decision" in form.changed_data):
            audit(request.user, "ticket.updated", obj.pk, status=obj.status)
