from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from bookings.models import Booking
from core.services import notify


class Command(BaseCommand):
    help = "Email reminders for confirmed bookings starting within 24 hours"

    def handle(self, *a, **kw):
        now = timezone.now()
        for b in Booking.objects.filter(status="CONFIRMED", reminded=False, start__gt=now,
                                        start__lte=now + timedelta(hours=24)).select_related("customer", "business"):
            notify(b.customer, "Appointment reminder", f"{b.service_name} at {b.business.name}, {b.start:%a %d %b %H:%M}. Balance due: KSh {b.balance:.0f}.", urgent=True)
            b.reminded = True
            b.save(update_fields=["reminded"])
