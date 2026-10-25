from django.conf import settings
from django.db import models


class Message(models.Model):
    booking = models.ForeignKey("bookings.Booking", on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField(max_length=1000)
    reported = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
