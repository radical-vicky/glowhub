import secrets
from django.conf import settings
from django.db import models


def _code():
    return "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=15, blank=True, db_index=True)
    phone_verified = models.BooleanField(default=False)
    sms_opt_in = models.BooleanField(default=True)
    whatsapp_opt_in = models.BooleanField(default=False)
    marketing_opt_in = models.BooleanField(default=False)  # separate from essential notices
    referral_code = models.CharField(max_length=10, unique=True, default=_code)
    rewards_frozen = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["phone"], condition=models.Q(phone_verified=True),
                                               name="unique_verified_phone")]


class PhoneOTP(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
