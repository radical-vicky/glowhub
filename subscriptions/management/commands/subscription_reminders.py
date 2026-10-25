from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.services import notify
from subscriptions.models import Subscription


class Command(BaseCommand):
    help = "Email providers whose plan ends within 3 days or has lapsed"

    def handle(self, *a, **kw):
        now = timezone.now()
        for s in Subscription.objects.select_related("business__owner").filter(period_end__lt=now + timedelta(days=3)):
            msg = "has ended. Renew to keep inventory, reports and new services." if s.period_end < now else "ends soon. Renew to avoid interruption."
            notify(s.business.owner, "Your GlowHub plan", f"Your {s.plan.name} plan {msg}")
