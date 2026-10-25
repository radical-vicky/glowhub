from django.conf import settings
from django.db import models


def private_storage():
    from django.core.files.storage import FileSystemStorage
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)  # never under MEDIA_ROOT / never public


class ProviderVerification(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        APPROVED = "APPROVED"
        REJECTED = "REJECTED"

    class DocType(models.TextChoices):
        NATIONAL_ID = "NATIONAL_ID", "National ID"
        PASSPORT = "PASSPORT", "Passport"

    business = models.OneToOneField("marketplace.Business", on_delete=models.CASCADE, related_name="verification")
    doc_type = models.CharField(max_length=12, choices=DocType)
    full_name = models.CharField(max_length=120)
    id_hash = models.CharField(max_length=64, unique=True)   # keyed hash: blocks one ID on many accounts
    id_last4 = models.CharField(max_length=4)
    id_front = models.FileField(upload_to="kyc/", storage=private_storage)
    id_back = models.FileField(upload_to="kyc/", storage=private_storage, blank=True)
    selfie = models.FileField(upload_to="kyc/", storage=private_storage)
    challenge_code = models.CharField(max_length=4)           # written on paper and held up in the selfie
    consent_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING, db_index=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reject_reason = models.CharField(max_length=200, blank=True)
    images_purged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        permissions = [("review_verification", "Can review identity verification")]
