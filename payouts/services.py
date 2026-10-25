import logging, secrets
from decimal import Decimal
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounts.services import get_profile
from bookings import mpesa
from core.services import audit, notify
from .models import LedgerEntry, Payout

log = logging.getLogger(__name__)
ALLOWED = {"REQUESTED": {"APPROVED", "REJECTED"}, "APPROVED": {"PAID", "FAILED"}, "PROCESSING": {"PAID", "FAILED"}}


def credit_booking(booking):
    amt = booking.deposit_amount
    fee = (amt * Decimal(str(settings.PLATFORM_FEE_PERCENT)) / 100).quantize(Decimal("0.01"))
    avail = booking.start + timedelta(hours=settings.PAYOUT_HOLD_HOURS)  # released after the appointment
    base = dict(business=booking.business, booking=booking, available_at=avail)
    LedgerEntry.objects.get_or_create(ref=f"dep:{booking.pk}", defaults=dict(kind="DEPOSIT", amount=amt, note="Deposit received", **base))
    LedgerEntry.objects.get_or_create(ref=f"fee:{booking.pk}", defaults=dict(kind="FEE", amount=-fee, note="Platform fee", **base))


def reverse_booking(booking):
    now = timezone.now()
    for kind, key, rev in (("REFUND", "dep", "depr"), ("FEE_REVERSAL", "fee", "feer")):
        e = LedgerEntry.objects.filter(ref=f"{key}:{booking.pk}").first()
        if e:
            LedgerEntry.objects.get_or_create(ref=f"{rev}:{booking.pk}", defaults=dict(
                business=e.business, booking=booking, kind=kind, amount=-e.amount, available_at=now, note="Booking cancelled/refunded"))


def balances(business):
    now = timezone.now()
    total = LedgerEntry.objects.filter(business=business).aggregate(s=Sum("amount"))["s"] or Decimal("0")
    avail = LedgerEntry.objects.filter(business=business, available_at__lte=now).aggregate(s=Sum("amount"))["s"] or Decimal("0")
    return {"available": avail, "pending": total - avail}


@transaction.atomic
def request_payout(business, amount, user):
    from marketplace.models import Business
    Business.objects.select_for_update().get(pk=business.pk)  # serialise per business: no double spend
    amount = Decimal(amount).quantize(Decimal("1"))
    profile = get_profile(user)
    if not business.verified:
        raise ValueError("Complete identity verification before requesting a payout.")
    if not profile.phone_verified:
        raise ValueError("Verify your phone number first. Payouts go to that number.")
    if amount < settings.MIN_PAYOUT_KES:
        raise ValueError(f"The minimum payout is KSh {settings.MIN_PAYOUT_KES}.")
    if amount > balances(business)["available"]:
        raise ValueError("That is more than your available balance.")
    if business.payouts.filter(status__in=["REQUESTED", "APPROVED", "PROCESSING"]).exists():
        raise ValueError("You already have a payout in progress.")
    p = Payout.objects.create(business=business, amount=amount, phone=profile.phone)
    LedgerEntry.objects.create(business=business, kind="PAYOUT", amount=-amount, ref=f"payout:{p.pk}",
                               available_at=timezone.now(), note="Payout requested")
    audit(user, "payout.requested", p.pk, amount=str(amount))
    return p


def send_payout(p):
    oid = f"PO-{p.pk}-{secrets.token_hex(4)}"
    try:
        mpesa.b2c(p.phone, p.amount, "GlowHub payout", "Payout", oid)
    except Exception:
        log.exception("B2C payout request failed")
        return  # stays APPROVED; staff can retry or pay manually
    p.originator_id, p.status = oid, "PROCESSING"
    p.save()


def reverse_payout(p):
    LedgerEntry.objects.get_or_create(ref=f"payoutr:{p.pk}", defaults=dict(
        business=p.business, kind="PAYOUT_REVERSAL", amount=p.amount, available_at=timezone.now(), note="Payout not completed"))


def finalize(obj, old, user, send, reverse):
    """Shared by payouts and reward withdrawals after staff change a status."""
    if obj.status == old:
        return
    audit(user, f"{obj._meta.model_name}.{obj.status.lower()}", obj.pk, note=obj.decision_note)
    if obj.status == "APPROVED" and settings.MPESA["B2C_ENABLED"]:
        send(obj)
    elif obj.status in ("REJECTED", "FAILED"):
        reverse(obj)


def handle_b2c_result(payload):
    r = payload.get("Result", {})
    oid, ok = r.get("OriginatorConversationID", ""), r.get("ResultCode") == 0
    if oid.startswith("PO-"):
        with transaction.atomic():
            p = Payout.objects.select_for_update().filter(originator_id=oid).first()
            if not p or p.status != "PROCESSING":
                return  # unknown or duplicate
            if ok:
                p.status, p.receipt = "PAID", str(r.get("TransactionID", ""))[:30]
            else:
                p.status, p.failure_reason = "FAILED", str(r.get("ResultDesc", ""))[:200]
                reverse_payout(p)
            p.save()
        notify(p.business.owner, "Payout update", f"Your payout of KSh {p.amount:.0f} is {p.status.lower()}.", urgent=True)
    elif oid.startswith("WD-"):
        from rewards.services import handle_withdrawal_result
        handle_withdrawal_result(oid, ok, r)
