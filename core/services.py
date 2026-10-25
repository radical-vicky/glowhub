from functools import wraps
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import HttpResponse
from .models import AuditEvent, Notification


def audit(actor, action, target="", **detail):
    AuditEvent.objects.create(actor=actor if getattr(actor, "pk", None) else None,
                              action=action, target=str(target)[:120], detail=detail)


def deliver(n):
    from .channels import send_sms, send_whatsapp
    n.attempts += 1
    try:
        if n.channel == "EMAIL":
            send_mail(n.subject, n.body, None, [n.user.email])
        else:
            phone = n.user.profile.phone
            (send_sms(phone, n.body) if n.channel == "SMS" else send_whatsapp(phone, n.body))
        n.status, n.error = "SENT", ""
    except Exception as e:  # transient failures are retried by `retry_notifications`
        n.status, n.error = "FAILED", str(e)[:200]
    n.save()


def notify(user, subject, body, urgent=False):
    """Email always; SMS/WhatsApp only for urgent items and only if the user verified a phone and opted in."""
    if not user:
        return
    if user.email:
        deliver(Notification.objects.create(user=user, subject=subject, body=body, channel="EMAIL"))
    if urgent:
        p = getattr(user, "profile", None)
        if p and p.phone_verified:
            text = f"GlowHub: {subject}. {body}"[:300]
            if p.sms_opt_in:
                deliver(Notification.objects.create(user=user, subject=subject, body=text, channel="SMS"))
            if p.whatsapp_opt_in and settings.WA_TEMPLATE:
                deliver(Notification.objects.create(user=user, subject=subject, body=text, channel="WHATSAPP"))


def rate_limit(key, limit, seconds=60):
    def deco(view):
        @wraps(view)
        def wrapper(request, *a, **kw):
            if request.method == "POST":
                ident = request.user.pk if request.user.is_authenticated else request.META.get("REMOTE_ADDR")
                ck = f"rl:{key}:{ident}"
                cache.add(ck, 0, seconds)
                if cache.incr(ck) > limit:
                    return HttpResponse("Too many requests. Please wait a minute and try again.", status=429)
            return view(request, *a, **kw)
        return wrapper
    return deco
