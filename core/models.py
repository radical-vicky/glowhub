from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=60, db_index=True)
    target = models.CharField(max_length=120, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    at = models.DateTimeField(auto_now_add=True, db_index=True)


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    channel = models.CharField(max_length=10, default="EMAIL")  # EMAIL / SMS / WHATSAPP
    status = models.CharField(max_length=10, default="PENDING", db_index=True)  # PENDING/SENT/FAILED
    error = models.CharField(max_length=200, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class SiteSettings(models.Model):
    """One row (id 1), edited in the admin. Controls the site-wide background image."""
    background_image = models.ImageField(upload_to="site/", blank=True)
    overlay_percent = models.PositiveSmallIntegerField(
        default=75, validators=[MaxValueValidator(95)],
        help_text="0-95. How strongly the background is veiled so text stays readable.")

    class Meta:
        verbose_name_plural = "site settings"

    def save(self, *a, **kw):
        self.pk = 1
        super().save(*a, **kw)

    @classmethod
    def current(cls):
        return cls.objects.filter(pk=1).first()
