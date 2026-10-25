from allauth.account.signals import user_signed_up
from django.dispatch import receiver
from .models import UserProfile


@receiver(user_signed_up)
def on_signup(request, user, **kw):
    UserProfile.objects.get_or_create(user=user)
    code = request.session.get("ref") if request else None
    referrer = UserProfile.objects.filter(referral_code=code).exclude(user=user).first() if code else None
    if referrer:
        from rewards.models import Referral
        Referral.objects.get_or_create(referee=user, defaults={"referrer": referrer.user})
