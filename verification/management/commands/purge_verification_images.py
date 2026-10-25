from datetime import timedelta
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from verification.models import ProviderVerification


class Command(BaseCommand):
    help = "Delete ID/selfie images after review + retention period (keeps the keyed hash for duplicate detection)"

    def handle(self, *a, **kw):
        cutoff = timezone.now() - timedelta(days=settings.VERIFICATION_RETENTION_DAYS)
        for v in ProviderVerification.objects.filter(reviewed_at__lt=cutoff, images_purged_at__isnull=True).exclude(status="PENDING"):
            for f in ("id_front", "id_back", "selfie"):
                if getattr(v, f):
                    getattr(v, f).delete(save=False)
            v.images_purged_at = timezone.now()
            v.save()
