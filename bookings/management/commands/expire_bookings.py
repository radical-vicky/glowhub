from django.core.management.base import BaseCommand
from bookings.payments import expire_stale_bookings


class Command(BaseCommand):
    help = "Expire unpaid bookings whose payment window has elapsed"

    def handle(self, *a, **kw):
        expire_stale_bookings()
