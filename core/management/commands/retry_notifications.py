from django.core.management.base import BaseCommand
from core.models import Notification
from core.services import deliver


class Command(BaseCommand):
    help = "Retry failed email notifications (max 5 attempts)"

    def handle(self, *a, **kw):
        for n in Notification.objects.filter(status="FAILED", attempts__lt=5).select_related("user"):
            deliver(n)
