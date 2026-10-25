from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone


class SupportTicket(models.Model):
    class Kind(models.TextChoices):
        TICKET = "TICKET", "Question"
        DISPUTE = "DISPUTE", "Dispute"

    class Status(models.TextChoices):
        OPEN = "OPEN"
        IN_REVIEW = "IN_REVIEW"
        RESOLVED = "RESOLVED"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tickets")
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=10, choices=Kind, default=Kind.TICKET)
    subject = models.CharField(max_length=160)
    body = models.TextField(max_length=3000)
    status = models.CharField(max_length=10, choices=Status, default=Status.OPEN, db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="assigned_tickets")
    decision = models.TextField(blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *a, **kw):
        if self.kind == self.Kind.DISPUTE and not self.due_at:
            self.due_at = timezone.now() + timedelta(days=3)
        super().save(*a, **kw)


class TicketReply(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)
