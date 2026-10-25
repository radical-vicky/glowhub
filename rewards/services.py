import logging, secrets
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounts.models import UserProfile
from accounts.services import get_profile
from bookings import mpesa
from core.services import audit, notify
from .models import DiamondEntry, Referral, Withdrawal

log = logging.getLogger(__name__)
R = lambda: settings.REWARDS
CAP_EXEMPT = ("REFERRAL", "REFERRAL_BONUS")  # referrals have their own monthly cap


def award(user, amount, kind, ref, note=""):
    """Idempotent (one reward per `ref`), capped per day, never for frozen accounts."""
    if not user or not settings.REWARDS_ENABLED or get_profile(user).rewards_frozen:
        return None
    existing = DiamondEntry.objects.filter(ref=ref).first()
    if existing:
        return existing
    if kind not in CAP_EXEMPT:
        earned = DiamondEntry.objects.filter(user=user, amount__gt=0, created_at__date=timezone.localdate()
                                             ).exclude(kind__in=CAP_EXEMPT).aggregate(s=Sum("amount"))["s"] or 0
        if earned + amount > R()["DAILY_CAP"]:
            return None
    return DiamondEntry.objects.get_or_create(ref=ref, defaults=dict(
        user=user, amount=amount, kind=kind, note=note,
        available_at=timezone.now() + timedelta(days=R()["HOLD_DAYS"])))[0]


def balance(user):
    q = DiamondEntry.objects.filter(user=user)
    total = q.aggregate(s=Sum("amount"))["s"] or 0
    avail = q.filter(available_at__lte=timezone.now()).aggregate(s=Sum("amount"))["s"] or 0
    return {"available": avail, "pending": total - avail}


def clawback_booking(booking):
    for ref in (f"bk:{booking.pk}", f"pbk:{booking.pk}"):
        e = DiamondEntry.objects.filter(ref=ref).first()
        if e:
            DiamondEntry.objects.get_or_create(ref=f"rev:{ref}", defaults=dict(
                user=e.user, amount=-e.amount, kind="CLAWBACK", available_at=e.available_at, note="Booking cancelled or refunded"))


def on_booking_completed(booking):
    if booking.customer_id == booking.business.owner_id:  # no self-dealing
        return
    if booking.deposit_amount < R()["MIN_BOOKING_KES"] or not booking.payments.filter(status="SUCCESS").exists():
        return
    award(booking.customer, R()["BOOKING_CUSTOMER"], "BOOKING", f"bk:{booking.pk}", "Completed booking")
    award(booking.business.owner, R()["BOOKING_PROVIDER"], "BOOKING", f"pbk:{booking.pk}", "Completed booking")
    _reward_referral(booking.customer, "customer")


def on_subscription_paid(business):
    """Provider referrals pay out only when the provider is ID-verified AND has paid a subscription."""
    if business.verified and business.subscription.payments.filter(status="SUCCESS").exists():
        _reward_referral(business.owner, "provider")


def on_review(user, booking):
    award(user, R()["REVIEW"], "REVIEW", f"rv:{booking.pk}", "Left a review")


def on_phone_verified(user):
    award(user, R()["PROFILE"], "PROFILE", f"prof:{user.pk}", "Verified phone number")


def _reward_referral(referee, role):
    ref = Referral.objects.filter(referee=referee, status="PENDING").first()
    if not ref or ref.referrer_id == referee.pk or not get_profile(referee).phone_verified:
        return
    month_ago = timezone.now() - timedelta(days=30)
    if Referral.objects.filter(referrer=ref.referrer, status="REWARDED", rewarded_at__gte=month_ago).count() >= R()["REFERRAL_MONTHLY_CAP"]:
        return
    with transaction.atomic():
        r = Referral.objects.select_for_update().get(pk=ref.pk)
        if r.status != "PENDING":
            return
        amt = R()["REFERRER_PROVIDER"] if role == "provider" else R()["REFERRER_CUSTOMER"]
        e = award(r.referrer, amt, "REFERRAL", f"ref:{referee.pk}", "Referral completed their first paid booking" if role == "customer" else "Referred provider is verified and subscribed")
        award(referee, R()["REFEREE_BONUS"], "REFERRAL_BONUS", f"refbonus:{referee.pk}", "Welcome bonus")
        r.status, r.rewarded_at = ("REWARDED" if e else "REJECTED"), timezone.now()
        r.save()


@transaction.atomic
def request_withdrawal(user, diamonds):
    p = UserProfile.objects.select_for_update().get(user=user)  # serialise per user: no double spend
    per = R()["DIAMONDS_PER_KES"]
    if not settings.WITHDRAWALS_ENABLED:
        raise ValueError("Withdrawals aren't open yet.")
    if p.rewards_frozen:
        raise ValueError("Rewards are paused on this account. Contact support.")
    if not p.phone_verified:
        raise ValueError("Verify your phone number first. Withdrawals go to that number.")
    biz = getattr(user, "business", None)
    if biz and not biz.verified:
        raise ValueError("Complete identity verification before withdrawing.")
    if user.date_joined > timezone.now() - timedelta(days=R()["MIN_ACCOUNT_AGE_DAYS"]):
        raise ValueError(f"New accounts can withdraw after {R()['MIN_ACCOUNT_AGE_DAYS']} days.")
    diamonds = int(diamonds)
    if diamonds < R()["MIN_WITHDRAW_DIAMONDS"] or diamonds % per:
        raise ValueError(f"Withdraw at least {R()['MIN_WITHDRAW_DIAMONDS']} diamonds, in multiples of {per}.")
    if diamonds > balance(user)["available"]:
        raise ValueError("You don't have that many available diamonds.")
    if user.withdrawals.filter(status__in=["REQUESTED", "APPROVED", "PROCESSING"]).exists():
        raise ValueError("You already have a withdrawal in progress.")
    w = Withdrawal.objects.create(user=user, diamonds=diamonds, kes=Decimal(diamonds // per), phone=p.phone)
    DiamondEntry.objects.create(user=user, amount=-diamonds, kind="WITHDRAWAL", ref=f"wd:{w.pk}",
                                available_at=timezone.now(), note="Withdrawal requested")
    audit(user, "withdrawal.requested", w.pk, diamonds=diamonds)
    return w


def send_withdrawal(w):
    oid = f"WD-{w.pk}-{secrets.token_hex(4)}"
    try:
        mpesa.b2c(w.phone, w.kes, "GlowHub reward", "Reward", oid)
    except Exception:
        log.exception("B2C withdrawal request failed")
        return
    w.originator_id, w.status = oid, "PROCESSING"
    w.save()


def reverse_withdrawal(w):
    DiamondEntry.objects.get_or_create(ref=f"wdr:{w.pk}", defaults=dict(
        user=w.user, amount=w.diamonds, kind="WITHDRAWAL_REVERSAL", available_at=timezone.now(), note="Withdrawal not completed"))


def handle_withdrawal_result(oid, ok, result):
    with transaction.atomic():
        w = Withdrawal.objects.select_for_update().filter(originator_id=oid).first()
        if not w or w.status != "PROCESSING":
            return
        if ok:
            w.status, w.receipt = "PAID", str(result.get("TransactionID", ""))[:30]
        else:
            w.status = "FAILED"
            reverse_withdrawal(w)
        w.save()
    notify(w.user, "Reward withdrawal", f"Your withdrawal of KSh {w.kes:.0f} is {w.status.lower()}.", urgent=True)
