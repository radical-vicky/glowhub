import hashlib, hmac, secrets
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from bookings.mpesa import normalize_phone
from core.channels import send_sms
from .models import PhoneOTP, UserProfile


def get_profile(user):
    return UserProfile.objects.get_or_create(user=user)[0]


def _h(code):
    return hmac.new(settings.SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest()


def send_otp(user, raw_phone):
    phone = normalize_phone(raw_phone)
    if UserProfile.objects.filter(phone=phone, phone_verified=True).exclude(user=user).exists():
        raise ValueError("This number is already linked to another account.")
    if PhoneOTP.objects.filter(user=user, created_at__gt=timezone.now() - timedelta(hours=1)).count() >= 3:
        raise ValueError("Too many codes requested. Try again in an hour.")
    code = f"{secrets.randbelow(10**6):06d}"
    PhoneOTP.objects.create(user=user, phone=phone, code_hash=_h(code), expires_at=timezone.now() + timedelta(minutes=10))
    send_sms(phone, f"Your GlowHub code is {code}. It expires in 10 minutes. Never share it.")


def verify_otp(user, code):
    otp = PhoneOTP.objects.filter(user=user, expires_at__gt=timezone.now()).order_by("-created_at").first()
    if not otp or otp.attempts >= 5:
        raise ValueError("That code has expired. Request a new one.")
    otp.attempts += 1
    otp.save(update_fields=["attempts"])
    if not hmac.compare_digest(otp.code_hash, _h(code)):
        raise ValueError("That code is incorrect.")
    p = get_profile(user)
    p.phone, p.phone_verified = otp.phone, True
    p.save()
    PhoneOTP.objects.filter(user=user).delete()
    try:
        from rewards.services import on_phone_verified
        on_phone_verified(user)
    except Exception:
        pass
