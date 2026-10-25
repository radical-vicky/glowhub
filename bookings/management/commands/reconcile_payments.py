from django.core.management.base import BaseCommand
from bookings.payments import reconcile_pending


class Command(BaseCommand):
    help = "Query Safaricom for stale pending payments and alert staff to discrepancies"

    def handle(self, *a, **kw):
        reconcile_pending()
